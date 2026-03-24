from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from pantry_server.contexts.pantry.domain.models import CategoryEnum, UnitEnum


class PantryItemWriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: CategoryEnum
    quantity: float = Field(gt=0)
    unit: UnitEnum
    expiry_date: date | None = None


class PantryItemBulkCreateRequest(BaseModel):
    items: list[PantryItemWriteRequest] = Field(default_factory=list, min_length=1)


class PantryItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: CategoryEnum | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: UnitEnum | None = None
    expiry_date: date | None = None
