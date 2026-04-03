from uuid import UUID

from fastapi import APIRouter, Depends

from pantry_server.contexts.ai.infrastructure.gemini_workflow import GeminiAiWorkflow
from pantry_server.contexts.recipes.presentation.models import GenerateRecipeResponse
from pantry_server.shared.auth import get_current_user_id
from pantry_server.shared.contracts import RecipeWorkflowInput

router = APIRouter()
workflow = GeminiAiWorkflow()
RECIPE_KNOWLEDGE_BASE = [
    "Tomato and olive oil pair well with rice and pasta.",
    "Use pantry staples first to reduce waste.",
    "Seasoning in layers improves flavor.",
]


def retrieve_recipe_context(pantry_items: list[str], limit: int = 2) -> list[str]:
    tokens = {item.lower() for item in pantry_items}
    ranked = sorted(
        RECIPE_KNOWLEDGE_BASE,
        key=lambda chunk: sum(token in chunk.lower() for token in tokens),
        reverse=True,
    )
    return ranked[:limit]


@router.get("/")
async def list_recipes() -> dict[str, list[object]]:
    return {"recipes": []}


@router.post("/generate-recipe")
async def generate_recipe(
    payload: RecipeWorkflowInput,
    _user_id: UUID = Depends(get_current_user_id),
) -> GenerateRecipeResponse:
    retrieved_context = retrieve_recipe_context(payload.pantry_items)
    recipe = await workflow.generate_recipe(payload)
    return GenerateRecipeResponse(
        recipe=recipe.model_dump(),
        retrieved_context=retrieved_context,
    )
