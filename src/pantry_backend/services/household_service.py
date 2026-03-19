from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import anyio
from fastapi import status
from postgrest.exceptions import APIError
from supabase import Client

from pantry_backend.core.exceptions import AppError
from pantry_backend.models.household import (
    HouseholdCreate,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
    HouseholdResponse,
)
from pantry_backend.utils.constants import (
    DEFAULT_PERSONAL_HOUSEHOLD_NAME,
    INVITE_CODE_LENGTH,
    MAX_INVITE_CODE_RETRIES,
    POSTGRES_UNIQUE_VIOLATION_CODE,
)
from pantry_backend.utils.date_time_styling import format_iso_datetime


logger = logging.getLogger("pantry_backend.household_service")


def _iso_now() -> str:
    return format_iso_datetime(value=datetime.now())


def _generate_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_CODE_LENGTH))


def _response_has_data(response: Any) -> bool:
    data = getattr(response, "data", None)
    return bool(data) and len(data) > 0


def _first_row(response: Any) -> Dict[str, Any]:
    data = getattr(response, "data", None) or []
    return data[0] if data else {}


def _row_to_household_response(row: Dict[str, Any]) -> HouseholdResponse:
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
        supabase_admin: Optional[Client] = None,
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
            logger.error(
                "Create household rejected: user already in a household",
                extra={"user_id": str(user_id)},
            )
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
                row = _first_row(existing_personal)
                logger.info(
                    "Reusing existing personal household for user",
                    extra={"user_id": str(user_id), "household_id": row["id"]},
                )
                return _row_to_household_response(row)

        payload: Dict[str, object] = {
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
                    row = _first_row(existing)
                    logger.info(
                        "Personal household unique constraint hit, reusing existing",
                        extra={"user_id": str(user_id), "household_id": row["id"]},
                    )
                    return _row_to_household_response(row)

            logger.error(
                "Failed to create household (APIError)",
                extra={"user_id": str(user_id), "error": details},
            )
            raise AppError(
                "Failed to create household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        if not _response_has_data(household_response):
            logger.error(
                "Failed to create household (no data from insert)",
                extra={"user_id": str(user_id)},
            )
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
                        lambda: client.table("households")
                        .delete()
                        .eq("id", household_id)
                        .execute(),
                    )
                    logger.error(
                        "Create household rejected: membership unique constraint after household insert",
                        extra={
                            "user_id": str(user_id),
                            "household_id": household_id,
                            "error": details,
                        },
                    )
                    raise AppError(
                        "User is already a member of a household",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    ) from exc

                logger.error(
                    "Failed to create household member row (APIError)",
                    extra={
                        "user_id": str(user_id),
                        "household_id": household_id,
                        "error": details,
                    },
                )
                raise AppError(
                    "Failed to create household",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                ) from exc

        out = _row_to_household_response(_first_row(household_response))
        logger.info(
            "Household created",
            extra={"user_id": str(user_id), "household_id": str(out.id)},
        )
        return out

    async def join_household_by_invite(
        self,
        invite_code: str,
        user_id: UUID,
    ) -> HouseholdJoinResponse:
        code = invite_code.upper().strip()
        if not code or len(code) != INVITE_CODE_LENGTH:
            logger.error(
                "Invalid invite code",
                extra={"user_id": str(user_id)},
            )
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
            logger.error(
                "Join household RPC failed (APIError)",
                extra={"user_id": str(user_id), "invite_code": code, "error": details},
            )

            if message == "household not found":
                raise AppError(
                    "Household not found for this invite code",
                    status_code=status.HTTP_404_NOT_FOUND,
                ) from exc
            if message in {
                "invalid invite code",
                "cannot join a personal household via invite code",
                "user is not in any household",
            }:
                raise AppError(
                    message.replace(
                        "user is not in any household",
                        "User is not in any household",
                    ).capitalize(),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc

            raise AppError(
                "Failed to join household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        payload = getattr(rpc_response, "data", None)
        if isinstance(payload, list):
            payload = payload[0] if payload else None
        if not isinstance(payload, dict):
            logger.error(
                "Join household RPC returned unexpected payload",
                extra={
                    "user_id": str(user_id),
                    "invite_code": code,
                    "payload_type": str(type(payload)),
                },
            )
            raise AppError(
                "Failed to join household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        household_raw = payload.get("household")
        if not isinstance(household_raw, dict):
            logger.error(
                "Join household RPC missing household payload",
                extra={"user_id": str(user_id), "invite_code": code, "payload": payload},
            )
            raise AppError(
                "Failed to join household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        items_moved = payload.get("items_moved", 0)
        if not isinstance(items_moved, int):
            items_moved = 0

        return HouseholdJoinResponse(
            household=_row_to_household_response(household_raw),
            items_moved=items_moved,
        )

    async def leave_household(self, user_id: UUID) -> HouseholdLeaveResponse:
        try:
            rpc_response = await anyio.to_thread.run_sync(
                lambda: self.supabase.rpc("leave_household_rpc", {}).execute(),
            )
        except APIError as exc:
            details = exc.args[0] if exc.args else {}
            message = details.get("message") if isinstance(details, dict) else None
            logger.error(
                "Leave household RPC failed (APIError)",
                extra={"user_id": str(user_id), "error": details},
            )

            if message in {
                "user is not in any household",
                "already in personal household",
            }:
                raise AppError(
                    message.replace(
                        "user is not in any household",
                        "User is not in any household",
                    ).capitalize(),
                    status_code=status.HTTP_400_BAD_REQUEST,
                ) from exc

            raise AppError(
                "Failed to leave household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        payload = getattr(rpc_response, "data", None)
        if isinstance(payload, list):
            payload = payload[0] if payload else None
        if not isinstance(payload, dict):
            logger.error(
                "Leave household RPC returned unexpected payload",
                extra={"user_id": str(user_id), "payload_type": str(type(payload))},
            )
            raise AppError(
                "Failed to leave household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        new_household_id_raw = payload.get("new_household_id")
        new_household_name = payload.get("new_household_name")
        items_moved = payload.get("items_moved", 0)

        try:
            new_household_id = (
                UUID(new_household_id_raw) if new_household_id_raw else None
            )
        except (TypeError, ValueError) as exc:
            logger.error(
                "Leave household RPC returned invalid new_household_id",
                extra={
                    "user_id": str(user_id),
                    "new_household_id": new_household_id_raw,
                },
            )
            raise AppError(
                "Failed to leave household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        if not isinstance(items_moved, int):
            items_moved = 0

        return HouseholdLeaveResponse(
            message="Left household and switched to personal household",
            items_deleted=items_moved,
            new_household_id=new_household_id,
            new_household_name=str(new_household_name)
            if new_household_name is not None
            else None,
        )

    async def convert_personal_to_joinable(
        self,
        user_id: UUID,
        supabase_admin: Client,
        name: Optional[str] = None,
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
            logger.error(
                "Convert to joinable: user not in any household",
                extra={"user_id": str(user_id)},
            )
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
            logger.error(
                "Convert to joinable: household not found",
                extra={
                    "user_id": str(user_id),
                    "household_id": str(household_id),
                },
            )
            raise AppError(
                "Household not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        row = _first_row(household)
        if not row.get("is_personal"):
            logger.error(
                "Convert to joinable: household already joinable",
                extra={
                    "user_id": str(user_id),
                    "household_id": str(household_id),
                },
            )
            raise AppError(
                "Household is already joinable; only personal households can be converted",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if str(row.get("owner_id")) != str(user_id):
            logger.error(
                "Convert to joinable: not owner",
                extra={
                    "user_id": str(user_id),
                    "household_id": str(household_id),
                },
            )
            raise AppError(
                "Only the household owner can convert it to joinable",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        update_payload: Dict[str, object] = {"is_personal": False}
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
            logger.error(
                "Convert to joinable: update failed",
                extra={
                    "user_id": str(user_id),
                    "household_id": str(household_id),
                },
            )
            raise AppError(
                "Failed to update household",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        out_row = _first_row(updated)
        logger.info(
            "Household converted to joinable",
            extra={"user_id": str(user_id), "household_id": str(household_id)},
        )
        return _row_to_household_response(out_row)


__all__ = [
    "HouseholdService",
]

