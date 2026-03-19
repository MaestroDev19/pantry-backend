from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShoppingListItemBase(BaseModel):
    """Base shopping list item."""

    name: str = Field(..., min_length=1, max_length=100)
    quantity: float = Field(default=1.0, gt=0, le=1000)
    unit: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized.title()


class ShoppingListItemCreate(ShoppingListItemBase):
    """Model for creating shopping list item."""


class ShoppingListItemUpdate(BaseModel):
    """Model for updating shopping list item."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    quantity: Optional[float] = Field(default=None, gt=0, le=1000)
    unit: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=200)
    purchased: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized.title()


class ShoppingListItem(ShoppingListItemBase):
    """Shopping list item with metadata."""

    purchased: bool = False
    purchased_at: Optional[datetime] = None
    reason: Optional[str] = None  # running_low | expiring | recipe | manual
    estimated_price: Optional[float] = Field(default=None, ge=0)


class ShoppingListBase(BaseModel):
    """Base shopping list model."""

    items: list[ShoppingListItem] = Field(default_factory=list)


class ShoppingListResponse(ShoppingListBase):
    """Model for shopping list response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    generated_at: datetime
    updated_at: datetime

    total_items: int = 0
    purchased_items: int = 0
    pending_items: int = 0


class ShoppingListGenerateRequest(BaseModel):
    """Request to generate shopping list."""

    include_low_stock: bool = True
    include_expiring: bool = True
    include_staples: bool = True
    max_items: int = Field(default=20, ge=5, le=50)


class ShoppingListMarkPurchasedRequest(BaseModel):
    """Request to mark items as purchased."""

    item_indices: list[int] = Field(..., min_length=1)
    add_to_pantry: bool = True


class ShoppingListMarkPurchasedResponse(BaseModel):
    """Response after marking items as purchased."""

    purchased_count: int
    added_to_pantry_count: int
    pantry_item_ids: list[UUID] = Field(default_factory=list)
    message: str


class ShoppingListExportFormat(str, Enum):
    """Export format options."""

    TEXT = "text"
    JSON = "json"
    CSV = "csv"


class ShoppingListExportRequest(BaseModel):
    """Request to export shopping list."""

    format: ShoppingListExportFormat = ShoppingListExportFormat.TEXT
    include_purchased: bool = False

