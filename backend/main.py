import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.core.logging import configure_logging
from backend.database.session import init_database
from backend.services.battery_alert import battery_alert_service
from backend.services.gpu_monitor import gpu_monitor_service
from backend.services.website_monitor import website_monitoring_service


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncIterator[None]:
    battery_alert_service.start()
    gpu_monitor_service.start()
    website_monitoring_service.start()
    try:
        yield
    finally:
        website_monitoring_service.stop()
        gpu_monitor_service.stop()
        battery_alert_service.stop()


def create_app() -> FastAPI:
    configure_logging()
    logging.getLogger(__name__).info("Starting Nexa API")
    init_database()
    app = FastAPI(title="Nexa API", version="1.0.0", lifespan=app_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
