from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.agents.planner import PlannerAgent
from backend.ai.providers import AIProviderError, ProviderFactory
from backend.core.task_manager import TaskManager
from backend.database.models import (
    AIInterpretation,
    ApprovalHistory,
    ApprovalStatus,
    CorrectionHistory,
    Memory,
    Notification,
    Task,
    TaskApproval,
)

logger = logging.getLogger("nexa.approvals")


@dataclass
class TaskInterpretation:
    corrected_text: str
    intent: str
    task_type: str
    date: str | None = None
    time: str | None = None
    trigger: str | None = None
    action: str | None = None
    priority: str = "normal"
    conditions: dict = field(default_factory=dict)
    confidence: int = 0
    execution_impact: str = "No direct execution until approval."
    high_risk: bool = False
    needs_clarification: bool = False
    provider: str = "local"

    def structured_task(self) -> dict:
        return asdict(self)


class TaskApprovalService:
    confidence_threshold = 80

    correction_map = {
        "remid": "remind",
        "remnd": "remind",
        "assigment": "assignment",
        "assingment": "assignment",
        "tomorow": "tomorrow",
        "battry": "battery",
        "chrom": "Chrome",
        "pythn": "Python",
        "clg": "college",
    }

    high_risk_terms = {
        "shutdown",
        "restart",
        "delete",
        "remove files",
        "kill process",
        "format",
        "registry",
        "move all",
        "browser",
        "login",
        "download",
        "automation",
    }

    def __init__(self, db: Session, scheduler=None) -> None:
        self.db = db
        self.scheduler = scheduler
        self.planner = PlannerAgent()

    def request_approval(self, command: str) -> TaskApproval:
        interpretation = self._interpret(command)
        plan = self.planner.plan(interpretation.corrected_text)
        if plan.requires_confirmation:
            interpretation.high_risk = True
        interpretation.needs_clarification = interpretation.needs_clarification or interpretation.confidence < self.confidence_threshold
        status = ApprovalStatus.needs_clarification.value if interpretation.needs_clarification else ApprovalStatus.pending.value
        approval = TaskApproval(
            original_text=command,
            corrected_text=interpretation.corrected_text,
            intent=interpretation.intent,
            task_type=interpretation.task_type,
            confidence=interpretation.confidence,
            status=status,
            structured_task_json=json.dumps(interpretation.structured_task(), default=str),
            plan_json=json.dumps(plan.__dict__, default=str),
            requires_approval=True,
            high_risk=interpretation.high_risk,
            clarification_required=interpretation.needs_clarification,
            provider=interpretation.provider,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        self._record_interpretation(approval, interpretation)
        self._record_history(approval.id, "created", interpretation.structured_task())
        self._notify_required(approval)
        logger.info(
            "Task approval created id=%s provider=%s confidence=%s status=%s original=%s corrected=%s",
            approval.id,
            approval.provider,
            approval.confidence,
            approval.status,
            command,
            approval.corrected_text,
        )
        return approval

    def approve(self, approval_id: int) -> tuple[TaskApproval, object | None]:
        approval = self._get(approval_id)
        if approval.status == ApprovalStatus.approved.value and approval.task_id:
            return approval, self.db.get(Task, approval.task_id)
        if approval.status == ApprovalStatus.rejected.value:
            raise ValueError("Rejected approvals cannot be approved")
        if approval.clarification_required:
            raise ValueError("Approval requires clarification before execution")
        task = TaskManager(self.db, self.scheduler).create_from_command(approval.corrected_text, auto_confirm=True)
        approval.status = ApprovalStatus.approved.value
        approval.task_id = task.id
        approval.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(approval)
        NotificationAgent(self.db).notify("Nexa Task Approved", f"Created task: {approval.corrected_text}")
        self._record_history(approval.id, "approved", {"task_id": task.id})
        logger.info("Task approval approved id=%s task_id=%s", approval.id, task.id)
        return approval, task

    def reject(self, approval_id: int, reason: str = "") -> TaskApproval:
        approval = self._get(approval_id)
        approval.status = ApprovalStatus.rejected.value
        approval.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(approval)
        self._record_history(approval.id, "rejected", {"reason": reason})
        logger.info("Task approval rejected id=%s reason=%s", approval.id, reason)
        return approval

    def edit(self, approval_id: int, updates: dict) -> TaskApproval:
        approval = self._get(approval_id)
        corrected = self._compose_edited_text(approval.corrected_text, updates)
        self.db.add(CorrectionHistory(original_text=approval.corrected_text, corrected_text=corrected, source="edit"))
        approval.corrected_text = corrected
        approval.structured_task_json = json.dumps({**json.loads(approval.structured_task_json), **updates, "corrected_text": corrected}, default=str)
        plan = self.planner.plan(corrected)
        approval.plan_json = json.dumps(plan.__dict__, default=str)
        approval.status = ApprovalStatus.pending.value
        approval.clarification_required = False
        approval.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(approval)
        self._record_history(approval.id, "edited", updates)
        self._notify_required(approval)
        logger.info("Task approval edited id=%s corrected=%s", approval.id, corrected)
        return approval

    def list(self, limit: int = 100) -> list[TaskApproval]:
        return self.db.query(TaskApproval).order_by(TaskApproval.created_at.desc()).limit(limit).all()

    def serialize(self, approval: TaskApproval, task: object | None = None) -> dict:
        task_payload = None
        if task:
            task_payload = {
                "id": task.id,
                "command": task.command,
                "intent": task.intent,
                "agent": task.agent,
                "status": task.status,
                "requires_confirmation": task.requires_confirmation,
                "plan": json.loads(task.plan_json),
                "result": json.loads(task.result_json),
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }
        return {
            "id": approval.id,
            "original_text": approval.original_text,
            "corrected_text": approval.corrected_text,
            "intent": approval.intent,
            "task_type": approval.task_type,
            "confidence": approval.confidence,
            "status": approval.status,
            "structured_task": json.loads(approval.structured_task_json),
            "plan": json.loads(approval.plan_json),
            "requires_approval": approval.requires_approval,
            "high_risk": approval.high_risk,
            "clarification_required": approval.clarification_required,
            "provider": approval.provider,
            "task_id": approval.task_id,
            "created_at": approval.created_at.isoformat(),
            "updated_at": approval.updated_at.isoformat(),
            "task": task_payload,
        }

    def _interpret(self, command: str) -> TaskInterpretation:
        prompt = self._prompt(command)
        provider = ProviderFactory.create()
        if provider:
            try:
                data = provider.interpret(prompt)
                return self._normalize_provider_response(command, data, provider.name)
            except AIProviderError as exc:
                logger.warning("AI provider failed; falling back to local interpreter: %s", exc)
        return self._local_interpret(command)

    def _prompt(self, command: str) -> str:
        dictionary = self._custom_dictionary()
        return json.dumps({"request": command, "custom_dictionary": dictionary})

    def _normalize_provider_response(self, command: str, data: dict, provider: str) -> TaskInterpretation:
        corrected = str(data.get("corrected_text") or command).strip()
        confidence = int(float(data.get("confidence") or 0))
        return TaskInterpretation(
            corrected_text=corrected,
            intent=str(data.get("intent") or "unknown"),
            task_type=str(data.get("task_type") or "Custom Task"),
            date=data.get("date"),
            time=data.get("time"),
            trigger=data.get("trigger"),
            action=data.get("action"),
            priority=str(data.get("priority") or "normal"),
            conditions=data.get("conditions") if isinstance(data.get("conditions"), dict) else {},
            confidence=max(0, min(100, confidence)),
            execution_impact=str(data.get("execution_impact") or "No direct execution until approval."),
            high_risk=bool(data.get("high_risk")) or self._is_high_risk(corrected),
            needs_clarification=bool(data.get("needs_clarification")),
            provider=provider,
        )

    def _local_interpret(self, command: str) -> TaskInterpretation:
        corrected = self._correct_text(command)
        lower = corrected.lower()
        plan = self.planner.plan(corrected)
        task_type = self._task_type(plan.intent, lower)
        confidence = 75 if plan.intent == "general_memory" else 92
        if any(term in lower for term in ("unclear", "maybe", "something", "thing")):
            confidence = min(confidence, 72)
        if corrected != command:
            confidence = min(98, confidence + 6)
        date_value = self._extract_date(lower)
        time_value = self._extract_time(lower)
        if "remind me" in lower and date_value and not time_value:
            confidence = 78
        if "remind me" in lower and date_value and time_value:
            confidence = 98
            corrected = self._normalize_reminder_text(corrected, date_value, time_value)
        if "battery" in lower and ("below" in lower or "low" in lower):
            task_type = "Automation"
            confidence = max(confidence, 92)
        return TaskInterpretation(
            corrected_text=corrected,
            intent=plan.intent,
            task_type=task_type,
            date=date_value,
            time=time_value,
            trigger=self._trigger(lower),
            action=self._action(plan.intent, corrected),
            confidence=confidence,
            execution_impact=self._impact(plan.agent, plan.action),
            high_risk=plan.requires_confirmation or self._is_high_risk(corrected),
            needs_clarification=confidence < self.confidence_threshold,
            provider="local",
        )

    def _correct_text(self, command: str) -> str:
        words = command.strip().split()
        corrected_words = [self.correction_map.get(word.lower(), word) for word in words]
        text = " ".join(corrected_words)
        text = re.sub(r"\bopen Chrome and search Python\b", "Open Chrome and search for Python", text, flags=re.I)
        text = re.sub(r"\bsubmit assignment\b", "submit my assignment", text, flags=re.I)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1].upper() + text[1:] if text else command

    def _normalize_reminder_text(self, corrected: str, date_value: str, time_value: str) -> str:
        body = re.sub(r"^remind me\s*", "", corrected, flags=re.I).strip()
        body = re.sub(r"\b(tomorrow|today)\b", "", body, flags=re.I).strip()
        body = re.sub(r"\b\d{1,2}(:\d{2})?\s*(am|pm)?\b", "", body, flags=re.I).strip()
        if not body.lower().startswith("to "):
            body = f"to {body}"
        return f"Remind me {body} {date_value} at {time_value}."

    def _extract_date(self, lower: str) -> str | None:
        if "tomorrow" in lower:
            return "tomorrow"
        if "today" in lower:
            return "today"
        return None

    def _extract_time(self, lower: str) -> str | None:
        match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3)
        if meridiem:
            suffix = meridiem.upper()
        else:
            suffix = "AM" if hour <= 11 else "PM"
        display_hour = hour if 1 <= hour <= 12 else ((hour - 1) % 12) + 1
        return f"{display_hour}:{minute:02d} {suffix}"

    def _task_type(self, intent: str, lower: str) -> str:
        if "remind" in lower or "reminder" in intent:
            return "Reminder"
        if "schedule" in intent:
            return "Schedule"
        if "automation" in lower or "when " in lower:
            return "Automation"
        if any(term in lower for term in ("shutdown", "restart", "sleep", "lock")):
            return "System Action"
        if any(term in lower for term in ("file", "folder", "pdf", "backup", "delete")):
            return "File Operation"
        if any(term in lower for term in ("open", "chrome", "browser", "google")):
            return "Browser Operation"
        if "coding" in intent or "code" in lower:
            return "Coding Task"
        if "research" in lower:
            return "Research Task"
        return "Custom Task"

    def _trigger(self, lower: str) -> str | None:
        if "battery" in lower and ("below" in lower or "low" in lower):
            percent = re.search(r"(\d{1,3})\s*(percent|%)", lower)
            threshold = percent.group(1) if percent else "configured threshold"
            return f"Battery <= {threshold}%"
        if "codex" in lower and "finish" in lower:
            return "Codex queue finished"
        return None

    def _action(self, intent: str, corrected: str) -> str:
        if "reminder" in intent or corrected.lower().startswith("remind me"):
            return "Create reminder"
        if "shutdown" in corrected.lower():
            return "Shutdown computer"
        if "restart" in corrected.lower():
            return "Restart computer"
        if "delete" in corrected.lower():
            return "Delete files"
        return "Create approved Nexa task"

    def _impact(self, agent: str, action: str) -> str:
        if agent == "system":
            return "System action requiring explicit user approval."
        if agent == "file" and action.startswith(("delete", "move")):
            return "File system change requiring explicit user approval."
        if agent == "browser":
            return "Browser automation will run only after approval."
        if agent == "scheduler":
            return "Scheduled task will be created only after approval."
        return "Task will be stored and executed only after approval."

    def _is_high_risk(self, text: str) -> bool:
        lower = text.lower()
        return any(term in lower for term in self.high_risk_terms)

    def _custom_dictionary(self) -> dict:
        rows = self.db.query(Memory).filter(Memory.scope == "correction_dictionary").all()
        return {row.key: row.value for row in rows}

    def _record_interpretation(self, approval: TaskApproval, interpretation: TaskInterpretation) -> None:
        self.db.add(
            AIInterpretation(
                approval_id=approval.id,
                provider=interpretation.provider,
                original_text=approval.original_text,
                response_json=json.dumps(interpretation.structured_task(), default=str),
                confidence=interpretation.confidence,
            )
        )
        if approval.original_text != approval.corrected_text:
            self.db.add(CorrectionHistory(original_text=approval.original_text, corrected_text=approval.corrected_text, source=interpretation.provider))
        self.db.commit()

    def _record_history(self, approval_id: int, action: str, payload: dict) -> None:
        self.db.add(ApprovalHistory(approval_id=approval_id, action=action, payload_json=json.dumps(payload, default=str)))
        self.db.commit()

    def _notify_required(self, approval: TaskApproval) -> None:
        warning = " Confidence is below 80%; clarification is required." if approval.clarification_required else ""
        message = (
            "I interpreted your request as:\n\n"
            f"\"{approval.corrected_text}\"\n\n"
            f"Intent: {approval.intent}\n"
            f"Type: {approval.task_type}\n"
            f"Confidence: {approval.confidence}%\n"
            "Actions: Approve, Edit, Reject."
            f"{warning}"
        )
        self.db.add(Notification(title="Nexa Task Approval Required", message=message))
        self.db.commit()

    def _get(self, approval_id: int) -> TaskApproval:
        approval = self.db.get(TaskApproval, approval_id)
        if not approval:
            raise ValueError("Approval not found")
        return approval

    def _compose_edited_text(self, current: str, updates: dict) -> str:
        title = str(updates.get("task_title") or updates.get("title") or current).strip()
        date_value = str(updates.get("date") or "").strip()
        time_value = str(updates.get("time") or "").strip()
        trigger = str(updates.get("trigger") or "").strip()
        if trigger:
            return f"{title}. Trigger: {trigger}"
        if date_value and time_value:
            return f"{title} on {date_value} at {time_value}"
        if date_value:
            return f"{title} on {date_value}"
        return title
