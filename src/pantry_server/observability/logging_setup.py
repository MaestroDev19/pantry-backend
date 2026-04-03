from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pantry_server.observability.redact import redact_for_log

_LOG_RECORD_STANDARD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "message",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """One JSON object per line; merges `extra={}` keys into the payload."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _LOG_RECORD_STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(redact_for_log(payload), default=str)


def setup_logging(*, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)


__all__ = ["JsonFormatter", "setup_logging"]
