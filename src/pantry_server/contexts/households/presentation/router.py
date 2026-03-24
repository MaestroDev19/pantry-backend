from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends
from supabase import Client

from pantry_server.contexts.households.application.household_service import HouseholdService
from pantry_server.contexts.households.domain.models import (
    HouseholdCreate,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
    HouseholdResponse,
)
from pantry_server.contexts.households.presentation.models import (
    HouseholdConvertToJoinableRequest,
    HouseholdCreateRequest,
    HouseholdJoinRequest,
)
from pantry_server.core.exceptions import AppError
from pantry_server.shared.auth import get_current_user_id
from pantry_server.shared.dependencies import get_supabase_client

router = APIRouter()


def get_household_service(supabase: Client | None = Depends(get_supabase_client)) -> HouseholdService:
    if supabase is None:
        raise AppError("Supabase is not configured", status_code=503)
    return HouseholdService(supabase)


@router.post("/create", response_model=HouseholdResponse)
async def create_household(
    *,
    body: HouseholdCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client | None = Depends(get_supabase_client),
) -> HouseholdResponse:
    household = HouseholdCreate(name=body.name, is_personal=body.is_personal)
    return await household_service.create_household(
        household,
        user_id,
        supabase_admin=supabase_admin,
    )


@router.post("/join", response_model=HouseholdJoinResponse)
async def join_household(
    *,
    body: HouseholdJoinRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
) -> HouseholdJoinResponse:
    return await household_service.join_household_by_invite(
        body.invite_code,
        user_id,
    )


@router.post("/leave", response_model=HouseholdLeaveResponse)
async def leave_household(
    *,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
) -> HouseholdLeaveResponse:
    return await household_service.leave_household(user_id)


@router.post("/convert-to-joinable", response_model=HouseholdResponse)
async def convert_to_joinable(
    *,
    body: HouseholdConvertToJoinableRequest | None = Body(None),
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client | None = Depends(get_supabase_client),
) -> HouseholdResponse:
    if supabase_admin is None:
        raise AppError("Supabase is not configured", status_code=503)
    name = body.name if body else None
    return await household_service.convert_personal_to_joinable(
        user_id,
        supabase_admin,
        name=name,
    )


__all__ = ["router"]
