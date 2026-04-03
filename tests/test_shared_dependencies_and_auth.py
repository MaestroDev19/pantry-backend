from types import SimpleNamespace
from typing import Any
from uuid import UUID

import anyio
import pytest
from fastapi import status
from starlette.requests import Request

from pantry_server.core.config import Settings
from pantry_server.core.exceptions import AppError
from pantry_server.shared.auth import (
    _get_supabase_client_dep,
    get_current_household_id,
    get_current_user,
    get_current_user_id,
)
from pantry_server.shared.dependencies import get_supabase_client


def _run_get_current_user(**kwargs: Any):
    async def _run():
        return await get_current_user(**kwargs)

    return anyio.run(_run)


class _FakeSupabaseTableQuery:
    def __init__(self, response_data: list[dict[str, str]]) -> None:
        self._response_data = response_data

    def select(self, _: str) -> "_FakeSupabaseTableQuery":
        return self

    def eq(self, _: str, __: str) -> "_FakeSupabaseTableQuery":
        return self

    def limit(self, _: int) -> "_FakeSupabaseTableQuery":
        return self

    def execute(self):
        return SimpleNamespace(data=self._response_data)


class _FakeSupabaseClient:
    def __init__(self, user_obj=None, household_rows=None) -> None:
        self.auth = SimpleNamespace(get_user=lambda _: SimpleNamespace(user=user_obj))
        self._household_rows = household_rows if household_rows is not None else []

    def table(self, _: str) -> _FakeSupabaseTableQuery:
        return _FakeSupabaseTableQuery(self._household_rows)


def _request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_get_current_user_dev_header_returns_user_when_flag_set() -> None:
    uid = "8b68f5fc-2660-4f80-a31e-58699bc2465d"
    user = _run_get_current_user(
        settings=Settings(auth_allow_x_user_id_header=True),
        x_user_id=uid,
        credentials=None,
        supabase=None,
    )

    assert getattr(user, "id", None) == uid


def test_get_current_user_dev_header_invalid_uuid_raises() -> None:
    with pytest.raises(AppError) as exc_info:
        _run_get_current_user(
            settings=Settings(auth_allow_x_user_id_header=True),
            x_user_id="not-a-uuid",
            credentials=None,
            supabase=None,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_ignores_dev_header_when_flag_false() -> None:
    fake_supabase = _FakeSupabaseClient(user_obj=SimpleNamespace(id="8b68f5fc-2660-4f80-a31e-58699bc2465d"))
    credentials = SimpleNamespace(credentials="token")

    user = _run_get_current_user(
        settings=Settings(auth_allow_x_user_id_header=False),
        x_user_id="8b68f5fc-2660-4f80-a31e-58699bc2465d",
        credentials=credentials,
        supabase=fake_supabase,
    )

    assert getattr(user, "id", None) == "8b68f5fc-2660-4f80-a31e-58699bc2465d"


def test_get_supabase_client_returns_none_when_url_missing() -> None:
    settings = Settings(supabase_url=None)
    assert get_supabase_client(settings) is None


def test_get_supabase_client_uses_service_role_key_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pantry_server.shared.dependencies.create_client",
        lambda url, key: {"url": url, "key": key},
    )
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role",
    )

    client = get_supabase_client(settings)

    assert client == {"url": "https://example.supabase.co/", "key": "service-role"}


def test_get_supabase_client_returns_none_when_service_role_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pantry_server.shared.dependencies.create_client",
        lambda url, key: {"url": url, "key": key},
    )
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key=None,
        supabase_publishable_key="publishable",
    )

    assert get_supabase_client(settings) is None


def test_get_supabase_client_returns_none_when_only_anon_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pantry_server.shared.dependencies.create_client",
        lambda url, key: {"url": url, "key": key},
    )
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key=None,
        supabase_publishable_key=None,
        supabase_anon_key="anon",
    )

    assert get_supabase_client(settings) is None


