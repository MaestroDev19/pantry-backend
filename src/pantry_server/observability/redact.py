from __future__ import annotations

import re
from typing import Any

_REDACT_KEYS = frozenset(
    {
        "authorization",
        "invite_code",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "secret",
        "api_key",
    }
)

_JWT_LIKE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _key_is_sensitive(key: str) -> bool:
    lower = key.lower()
    if lower in _REDACT_KEYS:
        return True
    return "jwt" in lower or "token" in lower or "secret" in lower


def _value_looks_like_jwt(value: Any) -> bool:
    if not isinstance(value, str) or len(value) < 20:
        return False
    return bool(_JWT_LIKE.match(value.strip()))


def redact_for_log(obj: Any) -> Any:
    """Return a log-safe copy: invite codes, tokens, and JWT-shaped strings are redacted."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if _key_is_sensitive(str(k)):
                out[str(k)] = "[REDACTED]"
            else:
                out[str(k)] = redact_for_log(v)
        return out
    if isinstance(obj, list):
        return [redact_for_log(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact_for_log(item) for item in obj)
    if isinstance(obj, str) and _value_looks_like_jwt(obj):
        return "[REDACTED]"
    return obj


__all__ = ["redact_for_log"]
