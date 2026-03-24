import anyio
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from pantry_server.core.errors import (
    app_error_exception_handler,
    register_exception_handlers,
    unhandled_exception_handler,
    validation_exception_handler,
)
from pantry_server.core.exceptions import AppError
from pantry_server.core.lifespan import lifespan


def _build_request_with_state(request_id: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "state": {"request_id": request_id},
    }
    return Request(scope)


def test_validation_exception_handler_returns_standard_payload() -> None:
    request = _build_request_with_state("req-1")
    exc = RequestValidationError([{"loc": ("body", "name"), "msg": "required", "type": "missing"}])

    response = anyio.run(validation_exception_handler, request, exc)

    assert response.status_code == 422
    assert response.body
    assert b'"error_code":"validation_error"' in response.body
    assert b'"request_id":"req-1"' in response.body


def test_unhandled_exception_handler_returns_internal_error_payload() -> None:
    request = _build_request_with_state("req-2")

    response = anyio.run(unhandled_exception_handler, request, Exception("boom"))

    assert response.status_code == 500
    assert b'"error_code":"internal_server_error"' in response.body
    assert b'"request_id":"req-2"' in response.body


def test_app_error_exception_handler_uses_app_error_fields() -> None:
    request = _build_request_with_state("req-3")
    exc = AppError(
        "Denied",
        status_code=403,
        error_code="forbidden",
        headers={"X-Reason": "auth"},
    )

    response = anyio.run(app_error_exception_handler, request, exc)

    assert response.status_code == 403
    assert response.headers["x-reason"] == "auth"
    assert b'"detail":"Denied"' in response.body
    assert b'"error_code":"forbidden"' in response.body


def test_register_exception_handlers_registers_all_custom_handlers() -> None:
    app = FastAPI()

    register_exception_handlers(app)

    assert AppError in app.exception_handlers
    assert RequestValidationError in app.exception_handlers
    assert Exception in app.exception_handlers


def test_lifespan_context_manager_yields_without_error() -> None:
    app = FastAPI()

    async def _run() -> None:
        async with lifespan(app):
            pass

    anyio.run(_run)
