from __future__ import annotations

import httpx
import pytest

from pantry_backend import app
from pantry_backend.core.settings import get_settings


@pytest.mark.anyio
async def test_health_is_ok() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readiness_reflects_supabase_configuration() -> None:
    settings = get_settings()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    body = response.json()

    is_configured = (
        settings.supabase_url is not None
        and (
            settings.supabase_service_role_key
            or settings.supabase_publishable_key
            or settings.supabase_anon_key
        )
    )

    assert body["integrations"]["supabase"]["configured"] is bool(is_configured)

