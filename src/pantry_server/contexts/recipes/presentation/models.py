from pydantic import BaseModel, Field


class GenerateRecipeResponse(BaseModel):
    recipe: dict[str, object]
    retrieved_context: list[str] = Field(default_factory=list)
