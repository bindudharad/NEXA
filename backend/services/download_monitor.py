from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.database.session import SessionLocal
from backend.services.evolution import evolution_service

logger = logging.getLogger("nexa.download-monitor")


@dataclass
class DownloadMonitorStatus:
    running: bool = False
    backend: str = "watchdog"
    watched_paths: list[str] | None = None
    last_event_type: str | None = None
    last_event_path: str | None = None
    last_error: str | None = None


class DownloadMonitoringService:
    """Event-driven Downloads watcher.

    Uses OS filesystem notifications through watchdog when available. It never
    performs a tight polling loop; events trigger a bounded scan of the changed
    folder so duplicate, large-file, timeline, and notification integrations
    stay centralized in EvolutionService.
    """

    def __init__(self) -> None:
        self.status = DownloadMonitorStatus(watched_paths=[])
        self._observer = None
        self._lock = threading.Lock()

    def start(self, paths: list[str] | None = None) -> dict:
        with self._lock:
            if self.status.running:
                return self.get_status()
            try:
                from watchdog.events import FileSystemEventHandler
                from watchdog.observers import Observer
            except Exception as exc:
                self.status.last_error = "watchdog dependency is not installed"
                logger.warning("Download monitor unavailable: %s", exc)
                return self.get_status()

            watch_paths = [Path(item).expanduser().resolve() for item in (paths or [Path.home() / "Downloads"])]
            watch_paths = [path for path in watch_paths if path.exists()]
            if not watch_paths:
                self.status.last_error = "No download folders available to watch"
                return self.get_status()

            service = self

            class Handler(FileSystemEventHandler):
                def on_created(self, event):  # type: ignore[no-untyped-def]
                    service._handle_event("created", event.src_path, getattr(event, "is_directory", False))

                def on_moved(self, event):  # type: ignore[no-untyped-def]
                    service._handle_event("moved", getattr(event, "dest_path", event.src_path), getattr(event, "is_directory", False))

                def on_deleted(self, event):  # type: ignore[no-untyped-def]
                    service._handle_event("deleted", event.src_path, getattr(event, "is_directory", False))

            observer = Observer()
            handler = Handler()
            for path in watch_paths:
                observer.schedule(handler, str(path), recursive=False)
            observer.daemon = True
            observer.start()
            self._observer = observer
            self.status.running = True
            self.status.last_error = None
            self.status.watched_paths = [str(path) for path in watch_paths]
            logger.info("Download monitor started paths=%s", self.status.watched_paths)
            return self.get_status()

    def stop(self) -> dict:
        with self._lock:
            if self._observer is not None:
                self._observer.stop()
                self._observer.join(timeout=3)
                self._observer = None
            self.status.running = False
            logger.info("Download monitor stopped")
            return self.get_status()

    def get_status(self) -> dict:
        return asdict(self.status)

    def _handle_event(self, event_type: str, raw_path: str, is_directory: bool) -> None:
        if is_directory:
            return
        path = Path(raw_path)
        if path.suffix.lower() in evolution_service.incomplete_download_suffixes:
            return
        self.status.last_event_type = event_type
        self.status.last_event_path = str(path)
        try:
            if event_type in {"created", "moved"} and path.parent.exists():
                with SessionLocal() as db:
                    evolution_service.scan_downloads(db, str(path.parent), large_file_mb=100)
            logger.info("Download monitor event type=%s path=%s", event_type, path)
        except Exception as exc:
            self.status.last_error = str(exc)
            logger.exception("Download monitor event failed path=%s", path)


download_monitoring_service = DownloadMonitoringService()
