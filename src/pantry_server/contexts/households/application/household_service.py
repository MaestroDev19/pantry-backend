from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime
from typing import Any
from uuid import UUID

import anyio
from fastapi import status
from postgrest.exceptions import APIError
from supabase import Client

from pantry_server.contexts.households.domain.models import (
    HouseholdCreate,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
    HouseholdResponse,
)
from pantry_server.core.constants import (
    INVITE_CODE_LENGTH,
    POSTGRES_UNIQUE_VIOLATION_CODE,
)
from pantry_server.core.datetime_formatting import format_iso_datetime
from pantry_server.core.exceptions import AppError
from pantry_server.observability.logging_events import log_household_event
from pantry_server.observability.metrics import record_household_outcome
from pantry_server.observability.redact import redact_for_log

logger = logging.getLogger("pantry_server.household_service")


def _emit_household(*, operation: str, outcome: str, reason: str) -> None:
    record_household_outcome(operation=operation, outcome=outcome, reason=reason)
    log_household_event(logger, operation=operation, outcome=outcome, reason=reason)


def _iso_now() -> str:
    return format_iso_datetime(value=datetime.now())


def _generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_CODE_LENGTH))


def _response_has_data(response: Any) -> bool:
    data = getattr(response, "data", None)
    return bool(data) and len(data) > 0


def _first_row(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None) or []
    return data[0] if data else {}


def _row_to_household_response(row: dict[str, Any]) -> HouseholdResponse:
    return HouseholdResponse(
        id=UUID(row["id"]),
        name=row["name"],
        created_at=row["created_at"],
        invite_code=row["invite_code"],
        is_personal=row.get("is_personal", False),
    )


