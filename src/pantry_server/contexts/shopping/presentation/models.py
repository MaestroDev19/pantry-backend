from pydantic import BaseModel, Field


class GenerateShoppingListResponse(BaseModel):
    shopping_list: dict[str, object]
    retrieved_context: list[str] = Field(default_factory=list)
