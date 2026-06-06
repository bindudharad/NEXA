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

    task_logger = logging.getLogger("nexa.tasks")
    if not any(getattr(handler, "baseFilename", "").endswith("task.log") for handler in task_logger.handlers):
        task_handler = logging.FileHandler(log_dir / "task.log", encoding="utf-8")
        task_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        task_logger.addHandler(task_handler)
        task_logger.setLevel(logging.INFO)
