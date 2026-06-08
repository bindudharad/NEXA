from __future__ import annotations

import csv
import json
import logging
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.database.models import Setting
from backend.database.session import SessionLocal
from backend.services.resource_manager import resource_manager_service

logger = logging.getLogger("nexa.gpu")


@dataclass
class GpuMonitorSettings:
    enabled: bool = True
    threshold_celsius: int = 50
    sound_enabled: bool = True
    voice_enabled: bool = True
    notification_enabled: bool = True
    repeat_interval_seconds: int = 300


@dataclass
class GpuMonitorStatus:
    gpu_name: str | None = None
    temperature_celsius: float | None = None
    usage_percent: float | None = None
    memory_usage_percent: float | None = None
    memory_used_mb: int | None = None
    memory_total_mb: int | None = None
    health_status: str = "Unknown"
    alert_active: bool = False
    last_alert_time: str | None = None
    last_stop_time: str | None = None
    testing_mode: bool = False
    source: str | None = None


@dataclass
class GpuSample:
    gpu_name: str | None = None
    temperature_celsius: float | None = None
    usage_percent: float | None = None
    memory_usage_percent: float | None = None
    memory_used_mb: int | None = None
    memory_total_mb: int | None = None
    source: str | None = None


class GpuMonitorService:
    settings_key = "gpu_monitor_settings"

    def __init__(self, db_factory: Callable[[], Session] = SessionLocal, poll_interval_seconds: int = 120) -> None:
        self.db_factory = db_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.status = GpuMonitorStatus()
        self._simulation: GpuSample | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.sound_path = Path("assets/sounds/nexa-critical.wav").resolve()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nexa-gpu-monitor", daemon=True)
        self._thread.start()
        logger.info("GPU monitor started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("GPU monitor stopped")

    def get_settings(self, db: Session | None = None) -> GpuMonitorSettings:
        owns_db = db is None
        db = db or self.db_factory()
        try:
            row = db.query(Setting).filter(Setting.key == self.settings_key).one_or_none()
            if not row:
                return GpuMonitorSettings()
            data = json.loads(row.value)
            return GpuMonitorSettings(**{**asdict(GpuMonitorSettings()), **data})
        finally:
            if owns_db:
                db.close()

    def update_settings(self, updates: dict, db: Session | None = None) -> dict:
        current = asdict(self.get_settings(db))
        current.update({key: value for key, value in updates.items() if value is not None})
        settings = GpuMonitorSettings(**current)
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

    def simulate(self, temperature_celsius: float, usage_percent: float | None = None, memory_usage_percent: float | None = None) -> dict:
        self._simulation = GpuSample(
            gpu_name="Simulated GPU",
            temperature_celsius=temperature_celsius,
            usage_percent=usage_percent if usage_percent is not None else 72,
            memory_usage_percent=memory_usage_percent if memory_usage_percent is not None else 48,
            memory_used_mb=4096,
            memory_total_mb=8192,
            source="simulation",
        )
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
        sample = self._read_gpu()
        now = datetime.utcnow()
        should_alert = bool(settings.enabled and sample.temperature_celsius is not None and sample.temperature_celsius > settings.threshold_celsius)

        with self._lock:
            self.status.gpu_name = sample.gpu_name
            self.status.temperature_celsius = sample.temperature_celsius
            self.status.usage_percent = sample.usage_percent
            self.status.memory_usage_percent = sample.memory_usage_percent
            self.status.memory_used_mb = sample.memory_used_mb
            self.status.memory_total_mb = sample.memory_total_mb
            self.status.source = sample.source
            self.status.health_status = self._health(sample.temperature_celsius, settings.threshold_celsius)

        if not should_alert:
            self._stop_alert_if_needed(sample)
            return self.get_status()

        last_alert = self._last_alert_datetime()
        if last_alert is None or now - last_alert >= timedelta(seconds=settings.repeat_interval_seconds):
            self._trigger_alert(settings, sample)
        return self.get_status()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.evaluate_once()
            except Exception:
                logger.exception("GPU monitor evaluation failed")
            self._stop.wait(resource_manager_service.interval_for("gpu_monitor", self.poll_interval_seconds))

    def _read_gpu(self) -> GpuSample:
        if self._simulation is not None:
            return self._simulation
        for reader in (self._read_nvidia_smi, self._read_hardware_monitor, self._read_windows_gpu):
            try:
                sample = reader()
                if sample.gpu_name or sample.temperature_celsius is not None or sample.usage_percent is not None:
                    return sample
            except Exception:
                logger.debug("GPU reader failed: %s", reader.__name__, exc_info=True)
        return GpuSample(source="unavailable")

    def _read_nvidia_smi(self) -> GpuSample:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            shell=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return GpuSample()
        row = next(csv.reader(StringIO(result.stdout.strip())))
        name, temp, usage, mem_usage, mem_used, mem_total = [item.strip() for item in row[:6]]
        return GpuSample(
            gpu_name=name,
            temperature_celsius=self._float_or_none(temp),
            usage_percent=self._float_or_none(usage),
            memory_usage_percent=self._float_or_none(mem_usage),
            memory_used_mb=self._int_or_none(mem_used),
            memory_total_mb=self._int_or_none(mem_total),
            source="nvidia-smi",
        )

    def _read_hardware_monitor(self) -> GpuSample:
        script = r"""
$namespaces = @('root\LibreHardwareMonitor','root\OpenHardwareMonitor')
foreach ($namespace in $namespaces) {
  try {
    $sensors = Get-CimInstance -Namespace $namespace -ClassName Sensor -ErrorAction Stop
    $gpuSensors = $sensors | Where-Object { $_.Identifier -like '*gpu*' -or $_.Name -like '*GPU*' }
    if ($gpuSensors) {
      $temp = $gpuSensors | Where-Object { $_.SensorType -eq 'Temperature' } | Select-Object -First 1
      $load = $gpuSensors | Where-Object { $_.SensorType -eq 'Load' -and ($_.Name -like '*Core*' -or $_.Name -like '*GPU*') } | Select-Object -First 1
      $mem = $gpuSensors | Where-Object { $_.SensorType -eq 'Load' -and $_.Name -like '*Memory*' } | Select-Object -First 1
      [pscustomobject]@{
        Name = if ($temp.Parent) { $temp.Parent } else { 'GPU' }
        Temperature = $temp.Value
        Usage = $load.Value
        MemoryUsage = $mem.Value
        Source = $namespace
      } | ConvertTo-Json -Compress
      exit 0
    }
  } catch {}
}
exit 1
"""
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=5, shell=False)
        if result.returncode != 0 or not result.stdout.strip():
            return GpuSample()
        data = json.loads(result.stdout)
        return GpuSample(
            gpu_name=data.get("Name") or "GPU",
            temperature_celsius=self._float_or_none(data.get("Temperature")),
            usage_percent=self._float_or_none(data.get("Usage")),
            memory_usage_percent=self._float_or_none(data.get("MemoryUsage")),
            source=data.get("Source"),
        )

    def _read_windows_gpu(self) -> GpuSample:
        script = r"""
$gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1 Name,AdapterRAM
$usage = $null
try {
  $counters = (Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop).CounterSamples
  $usage = [math]::Round(($counters | Measure-Object CookedValue -Sum).Sum, 1)
  if ($usage -gt 100) { $usage = 100 }
} catch {}
[pscustomobject]@{
  Name = $gpu.Name
  AdapterRAM = $gpu.AdapterRAM
  Usage = $usage
} | ConvertTo-Json -Compress
"""
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=5, shell=False)
        if result.returncode != 0 or not result.stdout.strip():
            return GpuSample()
        data = json.loads(result.stdout)
        total_mb = None
        if data.get("AdapterRAM"):
            total_mb = int(data["AdapterRAM"]) // (1024 * 1024)
        return GpuSample(gpu_name=data.get("Name"), usage_percent=self._float_or_none(data.get("Usage")), memory_total_mb=total_mb, source="windows")

    def _trigger_alert(self, settings: GpuMonitorSettings, sample: GpuSample) -> None:
        message = f"GPU Temperature is {sample.temperature_celsius}°C.\nThis exceeds your configured limit of {settings.threshold_celsius}°C."
        if settings.notification_enabled:
            with self.db_factory() as db:
                NotificationAgent(db).notify(
                    "Nexa GPU Alert",
                    message,
                    alert_type="gpu",
                    module="gpu_monitor",
                    severity="high",
                    priority="high",
                    category="critical",
                    suggested_action="View GPU details and reduce GPU load.",
                    action_buttons=["View GPU Details", "Dismiss"],
                    voice_message="GPU temperature is above the safe threshold.",
                    sound_enabled=False,
                    voice_enabled=False,
                    metadata={
                        "gpu_name": sample.gpu_name,
                        "temperature_celsius": sample.temperature_celsius,
                        "threshold_celsius": settings.threshold_celsius,
                    },
                )
        if settings.sound_enabled:
            self._play_sound()
        if settings.voice_enabled:
            self._speak()
        timestamp = datetime.utcnow().isoformat()
        with self._lock:
            self.status.alert_active = True
            self.status.last_alert_time = timestamp
        logger.warning(
            "GPU Alert Triggered temperature=%s timestamp=%s gpu=%s",
            sample.temperature_celsius,
            timestamp,
            sample.gpu_name,
        )

    def _stop_alert_if_needed(self, sample: GpuSample) -> None:
        with self._lock:
            was_active = self.status.alert_active
            self.status.alert_active = False
            if was_active:
                self.status.last_stop_time = datetime.utcnow().isoformat()
        if was_active:
            logger.info("GPU Alert Stopped temperature=%s gpu=%s timestamp=%s", sample.temperature_celsius, sample.gpu_name, self.status.last_stop_time)

    def _play_sound(self) -> None:
        if not self.sound_path.exists():
            logger.error("GPU alert sound missing: %s", self.sound_path)
            return
        try:
            import winsound

            winsound.PlaySound(str(self.sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            threading.Timer(2.0, lambda: winsound.PlaySound(None, winsound.SND_PURGE)).start()
            logging.getLogger("nexa.alerts").info("Sound Played module=gpu_monitor sound=%s reason=gpu_over_threshold", self.sound_path)
        except Exception:
            logger.exception("GPU alert sound playback failed")

    def _speak(self) -> None:
        text = "GPU temperature is above the safe threshold."
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
            logging.getLogger("nexa.alerts").info("Voice Played module=gpu_monitor text=%s", text)
        except Exception:
            logger.exception("GPU alert voice playback failed")

    def _last_alert_datetime(self) -> datetime | None:
        with self._lock:
            value = self.status.last_alert_time
        return datetime.fromisoformat(value) if value else None

    def _health(self, temperature: float | None, threshold: int) -> str:
        if temperature is None:
            return "Unavailable"
        if temperature > threshold:
            return "Hot"
        if temperature >= threshold - 5:
            return "Warm"
        return "Good"

    def _validate_settings(self, settings: GpuMonitorSettings) -> None:
        if not 1 <= settings.threshold_celsius <= 120:
            raise ValueError("threshold_celsius must be between 1 and 120")
        if settings.repeat_interval_seconds < 30:
            raise ValueError("repeat_interval_seconds must be at least 30")

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


gpu_monitor_service = GpuMonitorService()
