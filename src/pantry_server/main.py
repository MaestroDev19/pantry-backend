import logging

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pantry_server.api.router import api_router
from pantry_server.core.config import get_settings
from pantry_server.core.errors import register_exception_handlers
from pantry_server.core.lifespan import lifespan
from pantry_server.middleware.rate_limit import create_limiter, rate_limit_exceeded_handler
from pantry_server.middleware.request_context import RequestContextMiddleware

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
if settings.rate_limit_enabled and settings.rate_limit_per_minute > 0:
    app.state.limiter = create_limiter(limit_per_minute=settings.rate_limit_per_minute)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello, Welcome to the Pantry Server!"}
