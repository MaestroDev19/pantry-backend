from typing import Protocol

from pantry_server.shared.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    RecipeWorkflowInput,
    RecipeWorkflowOutput,
    ShoppingWorkflowInput,
    ShoppingWorkflowOutput,
)


class AiWorkflowPort(Protocol):
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResult: ...

    async def generate_recipe(self, request: RecipeWorkflowInput) -> RecipeWorkflowOutput: ...

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
    ) -> ShoppingWorkflowOutput: ...
