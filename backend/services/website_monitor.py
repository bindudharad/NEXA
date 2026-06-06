from __future__ import annotations

import logging
import threading

from backend.database.session import SessionLocal
from backend.services.website_profiles import WebsiteProfileService

logger = logging.getLogger("nexa.website-monitor")


class WebsiteMonitoringService:
    def __init__(self, poll_interval_seconds: int = 60) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="nexa-website-monitor", daemon=True)
        self._thread.start()
        logger.info("Website monitoring service started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        logger.info("Website monitoring service stopped")

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_interval_seconds):
            try:
                with SessionLocal() as db:
                    WebsiteProfileService(db).check_monitored()
            except Exception:
                logger.exception("Website monitoring cycle failed")


website_monitoring_service = WebsiteMonitoringService()
