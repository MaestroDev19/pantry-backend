from pydantic import BaseModel, Field


class ShoppingListDomainModel(BaseModel):
    items: list[str] = Field(default_factory=list)
