from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from pantry_backend.core.settings import get_settings


settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.rate_limit_per_minute}/minute",
    ]
    if getattr(settings, "rate_limit_enabled", False)
    else [],
)