class HouseholdService:
    def __init__(self, supabase: Client) -> None:
        self.supabase = supabase

    async def create_household(
        self,
        household: HouseholdCreate,
        user_id: UUID,
        supabase_admin: Client | None = None,
    ) -> HouseholdResponse:
        client = supabase_admin if supabase_admin is not None else self.supabase
        is_personal = bool(getattr(household, "is_personal", False))

        membership_response = await anyio.to_thread.run_sync(
            lambda: (
                client.table("household_members")
                .select("id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            ),
        )
        if _response_has_data(membership_response):
            _emit_household(operation="create", outcome="failure", reason="already_member")
            raise AppError(
                "User is already a member of a household",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if is_personal:
            existing_personal = await anyio.to_thread.run_sync(
                lambda: (
                    client.table("households")
                    .select("id, name, invite_code, is_personal, created_at")
                    .eq("owner_id", str(user_id))
                    .eq("is_personal", True)
                    .limit(1)
                    .execute()
                ),
            )
            if _response_has_data(existing_personal):
                row = _row_to_household_response(_first_row(existing_personal))
                _emit_household(operation="create", outcome="success", reason="ok")
                return row

        payload: dict[str, object] = {
            "name": household.name,
            "invite_code": _generate_invite_code(),
        }
        if is_personal:
            payload["is_personal"] = True
            payload["owner_id"] = str(user_id)

        try:
            household_response = await anyio.to_thread.run_sync(
                lambda: client.table("households").insert(payload).execute(),
            )
        except APIError as exc:
            details = exc.args[0] if exc.args else {}
            code = details.get("code") if isinstance(details, dict) else None

            if code == POSTGRES_UNIQUE_VIOLATION_CODE and is_personal:
                existing = await anyio.to_thread.run_sync(
                    lambda: (
                        client.table("households")
                        .select("id, name, invite_code, is_personal, created_at")
                        .eq("owner_id", str(user_id))
                        .eq("is_personal", True)
                        .limit(1)
                        .execute()
                    ),
                )
                if _response_has_data(existing):
                    row = _row_to_household_response(_first_row(existing))
                    _emit_household(operation="create", outcome="success", reason="ok")
                    return row

            logger.error(
                "Failed to create household",
                extra={
                    "event": "household_error",
                    "operation": "create",
                    "error": redact_for_log(details),
                },
            )
            _emit_household(operation="create", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to create household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        if not _response_has_data(household_response):
            _emit_household(operation="create", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to create household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not is_personal:
            household_id = str(household_response.data[0]["id"])
            try:
                await anyio.to_thread.run_sync(
                    lambda: (
                        client.table("household_members")
                        .insert(
                            {
                                "user_id": str(user_id),
                                "household_id": household_id,
                                "joined_at": _iso_now(),
                            },
                        )
                        .execute()
                    ),
                )
            except APIError as exc:
                details = exc.args[0] if exc.args else {}
                code = details.get("code") if isinstance(details, dict) else None
                if code == POSTGRES_UNIQUE_VIOLATION_CODE:
                    await anyio.to_thread.run_sync(
                        lambda: client.table("households").delete().eq("id", household_id).execute(),
                    )
                    _emit_household(operation="create", outcome="failure", reason="already_member")
                    raise AppError(
                        "User is already a member of a household",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    ) from exc
                _emit_household(operation="create", outcome="failure", reason="server_error")
                raise AppError(
                    "Failed to create household",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                ) from exc

        row = _row_to_household_response(_first_row(household_response))
        _emit_household(operation="create", outcome="success", reason="ok")
        return row

    async def join_household_by_invite(
        self,
        invite_code: str,
        user_id: UUID,
    ) -> HouseholdJoinResponse:
        code = invite_code.upper().strip()
        if not code or len(code) != INVITE_CODE_LENGTH:
            _emit_household(operation="join", outcome="failure", reason="invalid_invite")
            raise AppError(
                "Invalid invite code",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rpc_response = await anyio.to_thread.run_sync(
                lambda: self.supabase.rpc(
                    "join_household_by_invite_rpc",
                    {"invite_code": code},
                ).execute(),
            )
        except APIError as exc:
            details = exc.args[0] if exc.args else {}
            message = details.get("message") if isinstance(details, dict) else None
            if message == "household not found":
                _emit_household(operation="join", outcome="failure", reason="not_found")
                raise AppError(
                    "Household not found for this invite code",
                    status_code=status.HTTP_404_NOT_FOUND,
                ) from exc
            if message in {
                "invalid invite code",
                "cannot join a personal household via invite code",
                "user is not in any household",
            }:
                _emit_household(operation="join", outcome="failure", reason="bad_request")
                raise AppError(
                    message.replace(
                        "user is not in any household",
                        "User is not in any household",
                    ).capitalize(),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
            _emit_household(operation="join", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to join household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        payload = getattr(rpc_response, "data", None)
        if isinstance(payload, list):
            payload = payload[0] if payload else None
        if not isinstance(payload, dict):
            _emit_household(operation="join", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to join household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        household_raw = payload.get("household")
        if not isinstance(household_raw, dict):
            _emit_household(operation="join", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to join household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        items_moved = payload.get("items_moved", 0)
        if not isinstance(items_moved, int):
            items_moved = 0

        result = HouseholdJoinResponse(
            household=_row_to_household_response(household_raw),
            items_moved=items_moved,
        )
        _emit_household(operation="join", outcome="success", reason="ok")
        return result

    async def leave_household(self, user_id: UUID) -> HouseholdLeaveResponse:
        membership = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            ),
        )
        if not _response_has_data(membership):
            _emit_household(operation="leave", outcome="failure", reason="not_in_household")
            raise AppError(
                "User is not in any household",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        household_id = str(_first_row(membership)["household_id"])
        household_lookup = await anyio.to_thread.run_sync(
            lambda: (
                self.supabase.table("households")
                .select("is_personal")
                .eq("id", household_id)
                .limit(1)
                .execute()
            ),
        )
        if not _response_has_data(household_lookup):
            _emit_household(operation="leave", outcome="failure", reason="household_not_found")
            raise AppError(
                "Household not found",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if bool(_first_row(household_lookup).get("is_personal")):
            _emit_household(operation="leave", outcome="failure", reason="personal_household")
            raise AppError(
                "You cannot leave a personal household",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rpc_response = await anyio.to_thread.run_sync(
                lambda: self.supabase.rpc("leave_household_rpc", {}).execute(),
            )
        except APIError as exc:
            details = exc.args[0] if exc.args else {}
            message = details.get("message") if isinstance(details, dict) else None
            if message in {
                "user is not in any household",
                "already in personal household",
                "you cannot leave a personal household",
            }:
                _emit_household(operation="leave", outcome="failure", reason="bad_request")
                if message == "user is not in any household":
                    detail = "User is not in any household"
                else:
                    detail = "You cannot leave a personal household"
                raise AppError(
                    detail,
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc
            _emit_household(operation="leave", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to leave household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        payload = getattr(rpc_response, "data", None)
        if isinstance(payload, list):
            payload = payload[0] if payload else None
        if not isinstance(payload, dict):
            _emit_household(operation="leave", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to leave household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        new_household_id_raw = payload.get("new_household_id")
        new_household_name = payload.get("new_household_name")
        items_moved = payload.get("items_moved", 0)

        try:
            new_household_id = UUID(new_household_id_raw) if new_household_id_raw else None
        except (TypeError, ValueError) as exc:
            _emit_household(operation="leave", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to leave household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        if not isinstance(items_moved, int):
            items_moved = 0

        result = HouseholdLeaveResponse(
            message="Left household and switched to personal household",
            items_deleted=items_moved,
            new_household_id=new_household_id,
            new_household_name=str(new_household_name) if new_household_name is not None else None,
        )
        _emit_household(operation="leave", outcome="success", reason="ok")
        return result

    async def convert_personal_to_joinable(
        self,
        user_id: UUID,
        supabase_admin: Client,
        name: str | None = None,
    ) -> HouseholdResponse:
        membership = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            ),
        )
        if not _response_has_data(membership):
            _emit_household(operation="convert", outcome="failure", reason="not_in_household")
            raise AppError(
                "User is not in any household",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        household_id = UUID(_first_row(membership)["household_id"])

        household = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, invite_code, is_personal, created_at, owner_id")
                .eq("id", str(household_id))
                .limit(1)
                .execute()
            ),
        )
        if not _response_has_data(household):
            _emit_household(operation="convert", outcome="failure", reason="not_found")
            raise AppError(
                "Household not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        row = _first_row(household)
        if not row.get("is_personal"):
            _emit_household(operation="convert", outcome="failure", reason="already_joinable")
            raise AppError(
                "Household is already joinable; only personal households can be converted",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if str(row.get("owner_id")) != str(user_id):
            _emit_household(operation="convert", outcome="failure", reason="forbidden")
            raise AppError(
                "Only the household owner can convert it to joinable",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        update_payload: dict[str, object] = {"is_personal": False}
        if name is not None and name.strip():
            update_payload["name"] = name.strip()

        updated = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .update(update_payload)
                .eq("id", str(household_id))
                .execute()
            ),
        )
        if not _response_has_data(updated):
            _emit_household(operation="convert", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to update household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        row = _row_to_household_response(_first_row(updated))
        _emit_household(operation="convert", outcome="success", reason="ok")
        return row

    async def rename_household(
        self,
        user_id: UUID,
        supabase_admin: Client,
        name: str,
    ) -> HouseholdResponse:
        new_name = name.strip()
        if not new_name:
            _emit_household(operation="rename", outcome="failure", reason="bad_request")
            raise AppError(
                "Household name cannot be empty",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        membership = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            ),
        )
        if not _response_has_data(membership):
            _emit_household(operation="rename", outcome="failure", reason="not_in_household")
            raise AppError(
                "User is not in any household",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        household_id = UUID(_first_row(membership)["household_id"])

        household = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .select("id, name, invite_code, is_personal, created_at, owner_id")
                .eq("id", str(household_id))
                .limit(1)
                .execute()
            ),
        )
        if not _response_has_data(household):
            _emit_household(operation="rename", outcome="failure", reason="not_found")
            raise AppError(
                "Household not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        row = _first_row(household)
        if row.get("is_personal") and str(row.get("owner_id")) != str(user_id):
            _emit_household(operation="rename", outcome="failure", reason="forbidden")
            raise AppError(
                "Only the household owner can rename a personal household",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        updated = await anyio.to_thread.run_sync(
            lambda: (
                supabase_admin.table("households")
                .update({"name": new_name})
                .eq("id", str(household_id))
                .execute()
            ),
        )
        if not _response_has_data(updated):
            _emit_household(operation="rename", outcome="failure", reason="server_error")
            raise AppError(
                "Failed to update household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        result = _row_to_household_response(_first_row(updated))
        _emit_household(operation="rename", outcome="success", reason="ok")
        return result


__all__ = [
    "HouseholdService",
]
