from types import SimpleNamespace
from uuid import UUID

import anyio
import pytest
from postgrest.exceptions import APIError

from pantry_server.contexts.households.application.household_service import (
    HouseholdService,
    _first_row,
    _generate_invite_code,
    _response_has_data,
    _row_to_household_response,
)
from pantry_server.contexts.households.domain.models import HouseholdCreate
from pantry_server.core.constants import INVITE_CODE_LENGTH, POSTGRES_UNIQUE_VIOLATION_CODE
from pantry_server.core.exceptions import AppError


class _FakeQuery:
    def __init__(self, client: "_FakeSupabaseClient", table_name: str) -> None:
        self._client = client
        self._table_name = table_name
        self._op = "select"

    def select(self, _: str) -> "_FakeQuery":
        self._op = "select"
        return self

    def eq(self, _: str, __: str) -> "_FakeQuery":
        return self

    def limit(self, _: int) -> "_FakeQuery":
        return self

    def insert(self, __: dict[str, object]) -> "_FakeQuery":
        self._op = "insert"
        return self

    def update(self, __: dict[str, object]) -> "_FakeQuery":
        self._op = "update"
        return self

    def delete(self) -> "_FakeQuery":
        self._op = "delete"
        return self

    def execute(self):
        return self._client.pop(self._table_name, self._op)


class _FakeRpcCall:
    def __init__(self, client: "_FakeSupabaseClient", rpc_name: str) -> None:
        self._client = client
        self._rpc_name = rpc_name

    def execute(self):
        return self._client.pop_rpc(self._rpc_name)


class _FakeSupabaseClient:
    def __init__(
        self,
        table_results: dict[tuple[str, str], list[object]] | None = None,
        rpc_results: dict[str, list[object]] | None = None,
    ) -> None:
        self._table_results = table_results or {}
        self._rpc_results = rpc_results or {}

    def table(self, table_name: str) -> _FakeQuery:
        return _FakeQuery(self, table_name)

    def rpc(self, name: str, _: dict[str, object]) -> _FakeRpcCall:
        return _FakeRpcCall(self, name)

    def pop(self, table_name: str, op: str):
        key = (table_name, op)
        queue = self._table_results.get(key, [])
        if not queue:
            return SimpleNamespace(data=[])
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def pop_rpc(self, rpc_name: str):
        queue = self._rpc_results.get(rpc_name, [])
        if not queue:
            return SimpleNamespace(data=None)
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _api_error(message: str, code: str | None = None) -> APIError:
    payload: dict[str, str] = {"message": message}
    if code is not None:
        payload["code"] = code
    error = APIError(payload)
    error.args = (payload,)
    return error


def test_generate_invite_code_has_expected_shape() -> None:
    code = _generate_invite_code()

    assert len(code) == INVITE_CODE_LENGTH
    assert code.isalnum()
    assert code == code.upper()


def test_response_has_data_and_first_row_helpers() -> None:
    populated = SimpleNamespace(data=[{"id": "a"}])
    empty = SimpleNamespace(data=[])
    missing = SimpleNamespace()

    assert _response_has_data(populated) is True
    assert _response_has_data(empty) is False
    assert _response_has_data(missing) is False
    assert _first_row(populated) == {"id": "a"}
    assert _first_row(empty) == {}


def test_row_to_household_response_maps_values() -> None:
    row = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "Home",
        "created_at": "2026-01-01T10:00:00",
        "invite_code": "ABC123",
        "is_personal": True,
    }

    mapped = _row_to_household_response(row)

    assert mapped.id == UUID("6ef281de-53a8-47a8-8e19-2f9d4ac4f39b")
    assert mapped.name == "Home"
    assert mapped.invite_code == "ABC123"
    assert mapped.is_personal is True


def test_create_household_rejects_when_user_already_has_membership() -> None:
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[{"id": "member-1"}])],
        }
    )
    service = HouseholdService(client)
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.create_household, HouseholdCreate(name="Team"), user_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "User is already a member of a household"


def test_create_household_returns_existing_personal_household() -> None:
    existing = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "My Household",
        "created_at": "2026-01-01T10:00:00",
        "invite_code": "ABC123",
        "is_personal": True,
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[])],
            ("households", "select"): [SimpleNamespace(data=[existing])],
        }
    )
    service = HouseholdService(client)
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    result = anyio.run(
        service.create_household,
        HouseholdCreate(name="My Household", is_personal=True),
        user_id,
    )

    assert result.id == UUID(existing["id"])
    assert result.is_personal is True


