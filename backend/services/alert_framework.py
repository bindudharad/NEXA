from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from backend.database.models import AlertAction, AlertEvent, AlertSetting, Notification, NotificationHistory
from backend.database.session import SessionLocal

alerts_logger = logging.getLogger("nexa.alerts")


@dataclass(frozen=True)
class AlertStyle:
    sound: str
    icon: str
    color: str
    css_class: str


ALERT_STYLES: dict[str, AlertStyle] = {
    "info": AlertStyle("assets/sounds/nexa-info.wav", "Info", "#38bdf8", "alert-info"),
    "success": AlertStyle("assets/sounds/nexa-success.wav", "CheckCircle", "#22c55e", "alert-success"),
    "warning": AlertStyle("assets/sounds/low-battery-alert.wav", "TriangleAlert", "#f59e0b", "alert-warning"),
    "critical": AlertStyle("assets/sounds/nexa-critical.wav", "OctagonAlert", "#ef4444", "alert-critical"),
    "reminder": AlertStyle("assets/sounds/nexa-reminder.wav", "CalendarClock", "#a78bfa", "alert-reminder"),
    "automation": AlertStyle("assets/sounds/nexa-automation.wav", "Workflow", "#14b8a6", "alert-automation"),
}


@dataclass
class AlertPayload:
    alert_type: str
    module: str
    title: str
    message: str
    suggested_action: str
    action_buttons: list[str]
    severity: str = "low"
    priority: str = "low"
    category: str = "info"
    voice_message: str = ""
    sound_path: str | None = None
    sound_enabled: bool = False
    voice_enabled: bool = False
    notification_enabled: bool = True
    metadata: dict = field(default_factory=dict)


