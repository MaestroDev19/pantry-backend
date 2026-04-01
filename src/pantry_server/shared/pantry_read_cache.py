"""Short-TTL in-process cache for safe pantry list reads (reduces Supabase round trips)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

_lock = asyncio.Lock()
_entries: dict[str, tuple[float, Any]] = {}


def _monotonic_now() -> float:
    return time.monotonic()


async def get_or_set_coroutine(
    key: str,
    ttl_seconds: float,
    factory: Callable[[], Awaitable[T]],
) -> T:
    async with _lock:
        entry = _entries.get(key)
        if entry is not None:
            stored_at, value = entry
            if _monotonic_now() - stored_at < ttl_seconds:
                return value  # type: ignore[return-value]

    value = await factory()

    async with _lock:
        _entries[key] = (_monotonic_now(), value)
    return value  # type: ignore[return-value]


async def invalidate_keys(*keys: str) -> None:
    async with _lock:
        for k in keys:
            _entries.pop(k, None)


def cache_key_my_items(owner_id: str) -> str:
    return f"pantry:my_items:{owner_id}"


def cache_key_household(household_id: str) -> str:
    return f"pantry:household:{household_id}"
