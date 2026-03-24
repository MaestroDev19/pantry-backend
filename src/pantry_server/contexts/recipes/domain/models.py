from pydantic import BaseModel, Field


class RecipeDomainModel(BaseModel):
    title: str
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
