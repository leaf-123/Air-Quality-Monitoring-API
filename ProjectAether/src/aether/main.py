# main
# starts up the API using initialize_services (from dependencies.py)
# handles exceptions w/ exception_handlers

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from aether.dependencies import initialize_services
from aether.routes import router as api_router
from aether.sensor_manager import UnauthorizedSensorError, InvalidReadingError

logger = logging.getLogger(__name__)


def create_app(config_path: str, sensors_path: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Initialize all singletons/services once at startup (config, sensors, persistence, etc.)
        logger.info("Starting Aether API (config=%s sensors=%s)", config_path, sensors_path)
        initialize_services(config_path, sensors_path)
        yield
        logger.info("Shutting down Aether API")

    # endpoints
    app = FastAPI(
        title="Aether Sensor Analytics API",
        version="1.0.0",
        description=(
            "Backend API for ingesting sensor readings, retrieving historical data, "
            "and generating analytics/visualization outputs."
        ),
        lifespan=lifespan,
    )
    app.include_router(api_router)

    # exception handlers
    @app.exception_handler(UnauthorizedSensorError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedSensorError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidReadingError)
    async def invalid_reading_handler(request: Request, exc: InvalidReadingError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Log full traceback server-side, return generic message to clients
        logger.exception("Unhandled server error on %s %s", request.method, request.url, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal Server Error"},
        )

    return app


# global app
# Defaults for local run; tests can pass temporary config paths via create_app(...)
app = create_app(
    os.getenv("AETHER_CONFIG_PATH", "config/server_config.json"),
    os.getenv("AETHER_SENSORS_PATH", "config/sensors.json"),
)
