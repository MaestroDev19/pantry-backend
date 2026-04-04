from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, Request

from pantry_server.core.config import Settings, get_settings
from pantry_server.core.exceptions import AppError
from pantry_server.middleware.fixed_window_limiter import (
    FixedWindowRateLimiter,
    client_ip_for_rate_limit,
)
from pantry_server.middleware.rate_limit import WINDOW_SECONDS
from pantry_server.observability.logging_events import log_rate_limit_event
from pantry_server.observability.metrics import record_household_outcome
from pantry_server.shared.auth import get_current_user_id

LOGGER = logging.getLogger("pantry_server.rate_limit")

_AI_PATH_PREFIX = "/api/ai/"
_HOUSEHOLD_MUTATION_SUFFIXES = frozenset(
    {
        "/households/create",
        "/households/leave",
        "/households/convert-to-joinable",
        "/households/rename",
    },
)

_ai_ip_limiter = FixedWindowRateLimiter(window_seconds=WINDOW_SECONDS)
_household_mutation_user_limiter = FixedWindowRateLimiter(window_seconds=WINDOW_SECONDS)


def clear_supplementary_rate_limiters_for_testing() -> None:
    _ai_ip_limiter.clear()
    _household_mutation_user_limiter.clear()


def _household_mutation_path(request: Request) -> bool:
    path = request.url.path
    return request.method == "POST" and any(path.endswith(s) for s in _HOUSEHOLD_MUTATION_SUFFIXES)


async def enforce_ai_ip_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.ai_rate_limit_enabled:
        return
    limit = settings.ai_rate_limit_ip_per_minute
    if limit <= 0:
        return
    if request.method != "POST" or not request.url.path.startswith(_AI_PATH_PREFIX):
        return
    ip = client_ip_for_rate_limit(request, settings)
    allowed = await _ai_ip_limiter.allow(f"ai:ip:{ip}", limit)
    if allowed:
        return
    request_id = getattr(request.state, "request_id", "unknown")
    log_rate_limit_event(
        LOGGER,
        scope="ai",
        dimension="ip",
        request_id=request_id,
        path=request.url.path,
        client_ip=ip,
    )
    raise AppError(
        "Rate limit exceeded",
        status_code=429,
        error_code="rate_limit_exceeded",
        headers={"Retry-After": str(WINDOW_SECONDS)},
    )


async def enforce_household_mutation_user_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    if not settings.household_mutations_rate_limit_enabled:
        return
    limit = settings.household_mutations_user_per_minute
    if limit <= 0:
        return
    if not _household_mutation_path(request):
        return
    key = f"household_mut:user:{user_id}"
    allowed = await _household_mutation_user_limiter.allow(key, limit)
    if allowed:
        return
    request_id = getattr(request.state, "request_id", "unknown")
    ip = client_ip_for_rate_limit(request, settings)
    record_household_outcome(operation="mutation", outcome="failure", reason="rate_limited")
    log_rate_limit_event(
        LOGGER,
        scope="household_mutation",
        dimension="user",
        request_id=request_id,
        path=request.url.path,
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
    "clear_supplementary_rate_limiters_for_testing",
    "enforce_ai_ip_limit",
    "enforce_household_mutation_user_limit",
]
