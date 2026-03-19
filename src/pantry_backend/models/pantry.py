from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryEnum(str, Enum):
    """Categories for classifying pantry items."""

    DAIRY = "Dairy"
    PRODUCE = "Produce"
    MEAT_SEAFOOD = "Meat & Seafood"
    GRAINS_PASTA = "Grains & Pasta"
    CANNED_GOODS = "Canned Goods"
    FROZEN = "Frozen"
    SNACKS = "Snacks"
    BEVERAGES = "Beverages"
    CONDIMENTS_OILS = "Condiments & Oils"
    BAKING = "Baking"
    OTHER = "Other"


class UnitEnum(str, Enum):
    """Predefined units for pantry item quantities."""

    KG = "kg"
    G = "g"
    MG = "mg"
    LB = "lb"
    OZ = "oz"

    L = "L"
    ML = "mL"
    GAL = "gal"
    CUP = "cup"
    TBSP = "tbsp"
    TSP = "tsp"

    PIECES = "pieces"
    ITEMS = "items"

    CAN = "can"
    BOTTLE = "bottle"
    BOX = "box"
    BAG = "bag"
    PACK = "pack"


class ExpiryStatus(str, Enum):
    """Classification of an item's freshness state."""

    GOOD = "good"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    NO_DATE = "no_date"


class PantryItemBase(BaseModel):
    """Base model for pantry item fields."""

    name: str = Field(..., min_length=1, max_length=100)
    category: CategoryEnum
    quantity: float = Field(default=1.0, gt=0, le=10000)
    unit: Optional[UnitEnum] = None
    expiry_date: Optional[date] = None
    expiry_visible: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized.title()

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return None
        one_year_ago = date.today().replace(year=date.today().year - 1)
        if value < one_year_ago:
            raise ValueError("Expiry date cannot be more than 1 year in the past")
        return value


class PantryItemCreate(PantryItemBase):
    """Payload for creating a new pantry item."""


class PantryItemUpsert(PantryItemBase):
    """Payload for upserting a pantry item."""


class PantryItemUpdate(BaseModel):
    """Payload for updating a pantry item (all fields optional)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Optional[CategoryEnum] = None
    quantity: Optional[float] = Field(default=None, gt=0, le=10000)
    unit: Optional[UnitEnum] = None
    expiry_date: Optional[date] = None
    expiry_visible: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized.title()

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return None
        one_year_ago = date.today().replace(year=date.today().year - 1)
        if value < one_year_ago:
            raise ValueError("Expiry date cannot be more than 1 year in the past")
        return value


class PantryItemResponse(PantryItemBase):
    """Full response for a pantry item, including metadata and computed fields."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    owner_id: UUID
    household_id: UUID
    created_at: datetime
    updated_at: datetime

    expiry_status: Optional[ExpiryStatus] = None
    days_until_expiry: Optional[int] = None
    is_mine: bool = False


PantryItem = PantryItemResponse


class PantryItemWithOwner(PantryItemResponse):
    """Pantry item with owner identity information."""

    owner_email: Optional[str] = None
    owner_name: Optional[str] = None


class PantryItemUpsertResponse(BaseModel):
    """API response after an upsert action."""

    id: UUID
    is_new: bool
    old_quantity: float
    new_quantity: float
    message: str
    embedding_generated: bool


class PantryItemMarkUsed(BaseModel):
    """Payload to notify that some of an item was used."""

    quantity_used: Optional[float] = Field(default=None, gt=0)


class PantrySummary(BaseModel):
    """Aggregated pantry info for dashboards."""

    total_items: int = 0
    my_items: int = 0
    good_count: int = 0
    expiring_soon_count: int = 0
    expired_count: int = 0
    categories: dict[str, int] = Field(default_factory=dict)


class PantryFilterParams(BaseModel):
    """Filter parameters for pantry list/search endpoints."""

    owner_id: Optional[UUID] = None
    category: Optional[CategoryEnum] = None
    expiry_status: Optional[ExpiryStatus] = None
    search: Optional[str] = Field(default=None, max_length=100)
    sort_by: str = Field(
        default="expiry_date",
        pattern="^(name|category|expiry_date|created_at)$",
    )
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PantryItemBulkCreate(BaseModel):
    """Single item in bulk create request."""

    name: str = Field(..., min_length=1, max_length=100)
    category: CategoryEnum
    quantity: float = Field(default=1.0, gt=0, le=10000)
    unit: Optional[UnitEnum] = None
    expiry_date: Optional[date] = None
    expiry_visible: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized.title()

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return None
        one_year_ago = date.today().replace(year=date.today().year - 1)
        if value < one_year_ago:
            raise ValueError("Expiry date cannot be more than 1 year in the past")
        return value


class PantryItemsBulkCreateRequest(BaseModel):
    """Request to bulk create pantry items."""

    items: list[PantryItemBulkCreate] = Field(..., min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def validate_unique_names(
        cls,
        value: list[PantryItemBulkCreate],
    ) -> list[PantryItemBulkCreate]:
        names = [item.name.lower() for item in value]
        if len(names) != len(set(names)):
            # Allow duplicates for now; hook for future strictness.
            return value
        return value


class BulkUpsertResult(BaseModel):
    """Result for a single item in bulk operation."""

    name: str
    success: bool
    is_new: bool = False
    item_id: Optional[UUID] = None
    old_quantity: Optional[float] = None
    new_quantity: Optional[float] = None
    error: Optional[str] = None


class PantryItemsBulkCreateResponse(BaseModel):
    """Response for bulk create operation."""

    total_requested: int
    successful: int
    failed: int
    new_items: int
    updated_items: int
    results: list[BulkUpsertResult]
    embeddings_queued: int

