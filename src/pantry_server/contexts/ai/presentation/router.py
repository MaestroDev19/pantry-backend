from fastapi import APIRouter, Depends

from pantry_server.contexts.ai.infrastructure.mock_workflow import MockAiWorkflow
from pantry_server.middleware.supplementary_rate_limits import enforce_ai_ip_limit
from pantry_server.shared.contracts import EmbeddingRequest, RecipeWorkflowInput

router = APIRouter(dependencies=[Depends(enforce_ai_ip_limit)])
workflow = MockAiWorkflow()


@router.post("/embeddings")
async def create_embedding(payload: EmbeddingRequest) -> dict[str, object]:
    result = await workflow.create_embedding(payload)
    return {"embedding": result}


@router.post("/recipes/generate")
async def generate_recipe(payload: RecipeWorkflowInput) -> dict[str, object]:
    result = await workflow.generate_recipe(payload)
    return {"recipe": result}
