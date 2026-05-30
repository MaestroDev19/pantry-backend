"""AI utilities: embeddings and a legacy unauthenticated recipe path.

Clients should call `POST /api/recipes/generate-recipe` for recipe generation
(Bearer auth). This router keeps IP-based rate limits only.
"""

from fastapi import APIRouter, Depends

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.middleware.supplementary_rate_limits import enforce_ai_ip_limit
from pantry_server.shared.ai_workflow import get_ai_workflow
from pantry_server.shared.contracts import EmbeddingRequest, RecipeGenerationResult, RecipeWorkflowInput

router = APIRouter(dependencies=[Depends(enforce_ai_ip_limit)])


@router.post("/embeddings")
async def create_embedding(
    payload: EmbeddingRequest,
    workflow: AiWorkflowPort = Depends(get_ai_workflow),
) -> dict[str, object]:
    result = await workflow.create_embedding(payload)
    return {"embedding": result}


@router.post("/recipes/generate", response_model=RecipeGenerationResult)
async def generate_recipe_legacy(
    payload: RecipeWorkflowInput,
    workflow: AiWorkflowPort = Depends(get_ai_workflow),
) -> RecipeGenerationResult:
    """Legacy alias; prefer `/api/recipes/generate-recipe` (authenticated)."""
    return await workflow.generate_recipe(payload)
