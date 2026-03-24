from fastapi.testclient import TestClient

from pantry_server.main import app


def test_health_endpoint_returns_ok_status() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_root_endpoint_returns_welcome_message() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Welcome to the Pantry Server!"}
