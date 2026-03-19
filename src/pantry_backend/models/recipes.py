from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DietaryTag(str, Enum):
    """Dietary restriction tags for recipes."""

    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    NUT_FREE = "nut_free"
    LOW_CARB = "low_carb"
    KETO = "keto"
    PALEO = "paleo"
    HALAL = "halal"
    KOSHER = "kosher"


class Difficulty(str, Enum):
    """Levels of recipe difficulty."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class RecipeMode(str, Enum):
    """How to source pantry items for recipe generation."""

    PERSONAL = "personal"
    HOUSEHOLD = "household"


class RecipeIngredient(BaseModel):
    """
    A single ingredient used in a recipe.
    """

    name: str = Field(..., min_length=1, max_length=100)
    quantity: str = Field(..., max_length=50)
    unit: Optional[str] = Field(default=None, max_length=20)
    have: bool = False
    owner: Optional[str] = None
    pantry_item_id: Optional[UUID] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized.lower()


class RecipeStep(BaseModel):
    """A single step in a recipe."""

    step_number: int = Field(..., ge=1)
    instruction: str = Field(..., min_length=10, max_length=500)


class RecipeBase(BaseModel):
    """
    Core attributes for a recipe.
    """

    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    ingredients: list[RecipeIngredient] = Field(..., min_length=1)
    instructions: list[str] = Field(..., min_length=1)
    prep_time: int = Field(..., ge=0, le=480)
    cook_time: int = Field(..., ge=0, le=480)
    servings: int = Field(..., ge=1, le=50)
    difficulty: Optional[Difficulty] = Difficulty.MEDIUM
    cuisine: Optional[str] = Field(default=None, max_length=50)
    dietary_tags: list[DietaryTag] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized.title()

    @property
    def total_time(self) -> int:
        return self.prep_time + self.cook_time


class RecipeCreate(RecipeBase):
    """Payload for creating a new recipe."""


class RecipeResponse(RecipeBase):
    """
    API response model for a recipe, including metadata and computed fields.
    """

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    external_id: Optional[str] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime

    ingredients_available: int = 0
    ingredients_needed: int = 0
    can_make: bool = False


class RecipeGenerateRequest(BaseModel):
    """
    Request payload for generating new recipes.
    """

    mode: RecipeMode = RecipeMode.PERSONAL
    dietary_preferences: list[DietaryTag] = Field(default_factory=list)
    max_items_to_use: int = Field(default=15, ge=5, le=30)
    cuisine: Optional[str] = Field(default=None, max_length=50)
    max_prep_time: Optional[int] = Field(default=None, ge=5, le=120)
    difficulty: Optional[Difficulty] = None
    num_recipes: int = Field(default=3, ge=1, le=5)


class RecipeGenerateResponse(BaseModel):
    """
    Response payload after generating recipes.
    """

    recipes: list[RecipeResponse]
    mode: RecipeMode
    pantry_items_used: int
    generation_time: float
    tokens_used: Optional[int] = None


class RecipeUseIngredientsRequest(BaseModel):
    """
    Request payload to mark ingredients as used.
    """

    recipe_id: UUID
    ingredient_indices: list[int] = Field(..., min_length=1)


class RecipeUseIngredientsResponse(BaseModel):
    """
    Response after marking ingredients as used.
    """

    updated_items: list[UUID] = Field(default_factory=list)
    deleted_items: list[UUID] = Field(default_factory=list)
    message: str


class RecipeSearchRequest(BaseModel):
    """
    Request payload for searching recipes.
    """

    query: str = Field(..., min_length=1, max_length=200)
    dietary_preferences: list[DietaryTag] = Field(default_factory=list)
    max_prep_time: Optional[int] = Field(default=None, ge=5, le=120)
    difficulty: Optional[Difficulty] = None
    limit: int = Field(default=10, ge=1, le=50)

