from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response

LOGGER = logging.getLogger("pantry_server.requests")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        request.state.request_id = request_id

        start = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((perf_counter() - start) * 1000, 2)
            LOGGER.exception(
                "request_failed method=%s path=%s duration_ms=%s request_id=%s",
                request.method,
                request.url.path,
                elapsed_ms,
                request_id,
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error_code": "internal_server_error",
                    "request_id": request_id,
                },
            )
        elapsed_ms = round((perf_counter() - start) * 1000, 2)

        response.headers["x-request-id"] = request_id
        LOGGER.info(
            "request_handled method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response
