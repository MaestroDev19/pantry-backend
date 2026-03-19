from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(
        self,
        message: str,
        status_code: int,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.extra = extra or {}
        super().__init__(status_code=status_code, detail=message, headers=headers)

