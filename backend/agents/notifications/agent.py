from sqlalchemy.orm import Session

from backend.services.alert_framework import AlertPayload, AlertService


class NotificationAgent:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def notify(
        self,
        title: str,
        message: str,
        *,
        alert_type: str = "general",
        module: str = "notifications",
        severity: str = "low",
        priority: str = "low",
        category: str = "info",
        suggested_action: str = "Review the notification details.",
        action_buttons: list[str] | None = None,
        voice_message: str = "",
        sound_path: str | None = None,
        sound_enabled: bool = False,
        voice_enabled: bool = False,
        notification_enabled: bool = True,
        metadata: dict | None = None,
    ) -> dict:
        return AlertService(self.db).send(
            AlertPayload(
                alert_type=alert_type,
                module=module,
                title=title,
                message=message,
                suggested_action=suggested_action,
                action_buttons=action_buttons or ["Dismiss"],
                severity=severity,
                priority=priority,
                category=category,
                voice_message=voice_message,
                sound_path=sound_path,
                sound_enabled=sound_enabled,
                voice_enabled=voice_enabled,
                notification_enabled=notification_enabled,
                metadata=metadata or {},
            )
        )
