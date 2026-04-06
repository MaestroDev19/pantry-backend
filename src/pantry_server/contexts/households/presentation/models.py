from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

HOUSEHOLD_NAME_MAX_LENGTH = 120
INVITE_CODE_MAX_LENGTH = 32


class HouseholdCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=HOUSEHOLD_NAME_MAX_LENGTH)
    is_personal: bool = False

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        return value.strip()


class HouseholdJoinRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=INVITE_CODE_MAX_LENGTH)

    @field_validator("invite_code")
    @classmethod
    def _normalize_invite_code(cls, value: str) -> str:
        return value.strip()


class HouseholdConvertToJoinableRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=HOUSEHOLD_NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class HouseholdRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=HOUSEHOLD_NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        return value.strip()
