from __future__ import annotations

import asyncio
import time

from fastapi import Request

from pantry_server.core.config import Settings
from pantry_server.middleware.rate_limit import WINDOW_SECONDS


class FixedWindowRateLimiter:
    """In-process fixed-window counter (monotonic clock). Not shared across processes."""

    def __init__(self, *, window_seconds: int = WINDOW_SECONDS) -> None:
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


def client_ip_for_rate_limit(request: Request, settings: Settings) -> str:
    if settings.trust_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


__all__ = [
    "FixedWindowRateLimiter",
    "WINDOW_SECONDS",
    "client_ip_for_rate_limit",
]
