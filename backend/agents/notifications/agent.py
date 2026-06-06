import logging

from sqlalchemy.orm import Session

from backend.database.models import Notification


class NotificationAgent:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def notify(self, title: str, message: str) -> dict:
        if self.db:
            row = Notification(title=title, message=message)
            self.db.add(row)
            self.db.commit()
        try:
            from plyer import notification

            notification.notify(title=title, message=message, app_name="Nexa")
        except Exception as exc:
            logging.getLogger(__name__).debug("Desktop notification provider unavailable: %s", exc)
        return {"title": title, "message": message}