def test_create_household_maps_unique_violation_for_membership_insert() -> None:
    created = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "Team",
        "created_at": "2026-01-01T10:00:00",
        "invite_code": "ABC123",
        "is_personal": False,
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[])],
            ("households", "insert"): [SimpleNamespace(data=[created])],
            ("household_members", "insert"): [
                _api_error("duplicate member", code=POSTGRES_UNIQUE_VIOLATION_CODE)
            ],
            ("households", "delete"): [SimpleNamespace(data=[{"id": created["id"]}])],
        }
    )
    service = HouseholdService(client)
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.create_household, HouseholdCreate(name="Team"), user_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "User is already a member of a household"


def test_join_household_by_invite_rejects_invalid_code() -> None:
    service = HouseholdService(_FakeSupabaseClient())
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.join_household_by_invite, "abc", user_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "Invalid invite code"


def test_join_household_by_invite_maps_not_found_api_error() -> None:
    client = _FakeSupabaseClient(
        rpc_results={
            "join_household_by_invite_rpc": [_api_error("household not found")],
        }
    )
    service = HouseholdService(client)
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.join_household_by_invite, "ABC123", user_id)

    assert exc_info.value.status_code == 404


def test_leave_household_returns_mapped_response_on_success() -> None:
    client = _FakeSupabaseClient(
        rpc_results={
            "leave_household_rpc": [
                SimpleNamespace(
                    data={
                        "new_household_id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
                        "new_household_name": "My Household",
                        "items_moved": 5,
                    }
                )
            ],
        }
    )
    service = HouseholdService(client)
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    result = anyio.run(service.leave_household, user_id)

    assert result.new_household_id == UUID("6ef281de-53a8-47a8-8e19-2f9d4ac4f39b")
    assert result.new_household_name == "My Household"
    assert result.items_deleted == 5


def test_convert_personal_to_joinable_rejects_when_household_not_personal() -> None:
    member_row = {"household_id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b"}
    household_row = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "Team",
        "invite_code": "ABC123",
        "is_personal": False,
        "created_at": "2026-01-01T10:00:00",
        "owner_id": "8b68f5fc-2660-4f80-a31e-58699bc2465d",
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[member_row])],
            ("households", "select"): [SimpleNamespace(data=[household_row])],
        }
    )
    service = HouseholdService(client)
    user_id = UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d")

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.convert_personal_to_joinable, user_id, client, None)

    assert exc_info.value.status_code == 400


def test_create_household_personal_sets_owner_and_returns_created_row() -> None:
    created = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "My Household",
        "created_at": "2026-01-01T10:00:00",
        "invite_code": "ABC123",
        "is_personal": True,
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[])],
            ("households", "select"): [SimpleNamespace(data=[])],
            ("households", "insert"): [SimpleNamespace(data=[created])],
        }
    )
    service = HouseholdService(client)

    result = anyio.run(
        service.create_household,
        HouseholdCreate(name="My Household", is_personal=True),
        UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
    )

    assert result.is_personal is True
    assert result.name == "My Household"


def test_create_household_handles_personal_unique_violation_by_returning_existing() -> None:
    existing = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "My Household",
        "created_at": "2026-01-01T10:00:00",
        "invite_code": "ABC123",
        "is_personal": True,
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[])],
            ("households", "select"): [
                SimpleNamespace(data=[]),
                SimpleNamespace(data=[existing]),
            ],
            ("households", "insert"): [
                _api_error("duplicate", code=POSTGRES_UNIQUE_VIOLATION_CODE)
            ],
        }
    )
    service = HouseholdService(client)

    result = anyio.run(
        service.create_household,
        HouseholdCreate(name="My Household", is_personal=True),
        UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
    )

    assert result.id == UUID(existing["id"])


def test_create_household_raises_when_insert_returns_no_data() -> None:
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[])],
            ("households", "insert"): [SimpleNamespace(data=[])],
        }
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.create_household,
            HouseholdCreate(name="Team"),
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
        )

    assert exc_info.value.status_code == 500


def test_join_household_by_invite_maps_known_bad_request_messages() -> None:
    client = _FakeSupabaseClient(
        rpc_results={
            "join_household_by_invite_rpc": [_api_error("cannot join a personal household via invite code")],
        }
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.join_household_by_invite,
            "ABC123",
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
        )

    assert exc_info.value.status_code == 400


def test_join_household_by_invite_raises_on_non_dict_payload() -> None:
    client = _FakeSupabaseClient(
        rpc_results={"join_household_by_invite_rpc": [SimpleNamespace(data=["not-a-dict"])]}
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.join_household_by_invite,
            "ABC123",
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
        )

    assert exc_info.value.status_code == 500


def test_join_household_by_invite_defaults_items_moved_when_not_int() -> None:
    payload = {
        "household": {
            "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
            "name": "Team",
            "created_at": "2026-01-01T10:00:00",
            "invite_code": "ABC123",
            "is_personal": False,
        },
        "items_moved": "five",
    }
    client = _FakeSupabaseClient(
        rpc_results={"join_household_by_invite_rpc": [SimpleNamespace(data=payload)]}
    )
    service = HouseholdService(client)

    result = anyio.run(
        service.join_household_by_invite,
        "ABC123",
        UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
    )

    assert result.items_moved == 0


