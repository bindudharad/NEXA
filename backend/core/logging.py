import logging
from pathlib import Path

from backend.core.config import get_settings


def _attach_file_logger(name: str, log_file: Path, *, propagate: bool = True) -> None:
    logger = logging.getLogger(name)
    resolved = str(log_file.resolve())
    if not any(getattr(handler, "baseFilename", "") == resolved for handler in logger.handlers):
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = propagate


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    for file_name in ("nexa.log", "errors.log", "alerts.log", "battery.log", "voice.log", "task.log", "automation.log", "recovery.log", "security.log", "performance.log"):
        (log_dir / file_name).touch(exist_ok=True)

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

    _attach_file_logger("nexa.alerts", log_dir / "alerts.log")
    _attach_file_logger("nexa.battery", log_dir / "battery.log")
    _attach_file_logger("nexa.voice", log_dir / "voice.log")
    _attach_file_logger("nexa.tasks", log_dir / "task.log")
    _attach_file_logger("nexa.automation", log_dir / "automation.log")
    _attach_file_logger("nexa.recovery", log_dir / "recovery.log")
    _attach_file_logger("nexa.security", log_dir / "security.log")
    _attach_file_logger("nexa.performance", log_dir / "performance.log")
    _attach_file_logger("nexa.resource", log_dir / "performance.log")
