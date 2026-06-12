from __future__ import annotations

from uuid import UUID

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.shared.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    RecipeGenerationResult,
    RecipeWorkflowInput,
    RecipeWorkflowOutput,
    ShoppingGenerationResult,
    ShoppingWorkflowInput,
    ShoppingWorkflowOutput,
)


class MockAiWorkflow(AiWorkflowPort):
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResult:
        # Deterministic dummy vector for local development and tests.
        base = float(len(request.text))
        return EmbeddingResult(vector=[base, base / 2, base / 4])

    async def generate_recipe(
        self,
        request: RecipeWorkflowInput,
        household_id: UUID | None = None,
    ) -> RecipeGenerationResult:
        ingredients = request.pantry_items or ["rice", "salt"]
        recipe = RecipeWorkflowOutput(
            title="Mock Pantry Bowl",
            ingredients=ingredients,
            instructions=[
                "Combine available pantry ingredients.",
                "Cook until done.",
                "Serve warm.",
            ],
        )
        return RecipeGenerationResult(recipe=recipe, retrieved_context=[])

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
        household_id: UUID | None = None,
    ) -> ShoppingGenerationResult:
        desired = {"pasta", "tomato", "garlic", "olive oil", "salt"}
        available = {item.lower() for item in request.pantry_items}
        missing = sorted(item for item in desired if item not in available)
        shopping_list = ShoppingWorkflowOutput(items=missing)
        return ShoppingGenerationResult(shopping_list=shopping_list, retrieved_context=[])
