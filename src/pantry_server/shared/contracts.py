from pydantic import BaseModel, Field, field_validator

MAX_TEXT_LENGTH = 10_000
MAX_LIST_ITEMS = 200
MAX_ITEM_LENGTH = 200


class EmbeddingRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return value.strip()


class EmbeddingResult(BaseModel):
    vector: list[float]


class RecipeWorkflowInput(BaseModel):
    pantry_items: list[str] = Field(min_length=1, max_length=MAX_LIST_ITEMS)
    dietary_preferences: list[str] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    @field_validator("pantry_items", "dietary_preferences")
    @classmethod
    def _normalize_list(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        for item in value:
            normalized = item.strip()
            if normalized:
                out.append(normalized[:MAX_ITEM_LENGTH])
        return out


class RecipeWorkflowOutput(BaseModel):
    title: str
    ingredients: list[str]
    instructions: list[str]
    pantry_ingredients: list[str] = Field(default_factory=list)
    additional_ingredients: list[str] = Field(default_factory=list)
    pantry_coverage_note: str | None = None


class RecipeGenerationResult(BaseModel):
    recipe: RecipeWorkflowOutput
    retrieved_context: list[str] = Field(default_factory=list)


class ShoppingWorkflowInput(BaseModel):
    pantry_items: list[str] = Field(min_length=1, max_length=MAX_LIST_ITEMS)
    recipe_goal: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    servings: int = Field(default=2, ge=1, le=24)

    @field_validator("pantry_items")
    @classmethod
    def _normalize_pantry_items(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        for item in value:
            normalized = item.strip()
            if normalized:
                out.append(normalized[:MAX_ITEM_LENGTH])
        return out

    @field_validator("recipe_goal")
    @classmethod
    def _normalize_recipe_goal(cls, value: str) -> str:
        return value.strip()


class ShoppingWorkflowOutput(BaseModel):
    items: list[str]


class ShoppingGenerationResult(BaseModel):
    shopping_list: ShoppingWorkflowOutput
    retrieved_context: list[str] = Field(default_factory=list)
