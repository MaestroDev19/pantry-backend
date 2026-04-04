from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from pantry_server.contexts.households.domain.models import HouseholdResponse
from pantry_server.contexts.households.presentation.router import get_household_service
from pantry_server.core.config import Settings, get_settings
from pantry_server.main import app
from pantry_server.middleware.household_join_rate_limit import _clear_for_testing as clear_join_limiters
from pantry_server.middleware.supplementary_rate_limits import (
    clear_supplementary_rate_limiters_for_testing,
)


@pytest.fixture(autouse=True)
def clear_limiters() -> None:
    clear_join_limiters()
    clear_supplementary_rate_limiters_for_testing()
    yield
    clear_join_limiters()
    clear_supplementary_rate_limiters_for_testing()


def _supplementary_settings(**kwargs: Any) -> Settings:
    data: dict[str, Any] = {
        "supabase_url": "https://example.supabase.co",
        "auth_allow_x_user_id_header": True,
        "households_join_rate_limit_enabled": False,
        "household_mutations_rate_limit_enabled": True,
        "household_mutations_user_per_minute": 2,
        "ai_rate_limit_enabled": True,
        "ai_rate_limit_ip_per_minute": 2,
        "trust_x_forwarded_for": False,
    }
    data.update(kwargs)
    return Settings(**data)


class _FakeHouseholdService:
    async def create_household(self, household, user_id, supabase_admin=None) -> HouseholdResponse:
        return HouseholdResponse(
            id=uuid4(),
            name=household.name,
            created_at="2024-01-01T00:00:00Z",
            invite_code="ABCD12",
            is_personal=bool(getattr(household, "is_personal", False)),
        )


def test_ai_ip_limit_returns_429() -> None:
    app.dependency_overrides[get_settings] = lambda: _supplementary_settings()
    try:
        client = TestClient(app)
        payload = {"text": "hello"}
        first = client.post("/api/ai/embeddings", json=payload)
        second = client.post("/api/ai/embeddings", json=payload)
        third = client.post("/api/ai/embeddings", json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert third.json()["error_code"] == "rate_limit_exceeded"
        assert third.headers.get("Retry-After") == "60"
    finally:
        app.dependency_overrides.clear()


def test_household_mutation_user_limit_returns_429() -> None:
    uid = "8b68f5fc-2660-4f80-a31e-58699bc2465d"
    app.dependency_overrides[get_settings] = lambda: _supplementary_settings(
        supabase_url=None,
    )
    app.dependency_overrides[get_household_service] = lambda: _FakeHouseholdService()
    try:
        client = TestClient(app)
        headers = {"x-user-id": uid}
        body = {"name": "Team", "is_personal": False}
        first = client.post("/api/households/create", json=body, headers=headers)
        second = client.post("/api/households/create", json=body, headers=headers)
        third = client.post("/api/households/create", json=body, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert third.json()["error_code"] == "rate_limit_exceeded"
    finally:
        app.dependency_overrides.clear()
