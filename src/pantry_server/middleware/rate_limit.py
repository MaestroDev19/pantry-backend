from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

WINDOW_SECONDS = 60


def rate_limit_key_func(request: Request) -> str:
    user_id = request.headers.get("x-user-id", "")
    client_ip = request.client.host if request.client else "unknown"
    identity = user_id or client_ip
    return f"{request.method}:{request.url.path}:{identity}"


def create_limiter(*, limit_per_minute: int) -> Limiter:
    return Limiter(
        key_func=rate_limit_key_func,
        application_limits=[f"{limit_per_minute}/minute"],
        headers_enabled=True,
    )


async def rate_limit_exceeded_handler(request: Request, _: RateLimitExceeded) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "error_code": "rate_limit_exceeded",
            "request_id": request_id,
        },
        headers={"Retry-After": str(WINDOW_SECONDS)},
    )
