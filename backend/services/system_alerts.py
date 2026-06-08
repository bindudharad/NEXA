from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import psutil
from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.database.models import Setting
from backend.database.session import SessionLocal
from backend.services.resource_manager import resource_manager_service

logger = logging.getLogger("nexa.system-alerts")


@dataclass
class SystemAlertSettings:
    enabled: bool = True
    cpu_temperature_threshold_celsius: int = 80
    cpu_usage_threshold_percent: int = 90
    memory_threshold_percent: int = 90
    storage_threshold_percent: int = 95
    notification_enabled: bool = True
    sound_enabled: bool = True
    voice_enabled: bool = False
    repeat_interval_seconds: int = 600


class SystemAlertService:
    settings_key = "system_alert_settings"

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal, poll_interval_seconds: int = 120) -> None:
        self.db_factory = db_factory
        self.poll_interval_seconds = poll_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_alerts: dict[str, datetime] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nexa-system-alerts", daemon=True)
        self._thread.start()
        logger.info("System alert monitor started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("System alert monitor stopped")

    def get_settings(self, db: Session | None = None) -> SystemAlertSettings:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(Setting).filter(Setting.key == self.settings_key).one_or_none()
            if not row:
                return SystemAlertSettings()
            return SystemAlertSettings(**{**asdict(SystemAlertSettings()), **json.loads(row.value)})
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        current = asdict(self.get_settings(db))
        current.update({key: value for key, value in updates.items() if value is not None})
        settings = SystemAlertSettings(**current)
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(Setting).filter(Setting.key == self.settings_key).one_or_none()
            value = json.dumps(asdict(settings))
            if row:
                row.value = value
                row.updated_at = datetime.utcnow()
            else:
                db.add(Setting(key=self.settings_key, value=value))
            db.commit()
            return asdict(settings)
        finally:
            if owns_db:
                db.close()

    def evaluate_once(self) -> list[dict]:
        settings = self.get_settings()
        if not settings.enabled:
            return []
        alerts: list[dict] = []
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage(str(Path.home().anchor or Path.cwd()))
        cpu_temp = self._cpu_temperature()
        if cpu_temp is not None and cpu_temp > settings.cpu_temperature_threshold_celsius:
            alerts.append(self._send("cpu_temperature", settings, cpu_temp, settings.cpu_temperature_threshold_celsius))
        if cpu > settings.cpu_usage_threshold_percent:
            alerts.append(self._send("cpu_usage", settings, cpu, settings.cpu_usage_threshold_percent))
        if memory > settings.memory_threshold_percent:
            alerts.append(self._send("memory", settings, memory, settings.memory_threshold_percent))
        if disk.percent > settings.storage_threshold_percent:
            alerts.append(self._send("storage", settings, disk.percent, settings.storage_threshold_percent, drive=str(Path.home().anchor or Path.cwd())))
        return [alert for alert in alerts if alert]

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.evaluate_once()
            except Exception:
                logger.exception("System alert evaluation failed")
            self._stop.wait(resource_manager_service.interval_for("system_alerts", self.poll_interval_seconds))

    def _send(self, alert_type: str, settings: SystemAlertSettings, value: float, threshold: int, drive: str = "") -> dict | None:
        now = datetime.utcnow()
        last = self._last_alerts.get(alert_type)
        if last and now - last < timedelta(seconds=settings.repeat_interval_seconds):
            return None
        definitions = {
            "cpu_temperature": ("Nexa CPU Alert", f"CPU temperature is {value:.1f}°C.\nThis exceeds your configured limit of {threshold}°C.", "Open System Monitor", ["Open System Monitor", "Dismiss"], "critical"),
            "cpu_usage": ("Nexa CPU Alert", f"CPU usage has reached {value:.1f}%.\nSystem performance may be affected.", "Open System Monitor", ["Open System Monitor", "Dismiss"], "warning"),
            "memory": ("Nexa Memory Alert", f"Memory usage has reached {value:.1f}%.\nSystem performance may be affected.", "Open Task Manager", ["Open Task Manager", "Dismiss"], "warning"),
            "storage": ("Nexa Storage Alert", f"Drive {drive or 'system'} has reached {value:.1f}% capacity.\nFree space is recommended.", "Open Cleanup", ["Open Cleanup", "Dismiss"], "warning"),
        }
        title, message, suggested_action, buttons, category = definitions[alert_type]
        with self.db_factory() as db:
            result = NotificationAgent(db).notify(
                title,
                message,
                alert_type=alert_type,
                module="system_alerts",
                severity="critical" if category == "critical" else "high",
                priority="high",
                category=category,
                suggested_action=suggested_action,
                action_buttons=buttons,
                voice_message=message.split("\n", 1)[0],
                sound_enabled=settings.sound_enabled,
                voice_enabled=settings.voice_enabled,
                notification_enabled=settings.notification_enabled,
                metadata={"value": value, "threshold": threshold, "drive": drive},
            )
        self._last_alerts[alert_type] = now
        return result

    def _cpu_temperature(self) -> float | None:
        if not hasattr(psutil, "sensors_temperatures"):
            return None
        temperatures = psutil.sensors_temperatures()
        values = [entry.current for entries in temperatures.values() for entry in entries if entry.current is not None]
        return round(max(values), 1) if values else None


system_alert_service = SystemAlertService()