def test_get_supabase_client_dep_raises_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pantry_server.shared.auth.get_supabase_client", lambda _: None)

    with pytest.raises(AppError) as exc_info:
        _get_supabase_client_dep(Settings())

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_get_current_user_raises_when_credentials_missing() -> None:
    fake_supabase = _FakeSupabaseClient(user_obj=SimpleNamespace(id="u1"))

    with pytest.raises(AppError) as exc_info:
        _run_get_current_user(
            settings=Settings(auth_allow_x_user_id_header=False),
            x_user_id=None,
            credentials=None,
            supabase=fake_supabase,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_returns_user_when_supabase_validates_token() -> None:
    fake_user = SimpleNamespace(id="8b68f5fc-2660-4f80-a31e-58699bc2465d")
    fake_supabase = _FakeSupabaseClient(user_obj=fake_user)
    credentials = SimpleNamespace(credentials="token")

    user = _run_get_current_user(
        settings=Settings(auth_allow_x_user_id_header=False),
        x_user_id=None,
        credentials=credentials,
        supabase=fake_supabase,
    )

    assert user is fake_user


def test_get_current_user_raises_when_supabase_auth_lookup_fails() -> None:
    class _FailingAuth:
        def get_user(self, _: str):
            raise RuntimeError("auth service down")

    fake_supabase = SimpleNamespace(auth=_FailingAuth())
    credentials = SimpleNamespace(credentials="token")

    with pytest.raises(AppError) as exc_info:
        _run_get_current_user(
            settings=Settings(auth_allow_x_user_id_header=False),
            x_user_id=None,
            credentials=credentials,
            supabase=fake_supabase,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_raises_when_user_not_found() -> None:
    fake_supabase = _FakeSupabaseClient(user_obj=None)
    credentials = SimpleNamespace(credentials="token")

    with pytest.raises(AppError) as exc_info:
        _run_get_current_user(
            settings=Settings(auth_allow_x_user_id_header=False),
            x_user_id=None,
            credentials=credentials,
            supabase=fake_supabase,
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_raises_when_supabase_unconfigured_and_no_dev_header() -> None:
    with pytest.raises(AppError) as exc_info:
        _run_get_current_user(
            settings=Settings(auth_allow_x_user_id_header=False),
            x_user_id=None,
            credentials=SimpleNamespace(credentials="token"),
            supabase=None,
        )

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_get_current_user_id_sets_request_state_and_returns_uuid() -> None:
    request = _request()
    user = SimpleNamespace(id="8b68f5fc-2660-4f80-a31e-58699bc2465d")

    user_id = anyio.run(get_current_user_id, request, user)

    assert isinstance(user_id, UUID)
    assert request.state.user_id == "8b68f5fc-2660-4f80-a31e-58699bc2465d"


def test_get_current_user_id_raises_for_invalid_user_id() -> None:
    request = _request()
    user = SimpleNamespace(id="not-a-uuid")

    with pytest.raises(AppError) as exc_info:
        anyio.run(get_current_user_id, request, user)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_id_raises_when_user_id_missing() -> None:
    request = _request()
    user = SimpleNamespace(id=None)

    with pytest.raises(AppError) as exc_info:
        anyio.run(get_current_user_id, request, user)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_household_id_returns_household_uuid() -> None:
    fake_supabase = _FakeSupabaseClient(
        household_rows=[{"household_id": "f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a"}]
    )
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    household_id = anyio.run(get_current_household_id, user_id, fake_supabase)

    assert household_id == UUID("f8c2ce57-d0ac-4d8d-96f8-6c4a1844091a")


def test_get_current_household_id_raises_when_user_has_no_membership() -> None:
    fake_supabase = _FakeSupabaseClient(household_rows=[])
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(get_current_household_id, user_id, fake_supabase)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_get_current_household_id_raises_when_supabase_query_fails() -> None:
    class _FailingSupabaseClient:
        def table(self, _: str):
            raise RuntimeError("db down")

    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(get_current_household_id, user_id, _FailingSupabaseClient())

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
