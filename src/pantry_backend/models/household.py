from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HouseholdBase(BaseModel):
    """Base household model."""

    name: str = Field(..., min_length=1, max_length=100)


class HouseholdCreate(HouseholdBase):
    """Model for creating a household."""

    is_personal: bool = False


HouseholdCreateRequest = HouseholdCreate


class HouseholdUpdate(BaseModel):
    """Model for updating household."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)


class HouseholdResponse(HouseholdBase):
    """Model for household response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invite_code: str
    is_personal: bool = False
    created_at: datetime


class HouseholdMemberBase(BaseModel):
    """Base household member model."""

    user_id: UUID
    household_id: UUID


class HouseholdMemberResponse(HouseholdMemberBase):
    """Model for household member response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    joined_at: datetime
    user_email: Optional[str] = None


class HouseholdWithMembers(HouseholdResponse):
    """Household with member list."""

    members: list[HouseholdMemberResponse] = Field(default_factory=list)
    member_count: int = 0


class HouseholdJoinRequest(BaseModel):
    """Model for joining a household via invite code."""

    invite_code: str = Field(..., min_length=6, max_length=6)

    @field_validator("invite_code")
    @classmethod
    def validate_invite_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 6:
            raise ValueError("Invite code must be exactly 6 characters")
        if not normalized.isalnum():
            raise ValueError("Invite code must be alphanumeric")
        return normalized


class HouseholdJoinResponse(BaseModel):
    """Response after joining a household by invite code."""

    household: HouseholdResponse
    items_moved: int = 0


class HouseholdLeaveResponse(BaseModel):
    """Response when leaving a household."""

    message: str
    items_deleted: int = 0
    new_household_id: Optional[UUID] = None
    new_household_name: Optional[UUID] = None


class HouseholdConvertToJoinableRequest(BaseModel):
    """Optional body when converting personal household to joinable (shared)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)


__all__ = [
    "HouseholdBase",
    "HouseholdCreate",
    "HouseholdCreateRequest",
    "HouseholdUpdate",
    "HouseholdResponse",
    "HouseholdMemberBase",
    "HouseholdMemberResponse",
    "HouseholdWithMembers",
    "HouseholdJoinRequest",
    "HouseholdJoinResponse",
    "HouseholdLeaveResponse",
    "HouseholdConvertToJoinableRequest",
]

