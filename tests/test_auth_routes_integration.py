from fastapi.testclient import TestClient

from pantry_server.core.exceptions import AppError
from pantry_server.main import app
from pantry_server.shared.auth import get_current_household_id, get_current_user


def test_generate_recipe_returns_401_when_auth_rejects() -> None:
    async def deny() -> None:
        raise AppError("Missing authentication credentials", status_code=401)

    app.dependency_overrides[get_current_user] = deny
    try:
        client = TestClient(app)
        response = client.post(
            "/api/recipes/generate-recipe",
            json={"pantry_items": ["tomato"], "dietary_preferences": []},
        )
        assert response.status_code == 401
        body = response.json()
        assert body["detail"] == "Missing authentication credentials"
        assert body["error_code"] == "app_error"
    finally:
        app.dependency_overrides.clear()


def test_get_household_pantry_returns_403_when_no_household_membership() -> None:
    async def no_household() -> None:
        raise AppError(
            "User is not a member of any household",
            status_code=403,
        )

    app.dependency_overrides[get_current_household_id] = no_household
    try:
        client = TestClient(app)
        response = client.get("/api/pantry-items/get-household-pantry")
        assert response.status_code == 403
        body = response.json()
        assert body["detail"] == "User is not a member of any household"
        assert body["error_code"] == "app_error"
    finally:
        app.dependency_overrides.clear()
