from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Request
from supabase import Client

from pantry_backend.core.rate_limit import limiter
from pantry_backend.integrations.supabase_client import get_supabase_client
from pantry_backend.models.household import (
    HouseholdConvertToJoinableRequest,
    HouseholdCreateRequest,
    HouseholdJoinRequest,
    HouseholdJoinResponse,
    HouseholdLeaveResponse,
    HouseholdResponse,
)
from pantry_backend.services import (
    HouseholdService,
    get_current_user_id,
)


router = APIRouter(prefix="/households", tags=["households"])


def get_household_service(supabase: Client = Depends(get_supabase_client)) -> HouseholdService:
    return HouseholdService(supabase)


@router.post(
    "/create",
    response_model=HouseholdResponse,
)
@limiter.limit("5/minute")
async def create_household(
    request: Request,
    *,
    body: HouseholdCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_client),
) -> HouseholdResponse:
    return await household_service.create_household(
        body,
        user_id,
        supabase_admin=supabase_admin,
    )


@router.post(
    "/join",
    response_model=HouseholdJoinResponse,
)
@limiter.limit("5/minute")
async def join_household(
    request: Request,
    *,
    body: HouseholdJoinRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
) -> HouseholdJoinResponse:
    return await household_service.join_household_by_invite(
        body.invite_code,
        user_id,
    )


@router.post(
    "/leave",
    response_model=HouseholdLeaveResponse,
)
@limiter.limit("5/minute")
async def leave_household(
    request: Request,
    *,
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
) -> HouseholdLeaveResponse:
    return await household_service.leave_household(user_id)


@router.post(
    "/convert-to-joinable",
    response_model=HouseholdResponse,
)
@limiter.limit("5/minute")
async def convert_to_joinable(
    request: Request,
    *,
    body: HouseholdConvertToJoinableRequest | None = Body(None),
    user_id: UUID = Depends(get_current_user_id),
    household_service: HouseholdService = Depends(get_household_service),
    supabase_admin: Client = Depends(get_supabase_client),
) -> HouseholdResponse:
    name = body.name if body else None
    return await household_service.convert_personal_to_joinable(
        user_id,
        supabase_admin,
        name=name,
    )


__all__ = ["router"]

