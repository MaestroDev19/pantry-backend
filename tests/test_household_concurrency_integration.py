"""Concurrent create/join integration tests with a thread-safe fake Supabase."""

from __future__ import annotations

import asyncio
import secrets
import string
import threading
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from postgrest.exceptions import APIError

from pantry_server.core.config import Settings, get_settings
from pantry_server.core.constants import INVITE_CODE_LENGTH, POSTGRES_UNIQUE_VIOLATION_CODE
from pantry_server.main import app
from pantry_server.middleware.household_join_rate_limit import _clear_for_testing
from pantry_server.shared.auth import get_current_user_id
from pantry_server.shared.dependencies import get_supabase_client


def _api_error_unique() -> APIError:
    payload = {"message": "duplicate", "code": POSTGRES_UNIQUE_VIOLATION_CODE}
    exc = APIError(payload)
    exc.args = (payload,)
    return exc


def _eq_val(filters: list[tuple[str, str]], column: str) -> str:
    for col, val in filters:
        if col == column:
            return val
    raise AssertionError(f"missing eq {column} in {filters}")


def _random_invite() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_CODE_LENGTH))


class _TableQuery:
    def __init__(self, fake: "ConcurrentFakeSupabase", table_name: str) -> None:
        self._fake = fake
        self._table = table_name
        self._op = "select"
        self._payload: dict[str, object] | None = None
        self._filters: list[tuple[str, str]] = []

    def select(self, _: str) -> _TableQuery:
        self._op = "select"
        return self

    def insert(self, payload: dict[str, object]) -> _TableQuery:
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, object]) -> _TableQuery:
        self._op = "update"
        self._payload = payload
        return self

    def delete(self) -> _TableQuery:
        self._op = "delete"
        return self

    def eq(self, column: str, value: str) -> _TableQuery:
        self._filters.append((column, value))
        return self

    def limit(self, _: int) -> _TableQuery:
        return self

    def execute(self) -> Any:
        return self._fake._table_execute(self._table, self._op, self._filters, self._payload)


class _RpcCall:
    def __init__(
        self,
        fake: "ConcurrentFakeSupabase",
        name: str,
        params: dict[str, object],
    ) -> None:
        self._fake = fake
        self._name = name
        self._params = params

    def execute(self) -> Any:
        return self._fake._rpc_execute(self._name, self._params)


class ConcurrentFakeSupabase:
    """Minimal thread-safe Supabase: household_members, households, join RPC."""

    def __init__(self, *, fixed_user_id: UUID, target_invite_code: str = "JOIN01") -> None:
        self._lock = threading.Lock()
        self.fixed_user_id = str(fixed_user_id)
        self._target_invite = target_invite_code.upper().strip()
        self._membership: dict[str, str] = {}
        self._households: dict[str, dict[str, Any]] = {}
        target_id = str(uuid4())
        self._join_target_household_id = target_id
        self._households[target_id] = {
            "id": target_id,
            "name": "Host household",
            "created_at": "2026-01-01T00:00:00Z",
            "invite_code": self._target_invite,
            "is_personal": False,
        }

    def table(self, table_name: str) -> _TableQuery:
        return _TableQuery(self, table_name)

    def rpc(self, name: str, params: dict[str, object]) -> _RpcCall:
        return _RpcCall(self, name, params)

    def _table_execute(
        self,
        table: str,
        op: str,
        filters: list[tuple[str, str]],
        payload: dict[str, object] | None,
    ) -> Any:
        if table == "household_members":
            if op == "select":
                uid = _eq_val(filters, "user_id")
                with self._lock:
                    if uid in self._membership:
                        return SimpleNamespace(data=[{"id": "member-1"}])
                    return SimpleNamespace(data=[])
            if op == "insert":
                assert payload is not None
                uid = str(payload["user_id"])
                hid = str(payload["household_id"])
                with self._lock:
                    if uid in self._membership:
                        raise _api_error_unique()
                    self._membership[uid] = hid
                    return SimpleNamespace(data=[{"id": "member-new"}])
        if table == "households":
            if op == "insert":
                assert payload is not None
                hid = str(uuid4())
                invite = str(payload.get("invite_code") or _random_invite())
                if len(invite) != INVITE_CODE_LENGTH:
                    invite = _random_invite()
                row = {
                    "id": hid,
                    "name": str(payload["name"]),
                    "created_at": "2026-01-02T00:00:00Z",
                    "invite_code": invite,
                    "is_personal": bool(payload.get("is_personal", False)),
                }
                if "owner_id" in payload:
                    row["owner_id"] = str(payload["owner_id"])
                with self._lock:
                    self._households[hid] = row
                    return SimpleNamespace(data=[row])
            if op == "delete":
                hid = _eq_val(filters, "id")
                with self._lock:
                    self._households.pop(hid, None)
                    return SimpleNamespace(data=[])
        raise AssertionError(f"unsupported {table=} {op=} {filters=}")

    def _rpc_execute(self, name: str, params: dict[str, object]) -> Any:
        if name != "join_household_by_invite_rpc":
            raise AssertionError(f"unexpected rpc {name}")
        code = str(params.get("invite_code", "")).upper().strip()
        assert str(params.get("p_user_id")) == str(self.fixed_user_id)
        uid = self.fixed_user_id
        with self._lock:
            if uid in self._membership:
                err = APIError({"message": "invalid invite code"})
                err.args = ({"message": "invalid invite code"},)
                raise err
            if code != self._target_invite:
                err = APIError({"message": "household not found"})
                err.args = ({"message": "household not found"},)
                raise err
            self._membership[uid] = self._join_target_household_id
            row = dict(self._households[self._join_target_household_id])
        return SimpleNamespace(
            data=[
                {
                    "household": row,
                    "items_moved": 0,
                },
            ],
        )


