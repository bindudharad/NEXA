from sqlalchemy.orm import Session

from backend.database.models import Memory, Setting, Task


class MemoryAgent:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def remember_command(self, command: str) -> dict:
        memory = Memory(key="last_unclassified_command", value=command)
        self.db.add(memory)
        self.db.commit()
        return {"remembered": command}

    def set(self, key: str, value: str, scope: str = "global") -> dict:
        memory = Memory(key=key, value=value, scope=scope)
        self.db.add(memory)
        self.db.commit()
        return {"id": memory.id, "key": key}

    def set_setting(self, key: str, value: str) -> dict:
        row = self.db.query(Setting).filter(Setting.key == key).one_or_none()
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
            self.db.add(row)
        self.db.commit()
        return {"key": key, "value": value}

    def conversation_history(self, limit: int = 50) -> list[dict]:
        tasks = self.db.query(Task).order_by(Task.created_at.desc()).limit(limit).all()
        return [{"id": task.id, "command": task.command, "status": task.status, "created_at": task.created_at.isoformat()} for task in tasks]

    def list(self) -> list[dict]:
        rows = self.db.query(Memory).order_by(Memory.created_at.desc()).limit(100).all()
        return [{"id": row.id, "key": row.key, "value": row.value, "scope": row.scope} for row in rows]
