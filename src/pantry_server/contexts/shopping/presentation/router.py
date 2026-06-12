from uuid import UUID

from fastapi import APIRouter, Depends

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.shared.ai_workflow import get_ai_workflow
from pantry_server.shared.auth import get_current_household_id, get_current_user_id
from pantry_server.shared.contracts import ShoppingGenerationResult, ShoppingWorkflowInput

router = APIRouter()


@router.get("/")
async def list_shopping_lists() -> dict[str, list[object]]:
    """Placeholder until persisted shopping lists exist."""
    return {"shopping_lists": []}


@router.post("/generate-shopping-list", response_model=ShoppingGenerationResult)
async def generate_shopping_list(
    payload: ShoppingWorkflowInput,
    _user_id: UUID = Depends(get_current_user_id),
    household_id: UUID = Depends(get_current_household_id),
    workflow: AiWorkflowPort = Depends(get_ai_workflow),
) -> ShoppingGenerationResult:
    return await workflow.generate_shopping_list(payload, household_id=household_id)
