from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import psutil
from sqlalchemy.orm import Session

from backend.database.models import Setting
from backend.database.session import SessionLocal

logger = logging.getLogger("nexa.resource")


@dataclass
class ResourceManagerSettings:
    enabled: bool = True
    power_saving_battery_threshold_percent: int = 30
    thermal_cpu_threshold_celsius: int = 80
    thermal_gpu_threshold_celsius: int = 80
    heavy_cpu_threshold_percent: int = 85
    idle_seconds_for_light_mode: int = 300
    alert_poll_interval_seconds: int = 30
    dashboard_refresh_interval_seconds: int = 30
    website_monitor_interval_seconds: int = 600
    gpu_monitor_interval_seconds: int = 120
    system_monitor_interval_seconds: int = 120
    minimum_interval_seconds: int = 15


@dataclass
class ResourceManagerStatus:
    mode: str = "normal"
    power_saving: bool = False
    thermal_protection: bool = False
    heavy_load: bool = False
    user_idle: bool = False
    battery_percent: int | None = None
    is_charging: bool | None = None
    cpu_percent: float = 0
    ram_mb: float = 0
    process_cpu_percent: float = 0
    process_ram_mb: float = 0
    process_threads: int = 0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    health_score: int = 100
    last_evaluated_at: str | None = None


class ResourceManagerService:
    settings_key = "resource_manager_settings"

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal, poll_interval_seconds: int = 60) -> None:
        self.db_factory = db_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.status = ResourceManagerStatus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._process = psutil.Process(os.getpid())
        self._process.cpu_percent(interval=None)
        self._settings_cache: ResourceManagerSettings | None = None
        self._settings_cache_time = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.evaluate_once()
        self._thread = threading.Thread(target=self._loop, name="nexa-resource-manager", daemon=True)
        self._thread.start()
        logger.info("Resource manager started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("Resource manager stopped")

    def get_settings(self, db: Session | None = None) -> ResourceManagerSettings:
        if db is None and self._settings_cache and time.monotonic() - self._settings_cache_time < 30:
            return self._settings_cache
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(Setting).filter(Setting.key == self.settings_key).one_or_none()
            if not row:
                settings = ResourceManagerSettings()
            else:
                settings = ResourceManagerSettings(**{**asdict(ResourceManagerSettings()), **json.loads(row.value)})
            if owns_db:
                self._settings_cache = settings
                self._settings_cache_time = time.monotonic()
            return settings
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        current = asdict(self.get_settings(db))
        current.update({key: value for key, value in updates.items() if value is not None})
        settings = ResourceManagerSettings(**current)
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
            self._settings_cache = settings
            self._settings_cache_time = time.monotonic()
            return asdict(settings)
        finally:
            if owns_db:
                db.close()

    def get_status(self) -> dict:
        with self._lock:
            return asdict(self.status)

    def interval_for(self, service_name: str, default_seconds: int) -> int:
        settings = self.get_settings()
        status = self.get_status()
        configured = {
            "website_monitor": settings.website_monitor_interval_seconds,
            "gpu_monitor": settings.gpu_monitor_interval_seconds,
            "system_alerts": settings.system_monitor_interval_seconds,
            "dashboard": settings.dashboard_refresh_interval_seconds,
            "alerts": settings.alert_poll_interval_seconds,
        }.get(service_name, default_seconds)
        if service_name == "power_monitor":
            if status.get("is_charging") is True:
                configured = 120
            elif (status.get("battery_percent") or 100) <= 20:
                configured = 15
            else:
                configured = 60
        multiplier = 1
        if status.get("thermal_protection") or status.get("heavy_load"):
            multiplier = max(multiplier, 2)
        if status.get("power_saving") and service_name not in {"power_monitor", "voice_assistant"}:
            multiplier = max(multiplier, 3)
        if status.get("user_idle") and service_name in {"dashboard", "alerts", "website_monitor"}:
            multiplier = max(multiplier, 2)
        return max(settings.minimum_interval_seconds, int(configured * multiplier))

    def should_run_noncritical(self, service_name: str) -> bool:
        status = self.get_status()
        if service_name == "website_monitor" and (status.get("power_saving") or status.get("thermal_protection")):
            return False
        if service_name in {"analytics", "browser_automation", "bulk_file"} and (status.get("power_saving") or status.get("thermal_protection") or status.get("heavy_load")):
            return False
        return True

    def evaluate_once(self) -> dict:
        settings = self.get_settings()
        battery = psutil.sensors_battery()
        cpu = psutil.cpu_percent(interval=0)
        memory = psutil.virtual_memory()
        process_memory = self._process.memory_info().rss / (1024 * 1024)
        process_cpu = self._process.cpu_percent(interval=None)
        io = self._process.io_counters() if hasattr(self._process, "io_counters") else None
        network = psutil.net_io_counters()
        cpu_temp = self._cpu_temperature()
        battery_percent = int(round(battery.percent)) if battery else None
        charging = bool(battery.power_plugged) if battery else None
        power_saving = bool(battery_percent is not None and charging is False and battery_percent <= settings.power_saving_battery_threshold_percent)
        thermal = bool(cpu_temp is not None and cpu_temp >= settings.thermal_cpu_threshold_celsius)
        heavy_load = cpu >= settings.heavy_cpu_threshold_percent
        user_idle = self._idle_seconds() >= settings.idle_seconds_for_light_mode
        mode = "normal"
        if thermal:
            mode = "thermal_protection"
        elif power_saving:
            mode = "power_saving"
        elif heavy_load:
            mode = "load_shedding"
        elif user_idle:
            mode = "light_idle"
        health = max(0, min(100, round(100 - (process_cpu * 2.5) - max(0, process_memory - 80) * 0.4)))
        with self._lock:
            self.status = ResourceManagerStatus(
                mode=mode,
                power_saving=power_saving,
                thermal_protection=thermal,
                heavy_load=heavy_load,
                user_idle=user_idle,
                battery_percent=battery_percent,
                is_charging=charging,
                cpu_percent=round(cpu, 1),
                ram_mb=round(memory.used / (1024 * 1024), 1),
                process_cpu_percent=round(process_cpu, 2),
                process_ram_mb=round(process_memory, 1),
                process_threads=self._process.num_threads(),
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                disk_read_bytes=getattr(io, "read_bytes", 0) if io else 0,
                disk_write_bytes=getattr(io, "write_bytes", 0) if io else 0,
                health_score=health,
                last_evaluated_at=datetime.utcnow().isoformat(),
            )
        return self.get_status()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.evaluate_once()
            except Exception:
                logger.exception("Resource manager evaluation failed")
            self._stop.wait(self.poll_interval_seconds)

    def _cpu_temperature(self) -> float | None:
        if not hasattr(psutil, "sensors_temperatures"):
            return None
        values = [entry.current for entries in psutil.sensors_temperatures().values() for entry in entries if entry.current is not None]
        return round(max(values), 1) if values else None

    def _idle_seconds(self) -> int:
        if os.name != "nt":
            return 0
        try:
            import ctypes

            class LastInputInfo(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            last_input = LastInputInfo()
            last_input.cbSize = ctypes.sizeof(last_input)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input))
            millis = ctypes.windll.kernel32.GetTickCount() - last_input.dwTime
            return max(0, int(millis / 1000))
        except Exception:
            return 0


resource_manager_service = ResourceManagerService()
