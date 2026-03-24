from fastapi import APIRouter, Depends

from pantry_server.contexts.ai.infrastructure.gemini_workflow import GeminiAiWorkflow
from pantry_server.contexts.shopping.presentation.models import GenerateShoppingListResponse
from pantry_server.shared.contracts import AuthContext, ShoppingWorkflowInput
from pantry_server.shared.dependencies import get_auth_context

router = APIRouter()
workflow = GeminiAiWorkflow()
SHOPPING_KNOWLEDGE_BASE = [
    "For tomato pasta, keep garlic, tomato, olive oil, and salt in stock.",
    "Batch shopping by staple categories reduces missed items.",
    "Missing ingredients should be prioritized by recipe goal relevance.",
]


def retrieve_shopping_context(recipe_goal: str, limit: int = 2) -> list[str]:
    tokens = {token.strip().lower() for token in recipe_goal.split() if token.strip()}
    ranked = sorted(
        SHOPPING_KNOWLEDGE_BASE,
        key=lambda chunk: sum(token in chunk.lower() for token in tokens),
        reverse=True,
    )
    return ranked[:limit]


@router.get("/")
async def list_shopping_lists() -> dict[str, list[object]]:
    return {"shopping_lists": []}


@router.post("/generate-shopping-list")
async def generate_shopping_list(
    payload: ShoppingWorkflowInput,
    _: AuthContext = Depends(get_auth_context),
) -> GenerateShoppingListResponse:
    retrieved_context = retrieve_shopping_context(payload.recipe_goal)
    shopping_list = await workflow.generate_shopping_list(payload)
    return GenerateShoppingListResponse(
        shopping_list=shopping_list.model_dump(),
        retrieved_context=retrieved_context,
    )
