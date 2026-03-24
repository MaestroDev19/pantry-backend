from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pantry_server.middleware.rate_limit import WINDOW_SECONDS, create_limiter, rate_limit_exceeded_handler
from pantry_server.middleware.request_context import RequestContextMiddleware


def test_request_context_uses_incoming_request_id_header() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"result": "ok"}

    client = TestClient(app)
    response = client.get("/ok", headers={"x-request-id": "req-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-123"


def test_request_context_returns_standard_error_response_on_exception() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom", headers={"x-request-id": "req-fail"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error",
        "error_code": "internal_server_error",
        "request_id": "req-fail",
    }
    assert response.headers["x-request-id"] == "req-fail"


def test_rate_limit_blocks_request_after_limit_is_reached() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.state.limiter = create_limiter(limit_per_minute=1)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/limited")
    async def limited() -> dict[str, str]:
        return {"result": "ok"}

    client = TestClient(app)

    first = client.get("/limited", headers={"x-user-id": "u-1"})
    second = client.get("/limited", headers={"x-user-id": "u-1"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == str(WINDOW_SECONDS)
    payload = second.json()
    assert "Rate limit exceeded" in f"{payload.get('detail', '')}{payload.get('error', '')}"


def test_rate_limit_is_disabled_when_limit_is_zero() -> None:
    app = FastAPI()

    @app.get("/unlimited")
    async def unlimited() -> dict[str, str]:
        return {"result": "ok"}

    client = TestClient(app)

    first = client.get("/unlimited")
    second = client.get("/unlimited")

    assert first.status_code == 200
    assert second.status_code == 200
