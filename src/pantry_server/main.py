import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pantry_server.api.router import api_router
from pantry_server.core.config import get_settings
from pantry_server.core.errors import register_exception_handlers
from pantry_server.core.lifespan import lifespan
from pantry_server.middleware.rate_limit import create_limiter, rate_limit_exceeded_handler
from pantry_server.middleware.request_context import RequestContextMiddleware
from pantry_server.observability.logging_setup import setup_logging

settings = get_settings()

setup_logging()

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
if settings.rate_limit_enabled and settings.rate_limit_per_minute > 0:
    app.state.limiter = create_limiter(limit_per_minute=settings.rate_limit_per_minute)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api")
if settings.metrics_enabled:
    try:
        from prometheus_client import make_asgi_app

        app.mount("/metrics", make_asgi_app())
    except ImportError:
        logging.getLogger(__name__).warning(
            "prometheus_client not installed; /metrics disabled"
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello, Welcome to the Pantry Server!"}
