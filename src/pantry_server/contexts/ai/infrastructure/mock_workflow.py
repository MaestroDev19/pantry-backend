from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.shared.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    RecipeWorkflowInput,
    RecipeWorkflowOutput,
    ShoppingWorkflowInput,
    ShoppingWorkflowOutput,
)


class MockAiWorkflow(AiWorkflowPort):
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResult:
        # Deterministic dummy vector for local development and tests.
        base = float(len(request.text))
        return EmbeddingResult(vector=[base, base / 2, base / 4])

    async def generate_recipe(self, request: RecipeWorkflowInput) -> RecipeWorkflowOutput:
        ingredients = request.pantry_items or ["rice", "salt"]
        return RecipeWorkflowOutput(
            title="Mock Pantry Bowl",
            ingredients=ingredients,
            instructions=[
                "Combine available pantry ingredients.",
                "Cook until done.",
                "Serve warm.",
            ],
        )

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
    ) -> ShoppingWorkflowOutput:
        desired = {"pasta", "tomato", "garlic", "olive oil", "salt"}
        available = {item.lower() for item in request.pantry_items}
        missing = sorted(item for item in desired if item not in available)
        return ShoppingWorkflowOutput(items=missing)
