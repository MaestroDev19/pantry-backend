from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pantry_server.shared.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    RecipeGenerationResult,
    RecipeWorkflowInput,
    ShoppingGenerationResult,
    ShoppingWorkflowInput,
)


class AiWorkflowPort(Protocol):
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResult: ...

    async def generate_recipe(
        self,
        request: RecipeWorkflowInput,
        household_id: UUID | None = None,
    ) -> RecipeGenerationResult: ...

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
        household_id: UUID | None = None,
    ) -> ShoppingGenerationResult: ...