class AlertService:
    global_settings_key = "global_alert_settings"

    def __init__(self, db: Session | None = None, db_factory: Callable[[], Session] = SessionLocal) -> None:
        self.db = db
        self.db_factory = db_factory

    def send(self, payload: AlertPayload) -> dict:
        self._validate(payload)
        owns_db = self.db is None
        db = self.db or self.db_factory()
        try:
            settings = self.get_settings(db)
            style = ALERT_STYLES[payload.category]
            sound_path = str(Path(payload.sound_path or style.sound).resolve())
            voice_text = payload.voice_message if payload.voice_enabled and settings["voice_enabled"] else ""
            sound_used = sound_path if payload.sound_enabled and settings["sound_enabled"] else ""
            now = datetime.utcnow()
            row = Notification(
                title=payload.title,
                message=payload.message,
                alert_type=payload.alert_type,
                module=payload.module,
                severity=payload.severity,
                priority=payload.priority,
                category=payload.category,
                icon=style.icon,
                color=style.color,
                suggested_action=payload.suggested_action,
                action_buttons_json=json.dumps(payload.action_buttons),
                voice_used=voice_text,
                sound_used=sound_used,
                status="sent" if payload.notification_enabled else "logged",
                metadata_json=json.dumps({**payload.metadata, "timestamp": now.isoformat(), "style": style.css_class}, default=str),
                created_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            self._event(db, row.id, "alert_triggered", payload.module, self._event_payload(payload, sound_used, voice_text))
            self._history(db, row.id, payload, "notification_sent" if payload.notification_enabled else "notification_logged")
            db.commit()
            self._native_notify(payload, row.id) if payload.notification_enabled else None
            if sound_used:
                self._play_sound(sound_used, row.id)
            if voice_text:
                self._speak(voice_text, row.id)
            alerts_logger.info(
                "Alert Triggered id=%s type=%s module=%s severity=%s sound=%s voice=%s title=%s reason=%s action=%s",
                row.id,
                payload.alert_type,
                payload.module,
                payload.severity,
                sound_used or "none",
                "yes" if voice_text else "no",
                payload.title,
                payload.message.replace("\n", " "),
                payload.suggested_action,
            )
            return self.serialize(row)
        finally:
            if owns_db:
                db.close()

    def list(self, limit: int = 100, query: str | None = None, alert_type: str | None = None, severity: str | None = None, unread_only: bool = False) -> list[dict]:
        owns_db = self.db is None
        db = self.db or self.db_factory()
        try:
            rows = db.query(Notification)
            if query:
                like = f"%{query}%"
                rows = rows.filter((Notification.title.ilike(like)) | (Notification.message.ilike(like)) | (Notification.module.ilike(like)))
            if alert_type:
                rows = rows.filter(Notification.alert_type == alert_type)
            if severity:
                rows = rows.filter(Notification.severity == severity)
            if unread_only:
                rows = rows.filter(Notification.read.is_(False))
            return [self.serialize(row) for row in rows.order_by(Notification.created_at.desc()).limit(limit).all()]
        finally:
            if owns_db:
                db.close()

    def mark_read(self, notification_id: int, read: bool = True) -> dict:
        with self.db_factory() as db:
            row = db.get(Notification, notification_id)
            if not row:
                raise ValueError("Notification not found")
            row.read = read
            self._history_from_row(db, row, "marked_read" if read else "marked_unread", {"read": read})
            db.commit()
            db.refresh(row)
            return self.serialize(row)

    def delete(self, notification_id: int) -> dict:
        with self.db_factory() as db:
            row = db.get(Notification, notification_id)
            if not row:
                raise ValueError("Notification not found")
            db.query(AlertAction).filter(AlertAction.notification_id == row.id).delete()
            db.query(AlertEvent).filter(AlertEvent.notification_id == row.id).delete()
            db.query(NotificationHistory).filter(NotificationHistory.notification_id == row.id).delete()
            db.delete(row)
            db.commit()
            return {"deleted": True, "id": notification_id}

    def record_action(self, notification_id: int, action: str, payload: dict | None = None) -> dict:
        with self.db_factory() as db:
            row = db.get(Notification, notification_id)
            if not row:
                raise ValueError("Notification not found")
            row.user_action = action
            row.status = "acted"
            db.add(AlertAction(notification_id=row.id, action=action, payload_json=json.dumps(payload or {}, default=str)))
            self._history_from_row(db, row, "user_action", {"action": action, "payload": payload or {}})
            db.commit()
            db.refresh(row)
            alerts_logger.info("User Action notification_id=%s action=%s", notification_id, action)
            return self.serialize(row)

    def export(self) -> dict:
        rows = self.list(limit=1000)
        return {"exported_at": datetime.utcnow().isoformat(), "count": len(rows), "notifications": rows}

    def stats(self) -> dict:
        owns_db = self.db is None
        db = self.db or self.db_factory()
        try:
            rows = db.query(Notification).all()
            by_severity: dict[str, int] = {}
            by_type: dict[str, int] = {}
            unread = 0
            for row in rows:
                by_severity[row.severity] = by_severity.get(row.severity, 0) + 1
                by_type[row.alert_type] = by_type.get(row.alert_type, 0) + 1
                unread += 0 if row.read else 1
            return {"total": len(rows), "unread": unread, "by_severity": by_severity, "by_type": by_type}
        finally:
            if owns_db:
                db.close()

    def get_settings(self, db: Session | None = None) -> dict:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            defaults = {
                "sound_enabled": True,
                "voice_enabled": True,
                "sound_volume": 80,
                "notification_position": "system",
                "notification_duration_seconds": 8,
            }
            row = db.query(AlertSetting).filter(AlertSetting.key == self.global_settings_key).one_or_none()
            if not row:
                return defaults
            return {**defaults, **json.loads(row.value_json)}
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            current = self.get_settings(db)
            current.update({key: value for key, value in updates.items() if value is not None})
            row = db.query(AlertSetting).filter(AlertSetting.key == self.global_settings_key).one_or_none()
            if row:
                row.value_json = json.dumps(current, default=str)
                row.updated_at = datetime.utcnow()
            else:
                db.add(AlertSetting(key=self.global_settings_key, value_json=json.dumps(current, default=str)))
            db.commit()
            return current
        finally:
            if owns_db:
                db.close()

    def serialize(self, row: Notification) -> dict:
        return {
            "id": row.id,
            "alert_type": row.alert_type,
            "module": row.module,
            "title": row.title,
            "message": row.message,
            "timestamp": row.created_at.isoformat(),
            "suggested_action": row.suggested_action,
            "action_buttons": json.loads(row.action_buttons_json or "[]"),
            "severity": row.severity,
            "priority": row.priority,
            "category": row.category,
            "icon": row.icon,
            "color": row.color,
            "user_action": row.user_action,
            "voice_used": row.voice_used,
            "sound_used": row.sound_used,
            "status": row.status,
            "read": row.read,
            "metadata": json.loads(row.metadata_json or "{}"),
        }

    def _validate(self, payload: AlertPayload) -> None:
        missing = [
            name
            for name, value in {
                "alert_type": payload.alert_type,
                "module": payload.module,
                "title": payload.title,
                "message": payload.message,
                "suggested_action": payload.suggested_action,
            }.items()
            if not str(value).strip()
        ]
        if missing:
            raise ValueError(f"Alert missing required fields: {', '.join(missing)}")
        if not payload.action_buttons:
            raise ValueError("Alert must include action buttons")
        if payload.category not in ALERT_STYLES:
            raise ValueError(f"Unknown alert category: {payload.category}")

    def _native_notify(self, payload: AlertPayload, notification_id: int) -> None:
        try:
            from plyer import notification

            notification.notify(title=payload.title, message=payload.message, app_name="Nexa", timeout=8)
        except Exception as exc:
            alerts_logger.debug("Desktop notification provider unavailable id=%s error=%s", notification_id, exc)

    def _play_sound(self, sound_path: str, notification_id: int) -> None:
        if not Path(sound_path).exists():
            alerts_logger.error("Sound missing notification_id=%s sound=%s", notification_id, sound_path)
            return
        try:
            import winsound

            winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            alerts_logger.info("Sound Played notification_id=%s sound=%s", notification_id, sound_path)
        except Exception:
            alerts_logger.exception("Sound playback failed notification_id=%s sound=%s", notification_id, sound_path)

    def _speak(self, text: str, notification_id: int) -> None:
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Volume = 100; $s.Rate = 0; "
            f"$s.Speak({json.dumps(text)});"
        )
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
            alerts_logger.info("Voice Played notification_id=%s text=%s", notification_id, text)
        except Exception:
            alerts_logger.exception("Voice playback failed notification_id=%s", notification_id)

    def _event_payload(self, payload: AlertPayload, sound_used: str, voice_text: str) -> dict:
        return {
            "title": payload.title,
            "message": payload.message,
            "suggested_action": payload.suggested_action,
            "action_buttons": payload.action_buttons,
            "severity": payload.severity,
            "priority": payload.priority,
            "category": payload.category,
            "sound_used": sound_used,
            "voice_used": voice_text,
            "metadata": payload.metadata,
        }

    def _event(self, db: Session, notification_id: int, event_type: str, module: str, payload: dict) -> None:
        db.add(AlertEvent(notification_id=notification_id, event_type=event_type, module=module, payload_json=json.dumps(payload, default=str)))

    def _history(self, db: Session, notification_id: int, payload: AlertPayload, event: str) -> None:
        db.add(
            NotificationHistory(
                notification_id=notification_id,
                alert_type=payload.alert_type,
                module=payload.module,
                event=event,
                detail_json=json.dumps(self._event_payload(payload, "", ""), default=str),
            )
        )

    def _history_from_row(self, db: Session, row: Notification, event: str, detail: dict) -> None:
        db.add(
            NotificationHistory(
                notification_id=row.id,
                alert_type=row.alert_type,
                module=row.module,
                event=event,
                detail_json=json.dumps(detail, default=str),
            )
        )


alert_service = AlertService()
