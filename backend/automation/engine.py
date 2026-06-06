from __future__ import annotations

import json
from datetime import datetime

import psutil
from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.agents.scheduler import SchedulerAgent
from backend.agents.file_agent import FileAgent
from backend.database.models import Automation, Event


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

    def create(self, name: str, condition: dict, action: dict) -> dict:
        row = Automation(name=name, condition_json=json.dumps(condition), action_json=json.dumps(action))
        self.db.add(row)
        self.db.commit()
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
                fired.append(self._execute_action(automation.name, action))
                self.db.add(Event(event_type="automation_fired", payload_json=json.dumps({"automation": automation.name, "at": datetime.utcnow().isoformat()})))
        self.db.commit()
        return fired

    def ingest_event(self, event_type: str, payload: dict) -> list[dict]:
        self.db.add(Event(event_type=event_type, payload_json=json.dumps(payload)))
        fired = []
        for automation in self.db.query(Automation).filter(Automation.enabled.is_(True)).all():
            condition = json.loads(automation.condition_json)
            if condition.get("event_type") == event_type:
                action = json.loads(automation.action_json)
                fired.append(self._execute_action(automation.name, action))
        self.db.commit()
        return fired

    def context(self) -> dict:
        battery = psutil.sensors_battery()
        processes = [proc.info.get("name", "").lower() for proc in psutil.process_iter(["name"])]
        return {
            "battery": battery.percent if battery else None,
            "cpu": psutil.cpu_percent(interval=0.1),
            "ram": psutil.virtual_memory().percent,
            "vscode_running": "code.exe" in processes,
            "cursor_running": "cursor.exe" in processes,
        }

    def _matches(self, condition: dict, context: dict) -> bool:
        metric = condition.get("metric")
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

    def _execute_action(self, name: str, action: dict) -> dict:
        if action.get("type") == "notify":
            message = action.get("message", f"Automation fired: {name}")
            return self.notifications.notify(name, message)
        if action.get("type") == "schedule_delay":
            return SchedulerAgent().schedule_delay(action["command"], int(action.get("delay_seconds", 300)))
        if action.get("type") == "move_by_extension":
            return FileAgent().move_by_extension(action["extension"], action["destination"], action.get("source"))
        if action.get("type") == "backup_folder":
            return FileAgent().backup_folder(action.get("command", name), action.get("source"), action.get("destination"))
        return {"automation": name, "skipped": action}

    def serialize(self, row: Automation) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "condition": json.loads(row.condition_json),
            "action": json.loads(row.action_json),
            "enabled": row.enabled,
        }
