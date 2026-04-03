from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from pantry_server.contexts.households.domain.models import HouseholdJoinResponse, HouseholdResponse
from pantry_server.contexts.households.presentation.router import get_household_service
from pantry_server.core.config import Settings, get_settings
from pantry_server.main import app
from pantry_server.middleware.household_join_rate_limit import _clear_for_testing


@pytest.fixture(autouse=True)
def clear_join_limiters() -> None:
    _clear_for_testing()
    yield
    _clear_for_testing()


def _join_settings(**kwargs: Any) -> Settings:
    data: dict[str, Any] = {
        "supabase_url": "https://example.supabase.co",
        "auth_allow_x_user_id_header": False,
        "households_join_rate_limit_enabled": True,
        "households_join_rate_limit_ip_per_minute": 2,
        "households_join_rate_limit_user_per_minute": 100,
        "trust_x_forwarded_for": False,
    }
    data.update(kwargs)
    return Settings(**data)


class _FakeHouseholdService:
    async def join_household_by_invite(self, invite_code: str, user_id) -> HouseholdJoinResponse:
        return HouseholdJoinResponse(
            household=HouseholdResponse(
                id=uuid4(),
                name="Home",
                created_at="2024-01-01T00:00:00Z",
                invite_code="inv",
            ),
        )


def test_join_ip_limit_returns_429_before_authentication() -> None:
    app.dependency_overrides[get_settings] = lambda: _join_settings(
        households_join_rate_limit_ip_per_minute=2,
        households_join_rate_limit_user_per_minute=100,
    )
    try:
        client = TestClient(app)
        payload = {"invite_code": "abc"}
        first = client.post("/api/households/join", json=payload)
        second = client.post("/api/households/join", json=payload)
        third = client.post("/api/households/join", json=payload)

        assert first.status_code == 401
        assert second.status_code == 401
        assert third.status_code == 429
        body = third.json()
        assert body["error_code"] == "rate_limit_exceeded"
        assert third.headers.get("Retry-After") == "60"
    finally:
        app.dependency_overrides.clear()


def test_join_user_limit_returns_429_after_successful_joins() -> None:
    uid = "8b68f5fc-2660-4f80-a31e-58699bc2465d"
    app.dependency_overrides[get_settings] = lambda: _join_settings(
        auth_allow_x_user_id_header=True,
        households_join_rate_limit_ip_per_minute=1000,
        households_join_rate_limit_user_per_minute=2,
        supabase_url=None,
    )
    app.dependency_overrides[get_household_service] = lambda: _FakeHouseholdService()
    try:
        client = TestClient(app)
        headers = {"x-user-id": uid}
        payload = {"invite_code": "abc"}
        first = client.post("/api/households/join", json=payload, headers=headers)
        second = client.post("/api/households/join", json=payload, headers=headers)
        third = client.post("/api/households/join", json=payload, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert third.json()["error_code"] == "rate_limit_exceeded"
    finally:
        app.dependency_overrides.clear()


def test_join_uses_x_forwarded_for_when_trusted() -> None:
    app.dependency_overrides[get_settings] = lambda: _join_settings(
        households_join_rate_limit_ip_per_minute=1,
        households_join_rate_limit_user_per_minute=0,
        trust_x_forwarded_for=True,
    )
    try:
        client = TestClient(app)
        payload = {"invite_code": "abc"}
        h1 = {"x-forwarded-for": "10.0.0.1"}
        h2 = {"x-forwarded-for": "10.0.0.2"}
        assert client.post("/api/households/join", json=payload, headers=h1).status_code == 401
        assert client.post("/api/households/join", json=payload, headers=h2).status_code == 401
        assert client.post("/api/households/join", json=payload, headers=h1).status_code == 429
    finally:
        app.dependency_overrides.clear()
