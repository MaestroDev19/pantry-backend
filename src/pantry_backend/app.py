from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pantry_backend.api.v1.router import api_router
from pantry_backend.core.errors import (
    rate_limit_exceeded_handler,
    unhandled_exception_handler,
)
from pantry_backend.core.logging import RequestLoggingMiddleware
from pantry_backend.core.rate_limit import limiter
from pantry_backend.core.settings import get_settings
from pantry_backend.core.web.request_id import RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(level=logging.INFO)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    if settings.rate_limit_enabled:
        app.state.limiter = limiter
        app.add_middleware(SlowAPIMiddleware)
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(api_router)
    return app


