from __future__ import annotations

import time
from typing import Any, Dict, Optional


class InMemoryCache:
    def __init__(self) -> None:
        self._store: Dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = time.monotonic() + ttl_seconds
        self._store[key] = (expires_at, value)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


_CACHE = InMemoryCache()


def get_cache() -> InMemoryCache:
    return _CACHE


__all__ = ["InMemoryCache", "get_cache"]

