import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router, scheduler
from backend.core.logging import configure_logging
from backend.database.session import init_database
from backend.services.gpu_monitor import gpu_monitor_service
from backend.services.power_monitor import power_monitor_service
from backend.services.download_monitor import download_monitoring_service
from backend.services.resource_manager import resource_manager_service
from backend.services.system_alerts import system_alert_service
from backend.services.evolution import evolution_service
from backend.services.voice_assistant import voice_assistant_service
from backend.services.website_monitor import website_monitoring_service


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    voice_assistant_service.mark_starting()
    evolution_service.recovery_startup_check()
    resource_manager_service.start()
    power_monitor_service.start()
    gpu_monitor_service.start()
    system_alert_service.start()
    website_monitoring_service.start()
    download_monitoring_service.start()
    voice_assistant_service.start()
    evolution_service.ensure_daily_briefing_schedule(scheduler)
    try:
        yield
    finally:
        evolution_service.recovery_clean_shutdown()
        voice_assistant_service.stop()
        download_monitoring_service.stop()
        website_monitoring_service.stop()
        system_alert_service.stop()
        gpu_monitor_service.stop()
        power_monitor_service.stop()
        resource_manager_service.stop()


def create_app() -> FastAPI:
    configure_logging()
    logging.getLogger(__name__).info("Starting Nexa API")
    init_database()
    app = FastAPI(title="Nexa API", version="1.0.0", lifespan=app_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5175", "http://127.0.0.1:5175", "http://localhost:4173", "http://127.0.0.1:4173"],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
