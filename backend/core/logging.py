import logging
from pathlib import Path

from backend.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "nexa.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )

    error_handler = logging.FileHandler(log_dir / "errors.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(error_handler)

    alerts_logger = logging.getLogger("nexa.alerts")
    if not any(getattr(handler, "baseFilename", "").endswith("alerts.log") for handler in alerts_logger.handlers):
        alerts_handler = logging.FileHandler(log_dir / "alerts.log", encoding="utf-8")
        alerts_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        alerts_logger.addHandler(alerts_handler)
        alerts_logger.setLevel(logging.INFO)
        alerts_logger.propagate = True

    battery_logger = logging.getLogger("nexa.battery")
    if not any(getattr(handler, "baseFilename", "").endswith("battery.log") for handler in battery_logger.handlers):
        battery_handler = logging.FileHandler(log_dir / "battery.log", encoding="utf-8")
        battery_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        battery_logger.addHandler(battery_handler)
        battery_logger.setLevel(logging.INFO)
        battery_logger.propagate = True

    voice_logger = logging.getLogger("nexa.voice")
    if not any(getattr(handler, "baseFilename", "").endswith("voice.log") for handler in voice_logger.handlers):
        voice_handler = logging.FileHandler(log_dir / "voice.log", encoding="utf-8")
        voice_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        voice_logger.addHandler(voice_handler)
        voice_logger.setLevel(logging.INFO)
        voice_logger.propagate = True

    task_logger = logging.getLogger("nexa.tasks")
    if not any(getattr(handler, "baseFilename", "").endswith("task.log") for handler in task_logger.handlers):
        task_handler = logging.FileHandler(log_dir / "task.log", encoding="utf-8")
        task_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        task_logger.addHandler(task_handler)
        task_logger.setLevel(logging.INFO)
