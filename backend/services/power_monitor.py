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
from backend.database.models import BatteryEvent, BatteryHealthHistory, BatterySetting, ChargeHistory, PowerEvent
from backend.database.session import SessionLocal
from backend.services.resource_manager import resource_manager_service

logger = logging.getLogger("nexa.battery")


@dataclass
class PowerMonitorSettings:
    enabled: bool = True
    charger_connected_alerts: bool = True
    charger_disconnected_alerts: bool = True
    battery_95_alert_enabled: bool = True
    battery_full_alert_enabled: bool = True
    low_battery_alert_enabled: bool = True
    critical_battery_alert_enabled: bool = True
    fluctuation_detection_enabled: bool = True
    voice_enabled: bool = True
    sound_enabled: bool = True
    notification_enabled: bool = True
    low_battery_threshold_percent: int = 20
    critical_battery_threshold_percent: int = 10
    battery_95_threshold_percent: int = 95
    fluctuation_window_seconds: int = 30
    fluctuation_transition_count: int = 4
    low_repeat_interval_seconds: int = 120
    full_repeat_interval_seconds: int = 3600
    event_sound_volume: int = 35
    warning_sound_volume: int = 80


@dataclass
class PowerSample:
    battery_percent: int | None = None
    is_charging: bool | None = None
    power_source: str = "unknown"
    estimated_remaining_seconds: int | None = None
    battery_temperature_celsius: float | None = None
    full_charge_capacity_mwh: int | None = None
    design_capacity_mwh: int | None = None
    charge_cycles: int | None = None
    adapter_status: str = "unknown"


@dataclass
class PowerMonitorStatus:
    battery_percent: int | None = None
    is_charging: bool | None = None
    charger_connected: bool | None = None
    power_source: str = "unknown"
    adapter_status: str = "unknown"
    battery_health_percent: float | None = None
    battery_wear_percent: float | None = None
    charge_cycles: int | None = None
    full_charge_capacity_mwh: int | None = None
    design_capacity_mwh: int | None = None
    estimated_remaining_seconds: int | None = None
    battery_temperature_celsius: float | None = None
    charging_speed_percent_per_hour: float | None = None
    average_daily_usage_percent: float | None = None
    average_charging_time_seconds: int | None = None
    battery_age_days: int | None = None
    active_charge_session_id: int | None = None
    last_event_type: str | None = None
    last_event_time: str | None = None
    last_full_charge_time: str | None = None
    testing_mode: bool = False


