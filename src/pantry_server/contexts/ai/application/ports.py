from typing import Protocol

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

    async def generate_recipe(self, request: RecipeWorkflowInput) -> RecipeGenerationResult: ...

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
    ) -> ShoppingGenerationResult: ...
