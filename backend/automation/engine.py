from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter

import psutil
from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.agents.scheduler import SchedulerAgent
from backend.agents.file_agent import FileAgent
from backend.database.models import Automation, AutomationAction, AutomationAnalytics, AutomationCondition, AutomationHistory, AutomationTemplate, AutomationTrigger, Event


class AutomationEngine:
    operators = {
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b,
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.notifications = NotificationAgent(db)

    high_risk_actions = {"shutdown", "restart", "sleep", "delete", "delete_files", "delete_project", "move_files", "execute_script", "script", "browser_automation", "credential_usage", "registry_change"}

    def create(self, name: str, condition: dict, action: dict, description: str = "", schedule: dict | None = None, priority: str = "medium", owner: str = "local", approval_rules: dict | None = None) -> dict:
        row = Automation(name=name, condition_json=json.dumps(condition), action_json=json.dumps(action))
        self.db.add(row)
        self.db.flush()
        self._sync_structure(row, condition, action, description, schedule or {}, priority, owner, approval_rules or {})
        self._history(row.id, "created", {"condition": condition, "action": action}, {"message": "Automation created"}, "created")
        self.db.commit()
        self.db.refresh(row)
        return self.serialize(row)

    def list(self) -> list[dict]:
        return [self.serialize(row) for row in self.db.query(Automation).order_by(Automation.created_at.desc()).all()]

    def evaluate(self) -> list[dict]:
        context = self.context()
        fired = []
        for automation in self.db.query(Automation).filter(Automation.enabled.is_(True)).all():
            condition = json.loads(automation.condition_json)
            if self._matches(condition, context):
                action = json.loads(automation.action_json)
                fired.append(self._execute_with_history(automation, action, {"context": context, "condition": condition}))
                self.db.add(Event(event_type="automation_fired", payload_json=json.dumps({"automation": automation.name, "at": datetime.utcnow().isoformat()})))
        self.db.commit()
        return fired

    def ingest_event(self, event_type: str, payload: dict) -> list[dict]:
        self.db.add(Event(event_type=event_type, payload_json=json.dumps(payload)))
        fired = []
        for automation in self.db.query(Automation).filter(Automation.enabled.is_(True)).all():
            condition = json.loads(automation.condition_json)
            if condition.get("event_type") == event_type or self._matches(condition, payload | {"event_type": event_type}):
                action = json.loads(automation.action_json)
                fired.append(self._execute_with_history(automation, action, {"event_type": event_type, "payload": payload}))
        self.db.commit()
        return fired

    def context(self) -> dict:
        battery = psutil.sensors_battery()
        processes = [proc.info.get("name", "").lower() for proc in psutil.process_iter(["name"])]
        return {
            "battery": battery.percent if battery else None,
            "charging": bool(battery.power_plugged) if battery else None,
            "cpu": psutil.cpu_percent(interval=0.1),
            "ram": psutil.virtual_memory().percent,
            "vscode_running": "code.exe" in processes,
            "cursor_running": "cursor.exe" in processes,
        }

    def _matches(self, condition: dict, context: dict) -> bool:
        if "all" in condition:
            return all(self._matches(item, context) for item in condition.get("all", []))
        if "any" in condition:
            return any(self._matches(item, context) for item in condition.get("any", []))
        if "not" in condition:
            return not self._matches(condition.get("not", {}), context)
        metric = condition.get("metric")
        if condition.get("event_type") and context.get("event_type"):
            return condition.get("event_type") == context.get("event_type")
        if not metric:
            return False
        op = condition.get("operator")
        value = condition.get("value")
        current = context.get(metric)
        if op == "changed_to_false":
            return current is False and value is False
        if current is None or op not in self.operators:
            return False
        return self.operators[op](current, value)

    def _execute_with_history(self, automation: Automation, action: dict, trigger_event: dict) -> dict:
        started = perf_counter()
        try:
            result = self._execute_action(automation.name, action)
            status = "approval_required" if result.get("requires_approval") else "success"
            approval = "pending" if result.get("requires_approval") else ""
            self._history(automation.id, "executed", trigger_event, result, status, approval, (perf_counter() - started) * 1000)
            self._analytics(automation.id, status)
            return result
        except Exception as exc:
            error = str(exc)
            self._history(automation.id, "failed", trigger_event, {}, "failed", error=error, runtime_ms=(perf_counter() - started) * 1000)
            self._analytics(automation.id, "failed")
            return {"automation": automation.name, "error": error}

    def _execute_action(self, name: str, action: dict) -> dict:
        action_type = action.get("type", "")
        if action_type in self.high_risk_actions or action.get("requires_approval"):
            notification = self.notifications.notify(
                "Nexa Automation Approval Required",
                f"Approval required before automation can run: {name}",
                alert_type="automation_approval",
                module="automation_engine",
                severity="high",
                priority="high",
                category="warning",
                suggested_action="Approve, edit, or reject this automation before execution.",
                action_buttons=["Approve", "Edit", "Reject"],
                metadata={"automation": name, "action": action},
            )
            return {"automation": name, "requires_approval": True, "notification_id": notification.get("id"), "action": action}
        if action_type == "notify":
            message = action.get("message", f"Automation fired: {name}")
            return self.notifications.notify(
                "Nexa Automation",
                message,
                alert_type="automation",
                module="automation_engine",
                severity="low",
                priority="medium",
                category="automation",
                suggested_action="View the automation log or dismiss this alert.",
                action_buttons=["View Log", "Dismiss"],
                voice_message="Automation completed successfully.",
                voice_enabled=bool(action.get("voice_enabled", False)),
                metadata={"automation": name, "action": action},
            )
        if action_type == "voice_alert":
            return self.notifications.notify(
                "Nexa Automation",
                action.get("message", f"Automation fired: {name}"),
                alert_type="automation",
                module="automation_engine",
                severity="low",
                priority="medium",
                category="automation",
                suggested_action="Review the automation history.",
                action_buttons=["View History", "Dismiss"],
                voice_message=action.get("voice_message", action.get("message", "Automation completed successfully.")),
                voice_enabled=True,
                metadata={"automation": name, "action": action},
            )
        if action_type == "schedule_delay":
            return SchedulerAgent().schedule_delay(action["command"], int(action.get("delay_seconds", 300)))
        if action_type == "move_by_extension":
            return FileAgent().move_by_extension(action["extension"], action["destination"], action.get("source"))
        if action_type == "backup_folder":
            return FileAgent().backup_folder(action.get("command", name), action.get("source"), action.get("destination"))
        return {"automation": name, "skipped": action}

    def serialize(self, row: Automation) -> dict:
        triggers = [self._trigger_dict(item) for item in self.db.query(AutomationTrigger).filter(AutomationTrigger.automation_id == row.id).order_by(AutomationTrigger.id.asc()).all()]
        conditions = [self._condition_dict(item) for item in self.db.query(AutomationCondition).filter(AutomationCondition.automation_id == row.id).order_by(AutomationCondition.priority.asc()).all()]
        actions = [self._action_dict(item) for item in self.db.query(AutomationAction).filter(AutomationAction.automation_id == row.id).order_by(AutomationAction.order_index.asc()).all()]
        return {
            "id": row.id,
            "name": row.name,
            "condition": json.loads(row.condition_json),
            "action": json.loads(row.action_json),
            "trigger": triggers[0] if triggers else json.loads(row.condition_json),
            "triggers": triggers,
            "conditions": conditions,
            "actions": actions,
            "enabled": row.enabled,
            "created_at": row.created_at.isoformat(),
        }

    def dashboard(self) -> dict:
        items = self.list()
        history = [self._history_dict(row) for row in self.db.query(AutomationHistory).order_by(AutomationHistory.created_at.desc()).limit(50).all()]
        analytics = self.analytics()
        return {
            "active": [item for item in items if item["enabled"]],
            "paused": [item for item in items if not item["enabled"]],
            "completed": [item for item in history if item["status"] == "success"],
            "failed": [item for item in history if item["status"] == "failed"],
            "recent_executions": history,
            "statistics": analytics["summary"],
            "templates": self.templates(),
            "offline_ready": True,
        }

    def history(self, limit: int = 100) -> list[dict]:
        return [self._history_dict(row) for row in self.db.query(AutomationHistory).order_by(AutomationHistory.created_at.desc()).limit(limit).all()]

    def templates(self) -> list[dict]:
        self.ensure_templates()
        return [self._template_dict(row) for row in self.db.query(AutomationTemplate).order_by(AutomationTemplate.category.asc(), AutomationTemplate.name.asc()).all()]

    def analytics(self) -> dict:
        history = self.db.query(AutomationHistory).all()
        total = len(history)
        success = sum(1 for item in history if item.status == "success")
        failed = sum(1 for item in history if item.status == "failed")
        approvals = sum(1 for item in history if item.status == "approval_required" or item.approval_status == "pending")
        avg_runtime = round(sum(item.runtime_ms for item in history) / max(total, 1), 2)
        usage: dict[int, int] = {}
        for item in history:
            if item.automation_id:
                usage[item.automation_id] = usage.get(item.automation_id, 0) + 1
        most_used = [{"automation_id": key, "count": value} for key, value in sorted(usage.items(), key=lambda pair: pair[1], reverse=True)[:10]]
        return {"summary": {"total_executions": total, "success_rate": round(success / max(total, 1) * 100, 2), "failure_rate": round(failed / max(total, 1) * 100, 2), "pending_approvals": approvals, "average_runtime_ms": avg_runtime, "most_used": most_used}, "rows": [self._analytics_dict(row) for row in self.db.query(AutomationAnalytics).order_by(AutomationAnalytics.created_at.desc()).limit(30).all()]}

    def ensure_templates(self) -> None:
        if self.db.query(AutomationTemplate).count():
            return
        templates = [
            ("Battery Low Alert", "Notify when battery is low and not charging.", "battery", {"metric": "battery", "operator": "<=", "value": 20}, [{"metric": "charging", "operator": "==", "value": False}], [{"type": "notify", "message": "Battery is low. Please connect your charger."}]),
            ("Battery Full Alert", "Notify when battery reaches full charge.", "battery", {"metric": "battery", "operator": ">=", "value": 100}, [], [{"type": "notify", "message": "Battery fully charged."}]),
            ("GPU Temperature Alert", "Warn when GPU temperature is high.", "system", {"metric": "gpu_temperature", "operator": ">", "value": 80}, [], [{"type": "notify", "message": "GPU temperature is above threshold."}]),
            ("Website Monitoring", "Notify when a monitored website is available.", "website", {"event_type": "website_available"}, [], [{"type": "notify", "message": "Monitored website is available."}]),
            ("KCET Monitoring", "Check KCET result availability.", "college", {"event_type": "kcet_available"}, [], [{"type": "notify", "message": "KCET update is available."}]),
            ("Project Backup", "Backup project before risky operations.", "project", {"event_type": "before_restart"}, [], [{"type": "backup_folder", "message": "Project backup requested."}]),
            ("Download Cleanup", "Suggest cleanup after large downloads.", "downloads", {"event_type": "large_download"}, [], [{"type": "notify", "message": "Large download detected. Review cleanup suggestions."}]),
        ]
        for name, description, category, trigger, conditions, actions in templates:
            self.db.add(AutomationTemplate(name=name, description=description, category=category, trigger_json=json.dumps(trigger), conditions_json=json.dumps(conditions), actions_json=json.dumps(actions), approval_rules_json=json.dumps({"high_risk_actions": sorted(self.high_risk_actions)})))
        self.db.commit()

    def _sync_structure(self, row: Automation, condition: dict, action: dict, description: str, schedule: dict, priority: str, owner: str, approval_rules: dict) -> None:
        trigger_type = self._trigger_type(condition)
        self.db.add(AutomationTrigger(automation_id=row.id, trigger_type=trigger_type, event_type=condition.get("event_type", ""), metric=condition.get("metric", ""), operator=condition.get("operator", ""), value_json=json.dumps(condition.get("value")), schedule_json=json.dumps(schedule), metadata_json=json.dumps({"description": description, "priority": priority, "owner": owner})))
        expressions = condition.get("all") or condition.get("any") or [condition]
        join = "AND" if condition.get("all") else "OR" if condition.get("any") else "AND"
        for index, expr in enumerate(expressions):
            self.db.add(AutomationCondition(automation_id=row.id, expression_json=json.dumps(expr), join_operator=join, priority=index))
        risk = "high" if action.get("type") in self.high_risk_actions or action.get("requires_approval") else "low"
        self.db.add(AutomationAction(automation_id=row.id, action_type=action.get("type", "notify"), payload_json=json.dumps(action), requires_approval=risk == "high" or approval_rules.get("required", False), risk_level=risk))

    def _trigger_type(self, condition: dict) -> str:
        event_type = condition.get("event_type", "")
        metric = condition.get("metric", "")
        if event_type:
            return event_type.split("_")[0]
        if metric in {"battery", "charging"}:
            return "battery"
        if metric in {"cpu", "gpu", "ram", "disk"}:
            return "system"
        return "custom"

    def _history(self, automation_id: int | None, event_type: str, trigger_event: dict, result: dict, status: str, approval_status: str = "", runtime_ms: float = 0, error: str = "") -> None:
        self.db.add(AutomationHistory(automation_id=automation_id, event_type=event_type, trigger_event_json=json.dumps(trigger_event), result_json=json.dumps(result), status=status, approval_status=approval_status, runtime_ms=runtime_ms, error=error))

    def _analytics(self, automation_id: int | None, status: str) -> None:
        today = datetime.utcnow().date().isoformat()
        row = self.db.query(AutomationAnalytics).filter(AutomationAnalytics.automation_id == automation_id, AutomationAnalytics.analytics_date == today).first()
        if row is None:
            row = AutomationAnalytics(automation_id=automation_id, analytics_date=today)
            self.db.add(row)
        row.execution_count = (row.execution_count or 0) + 1
        row.success_count = (row.success_count or 0) + (1 if status == "success" else 0)
        row.failure_count = (row.failure_count or 0) + (1 if status == "failed" else 0)
        row.approval_count = (row.approval_count or 0) + (1 if status == "approval_required" else 0)

    def _trigger_dict(self, row: AutomationTrigger) -> dict:
        return {"id": row.id, "trigger_type": row.trigger_type, "event_type": row.event_type, "metric": row.metric, "operator": row.operator, "value": json.loads(row.value_json), "schedule": json.loads(row.schedule_json), "metadata": json.loads(row.metadata_json), "created_at": row.created_at.isoformat()}

    def _condition_dict(self, row: AutomationCondition) -> dict:
        return {"id": row.id, "condition_type": row.condition_type, "expression": json.loads(row.expression_json), "join_operator": row.join_operator, "priority": row.priority, "created_at": row.created_at.isoformat()}

    def _action_dict(self, row: AutomationAction) -> dict:
        return {"id": row.id, "action_type": row.action_type, "payload": json.loads(row.payload_json), "requires_approval": row.requires_approval, "risk_level": row.risk_level, "order_index": row.order_index, "status": row.status, "created_at": row.created_at.isoformat()}

    def _history_dict(self, row: AutomationHistory) -> dict:
        return {"id": row.id, "automation_id": row.automation_id, "event_type": row.event_type, "trigger_event": json.loads(row.trigger_event_json), "result": json.loads(row.result_json), "status": row.status, "error": row.error, "approval_status": row.approval_status, "runtime_ms": row.runtime_ms, "created_at": row.created_at.isoformat()}

    def _template_dict(self, row: AutomationTemplate) -> dict:
        return {"id": row.id, "name": row.name, "description": row.description, "category": row.category, "trigger": json.loads(row.trigger_json), "conditions": json.loads(row.conditions_json), "actions": json.loads(row.actions_json), "schedule": json.loads(row.schedule_json), "approval_rules": json.loads(row.approval_rules_json), "enabled": row.enabled, "created_at": row.created_at.isoformat()}

    def _analytics_dict(self, row: AutomationAnalytics) -> dict:
        return {"id": row.id, "automation_id": row.automation_id, "analytics_date": row.analytics_date, "execution_count": row.execution_count, "success_count": row.success_count, "failure_count": row.failure_count, "approval_count": row.approval_count, "average_runtime_ms": row.average_runtime_ms, "metadata": json.loads(row.metadata_json), "created_at": row.created_at.isoformat()}
