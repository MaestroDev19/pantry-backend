from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pantry_server.core.exceptions import AppError


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "error_code": "validation_error",
            "request_id": request_id,
            "errors": exc.errors(),
        },
    )


async def unhandled_exception_handler(request: Request, _: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "internal_server_error",
            "request_id": request_id,
        },
    )


async def app_error_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "request_id": request_id,
        },
        headers=exc.headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
