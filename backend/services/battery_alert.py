from __future__ import annotations

import json
import logging
import subprocess
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

logger = logging.getLogger("nexa.battery")


@dataclass
class BatteryAlertSettings:
    enabled: bool = True
    threshold_percent: int = 20
    voice_enabled: bool = True
    sound_enabled: bool = True
    notification_enabled: bool = True
    repeat_interval_seconds: int = 120


@dataclass
class BatteryAlertStatus:
    battery_percent: int | None = None
    is_charging: bool | None = None
    alert_active: bool = False
    last_alert_time: str | None = None
    last_stop_time: str | None = None
    testing_mode: bool = False


class BatteryAlertService:
    settings_key = "battery_alert_settings"

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal, poll_interval_seconds: int = 30) -> None:
        self.db_factory = db_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.status = BatteryAlertStatus()
        self._simulation: tuple[int | None, bool | None] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.sound_path = Path("assets/sounds/low-battery-alert.wav").resolve()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nexa-battery-alert", daemon=True)
        self._thread.start()
        logger.info("Battery alert monitor started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("Battery alert monitor stopped")

    def get_settings(self, db: Session | None = None) -> BatteryAlertSettings:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(Setting).filter(Setting.key == self.settings_key).one_or_none()
            if not row:
                return BatteryAlertSettings()
            data = json.loads(row.value)
            return BatteryAlertSettings(**{**asdict(BatteryAlertSettings()), **data})
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        current = asdict(self.get_settings(db))
        current.update({key: value for key, value in updates.items() if value is not None})
        settings = BatteryAlertSettings(**current)
        self._validate_settings(settings)
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

    def get_status(self) -> dict:
        with self._lock:
            return asdict(self.status)

    def simulate(self, battery_percent: int | None, is_charging: bool | None) -> dict:
        if battery_percent is not None and not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be between 0 and 100")
        self._simulation = (battery_percent, is_charging)
        self.status.testing_mode = True
        self.evaluate_once()
        return self.get_status()

    def clear_simulation(self) -> dict:
        self._simulation = None
        self.status.testing_mode = False
        self.evaluate_once()
        return self.get_status()

    def evaluate_once(self) -> dict:
        settings = self.get_settings()
        percent, charging = self._read_battery()
        now = datetime.utcnow()
        should_alert = bool(settings.enabled and percent is not None and charging is False and percent <= settings.threshold_percent)

        with self._lock:
            self.status.battery_percent = percent
            self.status.is_charging = charging

        if not should_alert:
            self._stop_alert_if_needed(percent, charging)
            return self.get_status()

        last_alert = self._last_alert_datetime()
        if last_alert is None or now - last_alert >= timedelta(seconds=settings.repeat_interval_seconds):
            self._trigger_alert(settings, percent, charging)
        return self.get_status()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.evaluate_once()
            except Exception:
                logger.exception("Battery alert monitor evaluation failed")
            self._stop.wait(self.poll_interval_seconds)

    def _read_battery(self) -> tuple[int | None, bool | None]:
        if self._simulation is not None:
            return self._simulation
        battery = psutil.sensors_battery()
        if not battery:
            return None, None
        return int(round(battery.percent)), bool(battery.power_plugged)

    def _trigger_alert(self, settings: BatteryAlertSettings, percent: int, charging: bool | None) -> None:
        message = f"Battery level has dropped to {percent}%.\nPlease connect your charger."
        if settings.notification_enabled:
            with self.db_factory() as db:
                NotificationAgent(db).notify(
                    "Nexa Battery Alert",
                    message,
                    alert_type="battery",
                    module="battery_alert",
                    severity="high" if percent <= 10 else "medium",
                    priority="high" if percent <= 10 else "medium",
                    category="warning",
                    suggested_action="Connect your charger.",
                    action_buttons=["Open Battery Details", "Dismiss", "Snooze 10 Minutes"],
                    voice_message="Battery level is low. Please connect your charger.",
                    sound_enabled=False,
                    voice_enabled=False,
                    metadata={"battery_percent": percent, "is_charging": charging, "threshold_percent": settings.threshold_percent},
                )
        if settings.sound_enabled:
            self._play_sound()
        if settings.voice_enabled:
            self._speak(percent)
        timestamp = datetime.utcnow().isoformat()
        with self._lock:
            self.status.alert_active = True
            self.status.last_alert_time = timestamp
        logger.warning("Alert Triggered battery_percent=%s charging=%s timestamp=%s", percent, charging, timestamp)

    def _stop_alert_if_needed(self, percent: int | None, charging: bool | None) -> None:
        with self._lock:
            was_active = self.status.alert_active
            self.status.alert_active = False
            if was_active:
                self.status.last_stop_time = datetime.utcnow().isoformat()
        if was_active:
            logger.info("Alert Stopped battery_percent=%s charging=%s timestamp=%s", percent, charging, self.status.last_stop_time)

    def _last_alert_datetime(self) -> datetime | None:
        with self._lock:
            value = self.status.last_alert_time
        return datetime.fromisoformat(value) if value else None

    def _play_sound(self) -> None:
        if not self.sound_path.exists():
            logger.error("Battery alert sound missing: %s", self.sound_path)
            return
        try:
            import winsound

            winsound.PlaySound(str(self.sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            logging.getLogger("nexa.alerts").info("Sound Played module=battery_alert sound=%s reason=low_battery", self.sound_path)
        except Exception:
            logger.exception("Battery alert sound playback failed")

    def _speak(self, percent: int) -> None:
        spoken = self._percent_to_words(percent)
        text = f"Warning. Only {spoken} percent battery left. Please charge your laptop now."
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
            logging.getLogger("nexa.alerts").info("Voice Played module=battery_alert text=%s", text)
        except Exception:
            logger.exception("Battery alert voice playback failed")

    def _percent_to_words(self, percent: int) -> str:
        words = {
            10: "ten",
            15: "fifteen",
            20: "twenty",
            25: "twenty five",
            30: "thirty",
        }
        return words.get(percent, str(percent))

    def _validate_settings(self, settings: BatteryAlertSettings) -> None:
        if not 1 <= settings.threshold_percent <= 100:
            raise ValueError("threshold_percent must be between 1 and 100")
        if settings.repeat_interval_seconds < 30:
            raise ValueError("repeat_interval_seconds must be at least 30")


battery_alert_service = BatteryAlertService()
