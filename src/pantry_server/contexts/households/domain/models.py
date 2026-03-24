from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class HouseholdCreate(BaseModel):
    name: str
    is_personal: bool = False


class HouseholdResponse(BaseModel):
    id: UUID
    name: str
    created_at: str
    invite_code: str
    is_personal: bool = False


class HouseholdJoinResponse(BaseModel):
    household: HouseholdResponse
    items_moved: int = 0


class HouseholdLeaveResponse(BaseModel):
    message: str
    items_deleted: int = 0
    new_household_id: UUID | None = None
    new_household_name: str | None = None
