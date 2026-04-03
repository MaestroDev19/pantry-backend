from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from fastapi import Depends, Request

from pantry_server.core.config import Settings, get_settings
from pantry_server.core.exceptions import AppError
from pantry_server.middleware.rate_limit import WINDOW_SECONDS
from pantry_server.observability.logging_events import log_rate_limit_event
from pantry_server.observability.metrics import record_household_outcome
from pantry_server.shared.auth import get_current_user_id

LOGGER = logging.getLogger("pantry_server.rate_limit")

_JOIN_PATH_SUFFIX = "/households/join"


class _FixedWindowLimiter:
    """In-process fixed-window counter (monotonic clock). Not shared across processes."""

    def __init__(self, *, window_seconds: int) -> None:
        self._window = float(window_seconds)
        self._data: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    def clear(self) -> None:
        self._data.clear()

    async def allow(self, key: str, limit: int) -> bool:
        if limit <= 0:
            return True
        async with self._lock:
            now = time.monotonic()
            start, count = self._data.get(key, (now, 0))
            if now - start >= self._window:
                self._data[key] = (now, 1)
                return True
            if count < limit:
                self._data[key] = (start, count + 1)
                return True
            return False


_ip_limiter = _FixedWindowLimiter(window_seconds=WINDOW_SECONDS)
_user_limiter = _FixedWindowLimiter(window_seconds=WINDOW_SECONDS)


def _clear_for_testing() -> None:
    _ip_limiter.clear()
    _user_limiter.clear()


def _client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _join_path(request: Request) -> str:
    return request.url.path


async def enforce_join_ip_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.households_join_rate_limit_enabled:
        return
    limit = settings.households_join_rate_limit_ip_per_minute
    if limit <= 0:
        return
    if request.method != "POST" or not request.url.path.endswith(_JOIN_PATH_SUFFIX):
        return
    ip = _client_ip(request, settings)
    allowed = await _ip_limiter.allow(f"ip:{ip}", limit)
    if allowed:
        return
    request_id = getattr(request.state, "request_id", "unknown")
    record_household_outcome(operation="join", outcome="failure", reason="rate_limited")
    log_rate_limit_event(
        LOGGER,
        dimension="ip",
        request_id=request_id,
        path=_join_path(request),
        client_ip=ip,
    )
    raise AppError(
        "Rate limit exceeded",
        status_code=429,
        error_code="rate_limit_exceeded",
        headers={"Retry-After": str(WINDOW_SECONDS)},
    )


async def enforce_join_user_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    if not settings.households_join_rate_limit_enabled:
        return
    limit = settings.households_join_rate_limit_user_per_minute
    if limit <= 0:
        return
    if request.method != "POST" or not request.url.path.endswith(_JOIN_PATH_SUFFIX):
        return
    key = f"user:{user_id}"
    allowed = await _user_limiter.allow(key, limit)
    if allowed:
        return
    request_id = getattr(request.state, "request_id", "unknown")
    ip = _client_ip(request, settings)
    record_household_outcome(operation="join", outcome="failure", reason="rate_limited")
    log_rate_limit_event(
        LOGGER,
        dimension="user",
        request_id=request_id,
        path=_join_path(request),
        client_ip=ip,
        user_id=str(user_id),
    )
    raise AppError(
        "Rate limit exceeded",
        status_code=429,
        error_code="rate_limit_exceeded",
        headers={"Retry-After": str(WINDOW_SECONDS)},
    )


__all__ = [
    "enforce_join_ip_limit",
    "enforce_join_user_limit",
]