class PowerMonitorService:
    settings_key = "power_monitor_settings"

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal, poll_interval_seconds: int = 60) -> None:
        self.db_factory = db_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.status = PowerMonitorStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._simulation: PowerSample | None = None
        self._last_sample: PowerSample | None = None
        self._last_sample_time: datetime | None = None
        self._last_health_query_time: datetime | None = None
        self._cached_health: dict = {}
        self._transitions: list[datetime] = []
        self._last_alerts: dict[str, datetime] = {}
        self._seen_95_this_charge = False
        self._seen_full_this_charge = False
        self.sound_paths = {
            "connected": Path("assets/sounds/power-connected.wav").resolve(),
            "disconnected": Path("assets/sounds/power-disconnected.wav").resolve(),
            "battery_95": Path("assets/sounds/power-95.wav").resolve(),
            "battery_full": Path("assets/sounds/power-full.wav").resolve(),
            "low_battery": Path("assets/sounds/low-battery-alert.wav").resolve(),
            "critical_battery": Path("assets/sounds/power-critical.wav").resolve(),
            "fluctuation": Path("assets/sounds/power-fluctuation.wav").resolve(),
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nexa-power-monitor", daemon=True)
        self._thread.start()
        logger.info("Power monitor started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("Power monitor stopped")

    def get_settings(self, db: Session | None = None) -> PowerMonitorSettings:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(BatterySetting).filter(BatterySetting.key == self.settings_key).one_or_none()
            if not row:
                return PowerMonitorSettings()
            return PowerMonitorSettings(**{**asdict(PowerMonitorSettings()), **json.loads(row.value_json)})
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        current = asdict(self.get_settings(db))
        current.update({key: value for key, value in updates.items() if value is not None})
        settings = PowerMonitorSettings(**current)
        self._validate_settings(settings)
        owns_db = db is None
        db = db or self.db_factory()
        try:
            value = json.dumps(asdict(settings), default=str)
            row = db.query(BatterySetting).filter(BatterySetting.key == self.settings_key).one_or_none()
            if row:
                row.value_json = value
                row.updated_at = datetime.utcnow()
            else:
                db.add(BatterySetting(key=self.settings_key, value_json=value))
            db.commit()
            return asdict(settings)
        finally:
            if owns_db:
                db.close()

    def get_status(self) -> dict:
        with self._lock:
            return asdict(self.status)

    def history(self, limit: int = 100, query: str | None = None, event_type: str | None = None) -> dict:
        with self.db_factory() as db:
            events = db.query(PowerEvent)
            if query:
                like = f"%{query}%"
                events = events.filter((PowerEvent.title.ilike(like)) | (PowerEvent.message.ilike(like)) | (PowerEvent.event_type.ilike(like)))
            if event_type:
                events = events.filter(PowerEvent.event_type == event_type)
            sessions = db.query(ChargeHistory).order_by(ChargeHistory.started_at.desc()).limit(limit).all()
            health = db.query(BatteryHealthHistory).order_by(BatteryHealthHistory.created_at.desc()).limit(1).first()
            return {
                "events": [self._serialize_power_event(row) for row in events.order_by(PowerEvent.created_at.desc()).limit(limit).all()],
                "charge_sessions": [self._serialize_charge_session(row) for row in sessions],
                "latest_health": self._serialize_health(health) if health else None,
            }

    def export(self) -> dict:
        payload = self.history(limit=1000)
        payload["exported_at"] = datetime.utcnow().isoformat()
        return payload

    def recommendations(self) -> list[dict]:
        with self.db_factory() as db:
            full_events = (
                db.query(PowerEvent)
                .filter(PowerEvent.event_type.in_(["battery_full", "battery_95"]))
                .order_by(PowerEvent.created_at.desc())
                .limit(20)
                .all()
            )
            health = db.query(BatteryHealthHistory).order_by(BatteryHealthHistory.created_at.desc()).first()
        recommendations = []
        if len([row for row in full_events if row.event_type == "battery_full"]) >= 3:
            recommendations.append(
                {
                    "title": "Reduce time at full charge",
                    "message": "You frequently keep your laptop plugged in at 100%. Consider unplugging near 95% to reduce battery wear.",
                    "severity": "medium",
                }
            )
        if health and health.health_percent is not None and health.health_percent <= 85:
            recommendations.append(
                {
                    "title": "Battery health is reduced",
                    "message": f"Battery health is {health.health_percent:.1f}%. Consider enabling battery conservation mode if your device supports it.",
                    "severity": "high",
                }
            )
        return recommendations

    def simulate(self, battery_percent: int | None, is_charging: bool | None) -> dict:
        if battery_percent is not None and not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be between 0 and 100")
        self._simulation = PowerSample(
            battery_percent=battery_percent,
            is_charging=is_charging,
            power_source="AC Power" if is_charging else "Battery",
            estimated_remaining_seconds=7200 if not is_charging else None,
            adapter_status="connected" if is_charging else "disconnected",
        )
        with self._lock:
            self.status.testing_mode = True
        self.evaluate_once()
        return self.get_status()

    def clear_simulation(self) -> dict:
        self._simulation = None
        with self._lock:
            self.status.testing_mode = False
        self.evaluate_once()
        return self.get_status()

    def evaluate_once(self) -> dict:
        settings = self.get_settings()
        sample = self._read_power_sample()
        now = datetime.utcnow()
        previous = self._last_sample
        speed = self._charging_speed(sample, now)
        health_percent, wear_percent = self._health(sample)
        active_session_id = self._track_charge_session(previous, sample, now, speed)
        self._record_health_snapshot(sample, health_percent, wear_percent)
        usage, avg_charge = self._usage_stats()
        self._update_status(sample, health_percent, wear_percent, speed, active_session_id, usage, avg_charge)
        if settings.enabled:
            self._evaluate_events(settings, previous, sample, now)
        self._last_sample = sample
        self._last_sample_time = now
        return self.get_status()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.evaluate_once()
            except Exception:
                logger.exception("Power monitor evaluation failed")
            self._stop.wait(resource_manager_service.interval_for("power_monitor", self.poll_interval_seconds))

    def _read_power_sample(self) -> PowerSample:
        if self._simulation is not None:
            return self._simulation
        battery = psutil.sensors_battery()
        percent = int(round(battery.percent)) if battery else None
        charging = bool(battery.power_plugged) if battery else None
        seconds_left = None
        if battery and battery.secsleft not in {psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED}:
            seconds_left = int(battery.secsleft)
        health = self._read_cached_windows_battery_health()
        return PowerSample(
            battery_percent=percent,
            is_charging=charging,
            power_source="AC Power" if charging else "Battery" if charging is False else "unknown",
            estimated_remaining_seconds=seconds_left,
            adapter_status="connected" if charging else "disconnected" if charging is False else "unknown",
            **health,
        )

    def _read_cached_windows_battery_health(self) -> dict:
        if self._last_health_query_time and datetime.utcnow() - self._last_health_query_time < timedelta(minutes=30):
            return self._cached_health
        self._cached_health = self._read_windows_battery_health()
        self._last_health_query_time = datetime.utcnow()
        return self._cached_health

    def _read_windows_battery_health(self) -> dict:
        script = r"""
$battery = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
$static = Get-CimInstance -Namespace root\wmi -ClassName BatteryStaticData -ErrorAction SilentlyContinue | Select-Object -First 1
$full = Get-CimInstance -Namespace root\wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue | Select-Object -First 1
$cycle = Get-CimInstance -Namespace root\wmi -ClassName BatteryCycleCount -ErrorAction SilentlyContinue | Select-Object -First 1
[pscustomobject]@{
  DesignCapacity = $static.DesignedCapacity
  FullChargeCapacity = $full.FullChargedCapacity
  CycleCount = $cycle.CycleCount
  Temperature = $battery.Temperature
} | ConvertTo-Json -Compress
"""
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=4, shell=False)
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            data = json.loads(result.stdout)
            temperature = self._float_or_none(data.get("Temperature"))
            if temperature and temperature > 200:
                temperature = round((temperature / 10) - 273.15, 1)
            return {
                "design_capacity_mwh": self._int_or_none(data.get("DesignCapacity")),
                "full_charge_capacity_mwh": self._int_or_none(data.get("FullChargeCapacity")),
                "charge_cycles": self._int_or_none(data.get("CycleCount")),
                "battery_temperature_celsius": temperature,
            }
        except Exception:
            logger.debug("Windows battery health query failed", exc_info=True)
            return {}

    def _evaluate_events(self, settings: PowerMonitorSettings, previous: PowerSample | None, sample: PowerSample, now: datetime) -> None:
        if previous and previous.is_charging is not None and sample.is_charging is not None and previous.is_charging != sample.is_charging:
            if sample.is_charging and settings.charger_connected_alerts:
                self._send_event(settings, "charger_connected", sample, "Nexa Power Monitor", "Charger Connected\nLaptop is now charging.", "Open Battery Details", ["Open Battery Details", "Dismiss"], "info", "Charger connected. Laptop is now charging.", "connected")
                self._seen_95_this_charge = False
                self._seen_full_this_charge = False
            elif not sample.is_charging and settings.charger_disconnected_alerts:
                self._send_event(settings, "charger_disconnected", sample, "Nexa Power Monitor", "Charger Disconnected\nLaptop is now running on battery power.", "Open Battery Details", ["Open Battery Details", "Dismiss"], "info", "Charger disconnected. Laptop is now running on battery power.", "disconnected")
                self._seen_95_this_charge = False
                self._seen_full_this_charge = False
            self._transitions.append(now)
            self._check_fluctuation(settings, sample, now)

        if sample.is_charging:
            if settings.battery_95_alert_enabled and not self._seen_95_this_charge and sample.battery_percent is not None and sample.battery_percent >= settings.battery_95_threshold_percent:
                self._send_event(settings, "battery_95", sample, "Battery Reached 95%", "Charging may be stopped to preserve battery health.", "Open Battery Details", ["Dismiss", "Open Battery Details"], "success", "Battery reached 95 percent.", "battery_95")
                self._seen_95_this_charge = True
            if settings.battery_full_alert_enabled and not self._seen_full_this_charge and sample.battery_percent == 100:
                self._send_event(settings, "battery_full", sample, "Battery Fully Charged", "Battery has reached full charge.\nYou may unplug the charger.", "Open Battery Details", ["Dismiss", "Open Battery Details"], "success", "Battery fully charged.", "battery_full")
                self._seen_full_this_charge = True
                with self._lock:
                    self.status.last_full_charge_time = datetime.utcnow().isoformat()

        if sample.is_charging is False and sample.battery_percent is not None:
            if settings.critical_battery_alert_enabled and sample.battery_percent <= settings.critical_battery_threshold_percent:
                self._send_repeating_event(settings, "critical_battery", sample, settings.low_repeat_interval_seconds, "Critical Battery Alert", "Critical battery level detected.\nConnect charger immediately.", "Connect charger immediately.", ["Open Battery Details", "Dismiss"], "critical", "Critical battery level detected. Connect charger immediately.", "critical_battery")
            elif settings.low_battery_alert_enabled and sample.battery_percent <= settings.low_battery_threshold_percent:
                self._send_repeating_event(settings, "low_battery", sample, settings.low_repeat_interval_seconds, "Nexa Battery Alert", "Battery level is low.\nPlease connect your charger.", "Connect your charger.", ["Open Battery Details", "Dismiss", "Snooze 10 Minutes"], "warning", "Battery level is low. Please connect your charger.", "low_battery")

    def _check_fluctuation(self, settings: PowerMonitorSettings, sample: PowerSample, now: datetime) -> None:
        if not settings.fluctuation_detection_enabled:
            return
        cutoff = now - timedelta(seconds=settings.fluctuation_window_seconds)
        self._transitions = [item for item in self._transitions if item >= cutoff]
        if len(self._transitions) >= settings.fluctuation_transition_count:
            self._send_repeating_event(settings, "power_fluctuation", sample, settings.fluctuation_window_seconds, "Power Connection Unstable", "The charger connection appears unstable.\nPlease check charger cable, adapter, and power outlet.", "Check charger cable, adapter, and power outlet.", ["Open Battery Details", "Dismiss"], "warning", "Power connection appears unstable.", "fluctuation")
            self._transitions.clear()

    def _send_repeating_event(self, settings: PowerMonitorSettings, event_type: str, sample: PowerSample, interval_seconds: int, title: str, message: str, suggested_action: str, buttons: list[str], category: str, voice: str, sound_key: str) -> None:
        now = datetime.utcnow()
        last = self._last_alerts.get(event_type)
        if last and now - last < timedelta(seconds=interval_seconds):
            return
        self._send_event(settings, event_type, sample, title, message, suggested_action, buttons, category, voice, sound_key)

    def _send_event(self, settings: PowerMonitorSettings, event_type: str, sample: PowerSample, title: str, message: str, suggested_action: str, buttons: list[str], category: str, voice: str, sound_key: str) -> None:
        timestamp = datetime.utcnow()
        battery_line = f"\nBattery: {sample.battery_percent}%" if sample.battery_percent is not None else ""
        time_line = f"\nTime: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        full_message = f"{message}{battery_line}{time_line}"
        severity = "critical" if category == "critical" else "high" if category == "warning" else "medium"
        with self.db_factory() as db:
            event = PowerEvent(
                event_type=event_type,
                title=title,
                message=full_message,
                battery_percent=sample.battery_percent,
                power_source=sample.power_source,
                detail_json=json.dumps(asdict(sample), default=str),
                created_at=timestamp,
            )
            db.add(event)
            db.add(BatteryEvent(event_type=event_type, battery_percent=sample.battery_percent, is_charging=sample.is_charging, power_source=sample.power_source, detail_json=json.dumps(asdict(sample), default=str), created_at=timestamp))
            result = NotificationAgent(db).notify(
                title,
                full_message,
                alert_type=event_type,
                module="power_monitor",
                severity=severity,
                priority=severity,
                category=category,
                suggested_action=suggested_action,
                action_buttons=buttons,
                voice_message=voice,
                sound_path=str(self.sound_paths[sound_key]),
                sound_enabled=settings.sound_enabled,
                voice_enabled=settings.voice_enabled,
                notification_enabled=settings.notification_enabled,
                metadata={"power_event": event_type, "battery_percent": sample.battery_percent, "power_source": sample.power_source, "sound_volume": settings.warning_sound_volume if category in {"warning", "critical"} else settings.event_sound_volume},
            )
            db.commit()
        self._last_alerts[event_type] = timestamp
        with self._lock:
            self.status.last_event_type = event_type
            self.status.last_event_time = timestamp.isoformat()
        logger.info("Power Event event=%s notification_id=%s battery=%s charging=%s source=%s", event_type, result.get("id"), sample.battery_percent, sample.is_charging, sample.power_source)

    def _track_charge_session(self, previous: PowerSample | None, sample: PowerSample, now: datetime, speed: float | None) -> int | None:
        with self.db_factory() as db:
            active = db.query(ChargeHistory).filter(ChargeHistory.status == "active").order_by(ChargeHistory.started_at.desc()).first()
            if sample.is_charging and not active:
                active = ChargeHistory(started_at=now, start_percent=sample.battery_percent, power_source=sample.power_source, detail_json=json.dumps({"charging_speed_percent_per_hour": speed}, default=str))
                db.add(active)
                db.commit()
                db.refresh(active)
                logger.info("Charging Started session_id=%s battery=%s", active.id, sample.battery_percent)
            elif active and sample.is_charging is False:
                active.ended_at = now
                active.end_percent = sample.battery_percent
                active.duration_seconds = max(0, int((now - active.started_at).total_seconds()))
                if active.start_percent is not None and active.end_percent is not None:
                    active.charge_added_percent = max(0, active.end_percent - active.start_percent)
                active.status = "completed"
                active.detail_json = json.dumps({"charging_speed_percent_per_hour": speed}, default=str)
                db.commit()
                logger.info("Charging Stopped session_id=%s battery=%s duration=%s", active.id, sample.battery_percent, active.duration_seconds)
                return None
            return active.id if active and sample.is_charging else None

    def _record_health_snapshot(self, sample: PowerSample, health_percent: float | None, wear_percent: float | None) -> None:
        with self.db_factory() as db:
            latest = db.query(BatteryHealthHistory).order_by(BatteryHealthHistory.created_at.desc()).first()
            if latest and (datetime.utcnow() - latest.created_at).total_seconds() < 300:
                return
            db.add(
                BatteryHealthHistory(
                    battery_percent=sample.battery_percent,
                    health_percent=health_percent,
                    wear_percent=wear_percent,
                    charge_cycles=sample.charge_cycles,
                    full_charge_capacity_mwh=sample.full_charge_capacity_mwh,
                    design_capacity_mwh=sample.design_capacity_mwh,
                    battery_temperature_celsius=sample.battery_temperature_celsius,
                    estimated_remaining_seconds=sample.estimated_remaining_seconds,
                    detail_json=json.dumps(asdict(sample), default=str),
                )
            )
            db.commit()

    def _usage_stats(self) -> tuple[float | None, int | None]:
        with self.db_factory() as db:
            sessions = db.query(ChargeHistory).filter(ChargeHistory.status == "completed", ChargeHistory.duration_seconds > 0).order_by(ChargeHistory.started_at.desc()).limit(20).all()
            avg_charge = int(sum(row.duration_seconds for row in sessions) / len(sessions)) if sessions else None
            events = db.query(BatteryEvent).order_by(BatteryEvent.created_at.desc()).limit(200).all()
        by_day: dict[str, list[int]] = {}
        for event in events:
            if event.battery_percent is None:
                continue
            by_day.setdefault(event.created_at.date().isoformat(), []).append(event.battery_percent)
        daily_usage = [max(values) - min(values) for values in by_day.values() if len(values) >= 2]
        avg_usage = round(sum(daily_usage) / len(daily_usage), 1) if daily_usage else None
        return avg_usage, avg_charge

    def _update_status(self, sample: PowerSample, health_percent: float | None, wear_percent: float | None, speed: float | None, active_session_id: int | None, average_daily_usage_percent: float | None, average_charging_time_seconds: int | None) -> None:
        with self._lock:
            self.status.battery_percent = sample.battery_percent
            self.status.is_charging = sample.is_charging
            self.status.charger_connected = sample.is_charging
            self.status.power_source = sample.power_source
            self.status.adapter_status = sample.adapter_status
            self.status.battery_health_percent = health_percent
            self.status.battery_wear_percent = wear_percent
            self.status.charge_cycles = sample.charge_cycles
            self.status.full_charge_capacity_mwh = sample.full_charge_capacity_mwh
            self.status.design_capacity_mwh = sample.design_capacity_mwh
            self.status.estimated_remaining_seconds = sample.estimated_remaining_seconds
            self.status.battery_temperature_celsius = sample.battery_temperature_celsius
            self.status.charging_speed_percent_per_hour = speed
            self.status.average_daily_usage_percent = average_daily_usage_percent
            self.status.average_charging_time_seconds = average_charging_time_seconds
            self.status.active_charge_session_id = active_session_id

    def _charging_speed(self, sample: PowerSample, now: datetime) -> float | None:
        if not self._last_sample or not self._last_sample_time:
            return None
        if not sample.is_charging or sample.battery_percent is None or self._last_sample.battery_percent is None:
            return None
        elapsed_hours = (now - self._last_sample_time).total_seconds() / 3600
        if elapsed_hours <= 0:
            return None
        return round((sample.battery_percent - self._last_sample.battery_percent) / elapsed_hours, 2)

    def _health(self, sample: PowerSample) -> tuple[float | None, float | None]:
        if sample.full_charge_capacity_mwh and sample.design_capacity_mwh:
            health = round((sample.full_charge_capacity_mwh / sample.design_capacity_mwh) * 100, 1)
            return health, round(max(0, 100 - health), 1)
        return None, None

    def _serialize_power_event(self, row: PowerEvent) -> dict:
        return {
            "id": row.id,
            "event_type": row.event_type,
            "title": row.title,
            "message": row.message,
            "battery_percent": row.battery_percent,
            "power_source": row.power_source,
            "location": row.location,
            "detail": json.loads(row.detail_json or "{}"),
            "created_at": row.created_at.isoformat(),
        }

    def _serialize_charge_session(self, row: ChargeHistory) -> dict:
        return {
            "id": row.id,
            "started_at": row.started_at.isoformat(),
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            "start_percent": row.start_percent,
            "end_percent": row.end_percent,
            "duration_seconds": row.duration_seconds,
            "charge_added_percent": row.charge_added_percent,
            "power_source": row.power_source,
            "location": row.location,
            "status": row.status,
            "detail": json.loads(row.detail_json or "{}"),
        }

    def _serialize_health(self, row: BatteryHealthHistory) -> dict:
        return {
            "id": row.id,
            "battery_percent": row.battery_percent,
            "health_percent": row.health_percent,
            "wear_percent": row.wear_percent,
            "charge_cycles": row.charge_cycles,
            "full_charge_capacity_mwh": row.full_charge_capacity_mwh,
            "design_capacity_mwh": row.design_capacity_mwh,
            "battery_temperature_celsius": row.battery_temperature_celsius,
            "estimated_remaining_seconds": row.estimated_remaining_seconds,
            "created_at": row.created_at.isoformat(),
        }

    def _validate_settings(self, settings: PowerMonitorSettings) -> None:
        if not 1 <= settings.low_battery_threshold_percent <= 100:
            raise ValueError("low_battery_threshold_percent must be between 1 and 100")
        if not 1 <= settings.critical_battery_threshold_percent <= settings.low_battery_threshold_percent:
            raise ValueError("critical threshold must be between 1 and low threshold")
        if not 50 <= settings.battery_95_threshold_percent <= 100:
            raise ValueError("battery_95_threshold_percent must be between 50 and 100")
        if settings.low_repeat_interval_seconds < 30:
            raise ValueError("low_repeat_interval_seconds must be at least 30")

    def _float_or_none(self, value) -> float | None:
        try:
            if value is None or value == "":
                return None
            return round(float(value), 1)
        except (TypeError, ValueError):
            return None

    def _int_or_none(self, value) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None


power_monitor_service = PowerMonitorService()