def test_leave_household_maps_known_bad_request_messages() -> None:
    client = _FakeSupabaseClient(
        rpc_results={"leave_household_rpc": [_api_error("already in personal household")]}
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.leave_household, UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"))

    assert exc_info.value.status_code == 400


def test_leave_household_raises_when_payload_is_not_dict() -> None:
    client = _FakeSupabaseClient(rpc_results={"leave_household_rpc": [SimpleNamespace(data=None)]})
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.leave_household, UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"))

    assert exc_info.value.status_code == 500


def test_leave_household_raises_when_new_household_id_is_invalid() -> None:
    client = _FakeSupabaseClient(
        rpc_results={
            "leave_household_rpc": [
                SimpleNamespace(
                    data={
                        "new_household_id": "invalid-uuid",
                        "new_household_name": "My Household",
                        "items_moved": 2,
                    }
                )
            ],
        }
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(service.leave_household, UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"))

    assert exc_info.value.status_code == 500


def test_leave_household_defaults_items_deleted_when_not_int() -> None:
    client = _FakeSupabaseClient(
        rpc_results={
            "leave_household_rpc": [
                SimpleNamespace(
                    data={
                        "new_household_id": None,
                        "new_household_name": None,
                        "items_moved": "bad",
                    }
                )
            ],
        }
    )
    service = HouseholdService(client)

    result = anyio.run(service.leave_household, UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"))

    assert result.items_deleted == 0


def test_convert_personal_to_joinable_raises_when_no_membership() -> None:
    client = _FakeSupabaseClient(table_results={("household_members", "select"): [SimpleNamespace(data=[])]})
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.convert_personal_to_joinable,
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            client,
            None,
        )

    assert exc_info.value.status_code == 400


def test_convert_personal_to_joinable_raises_when_household_missing() -> None:
    member_row = {"household_id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b"}
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[member_row])],
            ("households", "select"): [SimpleNamespace(data=[])],
        }
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.convert_personal_to_joinable,
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            client,
            None,
        )

    assert exc_info.value.status_code == 404


def test_convert_personal_to_joinable_raises_when_user_not_owner() -> None:
    member_row = {"household_id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b"}
    household_row = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "My Household",
        "invite_code": "ABC123",
        "is_personal": True,
        "created_at": "2026-01-01T10:00:00",
        "owner_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[member_row])],
            ("households", "select"): [SimpleNamespace(data=[household_row])],
        }
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.convert_personal_to_joinable,
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            client,
            None,
        )

    assert exc_info.value.status_code == 403


def test_convert_personal_to_joinable_raises_when_update_returns_no_data() -> None:
    member_row = {"household_id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b"}
    household_row = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "My Household",
        "invite_code": "ABC123",
        "is_personal": True,
        "created_at": "2026-01-01T10:00:00",
        "owner_id": "8b68f5fc-2660-4f80-a31e-58699bc2465d",
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[member_row])],
            ("households", "select"): [SimpleNamespace(data=[household_row])],
            ("households", "update"): [SimpleNamespace(data=[])],
        }
    )
    service = HouseholdService(client)

    with pytest.raises(AppError) as exc_info:
        anyio.run(
            service.convert_personal_to_joinable,
            UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
            client,
            " Team Household ",
        )

    assert exc_info.value.status_code == 500


def test_convert_personal_to_joinable_success() -> None:
    member_row = {"household_id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b"}
    household_row = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "My Household",
        "invite_code": "ABC123",
        "is_personal": True,
        "created_at": "2026-01-01T10:00:00",
        "owner_id": "8b68f5fc-2660-4f80-a31e-58699bc2465d",
    }
    updated_row = {
        "id": "6ef281de-53a8-47a8-8e19-2f9d4ac4f39b",
        "name": "Team Household",
        "invite_code": "ABC123",
        "is_personal": False,
        "created_at": "2026-01-01T10:00:00",
    }
    client = _FakeSupabaseClient(
        table_results={
            ("household_members", "select"): [SimpleNamespace(data=[member_row])],
            ("households", "select"): [SimpleNamespace(data=[household_row])],
            ("households", "update"): [SimpleNamespace(data=[updated_row])],
        }
    )
    service = HouseholdService(client)

    result = anyio.run(
        service.convert_personal_to_joinable,
        UUID("8b68f5fc-2660-4f80-a31e-58699bc2465d"),
        client,
        " Team Household ",
    )

    assert result.is_personal is False
    assert result.name == "Team Household"
