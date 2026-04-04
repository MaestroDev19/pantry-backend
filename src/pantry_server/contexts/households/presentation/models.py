from __future__ import annotations

from pydantic import BaseModel


class HouseholdCreateRequest(BaseModel):
    name: str
    is_personal: bool = False


class HouseholdJoinRequest(BaseModel):
    invite_code: str


class HouseholdConvertToJoinableRequest(BaseModel):
    name: str | None = None


class HouseholdRenameRequest(BaseModel):
    name: str
