from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    text: str


class EmbeddingResult(BaseModel):
    vector: list[float]


class RecipeWorkflowInput(BaseModel):
    pantry_items: list[str]
    dietary_preferences: list[str] = Field(default_factory=list)


class RecipeWorkflowOutput(BaseModel):
    title: str
    ingredients: list[str]
    instructions: list[str]


class ShoppingWorkflowInput(BaseModel):
    pantry_items: list[str]
    recipe_goal: str
    servings: int = 2


class ShoppingWorkflowOutput(BaseModel):
    items: list[str]
