from __future__ import annotations

import logging


def log_household_event(
    logger: logging.Logger,
    *,
    operation: str,
    outcome: str,
    reason: str,
) -> None:
    logger.info(
        "household_operation",
        extra={
            "event": "household_operation",
            "operation": operation,
            "outcome": outcome,
            "reason": reason,
        },
    )


def log_auth_failure(logger: logging.Logger, *, reason: str) -> None:
    logger.warning(
        "auth_failure",
        extra={
            "event": "auth_failure",
            "reason": reason,
        },
    )


def log_rate_limit_event(
    logger: logging.Logger,
    *,
    scope: str = "household_join",
    dimension: str,
    request_id: str,
    path: str,
    client_ip: str | None = None,
    user_id: str | None = None,
) -> None:
    extra: dict[str, str] = {
        "event": "rate_limit",
        "scope": scope,
        "dimension": dimension,
        "request_id": request_id,
        "path": path,
    }
    if client_ip is not None:
        extra["client_ip"] = client_ip
    if user_id is not None:
        extra["user_id"] = user_id
    logger.warning("rate_limit", extra=extra)


__all__ = ["log_auth_failure", "log_household_event", "log_rate_limit_event"]
