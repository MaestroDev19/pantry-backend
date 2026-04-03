from __future__ import annotations

from prometheus_client import Counter

household_operations_total = Counter(
    "household_operations_total",
    "Household create/join/leave/convert outcomes",
    labelnames=("operation", "outcome", "reason"),
)

auth_failures_total = Counter(
    "auth_failures_total",
    "Authentication and household-membership resolution failures",
    labelnames=("reason",),
)


def record_household_outcome(*, operation: str, outcome: str, reason: str) -> None:
    household_operations_total.labels(
        operation=operation,
        outcome=outcome,
        reason=reason,
    ).inc()


def record_auth_failure(*, reason: str) -> None:
    auth_failures_total.labels(reason=reason).inc()


__all__ = [
    "auth_failures_total",
    "household_operations_total",
    "record_auth_failure",
    "record_household_outcome",
]