FIXED_USER = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")


def _concurrency_settings(**kwargs: Any) -> Settings:
    data: dict[str, Any] = {
        "supabase_url": "https://example.supabase.co",
        "supabase_service_role_key": "test-service-role",
        "households_join_rate_limit_enabled": False,
        "households_join_rate_limit_ip_per_minute": 0,
        "households_join_rate_limit_user_per_minute": 0,
        "household_mutations_rate_limit_enabled": False,
        "ai_rate_limit_enabled": False,
        "auth_allow_x_user_id_header": True,
    }
    data.update(kwargs)
    return Settings(**data)


@pytest.fixture(autouse=True)
def clear_join_limiters() -> None:
    _clear_for_testing()
    yield
    _clear_for_testing()


@pytest.mark.anyio
async def test_concurrent_non_personal_creates_single_membership_stable_statuses() -> None:
    fake = ConcurrentFakeSupabase(fixed_user_id=FIXED_USER)

    async def current_user() -> UUID:
        return FIXED_USER

    app.dependency_overrides[get_current_user_id] = current_user
    app.dependency_overrides[get_supabase_client] = lambda: fake
    app.dependency_overrides[get_settings] = lambda: _concurrency_settings()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            body = {"name": "Team A", "is_personal": False}

            async def post_create() -> int:
                r = await client.post(
                    "/api/households/create",
                    json=body,
                    headers={"x-user-id": str(FIXED_USER)},
                )
                return r.status_code

            a, b = await asyncio.gather(post_create(), post_create())

        assert {a, b} == {200, 400}
        assert len(fake._membership) == 1
        assert str(FIXED_USER) in fake._membership
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_concurrent_create_and_join_single_membership_stable_statuses() -> None:
    fake = ConcurrentFakeSupabase(fixed_user_id=FIXED_USER)

    async def current_user() -> UUID:
        return FIXED_USER

    app.dependency_overrides[get_current_user_id] = current_user
    app.dependency_overrides[get_supabase_client] = lambda: fake
    app.dependency_overrides[get_settings] = lambda: _concurrency_settings()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_body = {"name": "Team B", "is_personal": False}
            join_body = {"invite_code": "JOIN01"}

            async def post_create() -> int:
                return (
                    await client.post(
                        "/api/households/create",
                        json=create_body,
                        headers={"x-user-id": str(FIXED_USER)},
                    )
                ).status_code

            async def post_join() -> int:
                return (
                    await client.post(
                        "/api/households/join",
                        json=join_body,
                        headers={"x-user-id": str(FIXED_USER)},
                    )
                ).status_code

            a, b = await asyncio.gather(post_create(), post_join())

        assert {a, b} == {200, 400}
        assert len(fake._membership) == 1
        assert str(FIXED_USER) in fake._membership
    finally:
        app.dependency_overrides.clear()
