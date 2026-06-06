import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.core.logging import configure_logging
from backend.database.session import init_database
from backend.services.battery_alert import battery_alert_service


def create_app() -> FastAPI:
    configure_logging()
    logging.getLogger(__name__).info("Starting Nexa API")
    init_database()
    app = FastAPI(title="Nexa API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.add_event_handler("startup", battery_alert_service.start)
    app.add_event_handler("shutdown", battery_alert_service.stop)
    return app


app = create_app()
