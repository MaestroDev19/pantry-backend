from uuid import UUID

from fastapi import APIRouter, Depends

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.contexts.recipes.infrastructure.mealdb import fetch_random_recipe_components
from pantry_server.core.exceptions import AppError
from pantry_server.middleware.fixed_window_limiter import FixedWindowRateLimiter
from pantry_server.middleware.rate_limit import WINDOW_SECONDS
from pantry_server.shared.ai_workflow import get_ai_workflow
from pantry_server.shared.auth import get_current_user_id
from pantry_server.shared.contracts import RecipeGenerationResult, RecipeWorkflowInput
from pantry_server.shared.pantry_read_cache import get_or_set_coroutine

router = APIRouter()

MEALDB_RANDOM_RECIPE_CACHE_TTL_SECONDS = 24 * 60 * 60
MEALDB_RANDOM_RECIPE_RATE_LIMIT_PER_MINUTE = 5

_mealdb_random_recipe_limiter = FixedWindowRateLimiter(window_seconds=WINDOW_SECONDS)
_MEALDB_RANDOM_RECIPE_CACHE_KEY = "mealdb:random_recipe_components"


@router.get("/")
async def list_recipes() -> dict[str, list[object]]:
    """Placeholder until persisted recipes exist."""
    return {"recipes": []}


@router.post("/generate-recipe", response_model=RecipeGenerationResult)
async def generate_recipe(
    payload: RecipeWorkflowInput,
    _user_id: UUID = Depends(get_current_user_id),
    workflow: AiWorkflowPort = Depends(get_ai_workflow),
) -> RecipeGenerationResult:
    return await workflow.generate_recipe(payload)


@router.get("/get-random-recipe")
async def get_random_recipe(
    _user_id: UUID = Depends(get_current_user_id),
) -> dict[str, object]:
    allowed = await _mealdb_random_recipe_limiter.allow(
        f"mealdb:random_recipe:user:{_user_id}",
        MEALDB_RANDOM_RECIPE_RATE_LIMIT_PER_MINUTE,
    )
    if not allowed:
        raise AppError(
            "Rate limit exceeded",
            status_code=429,
            error_code="rate_limit_exceeded",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )

    return await get_or_set_coroutine(
        _MEALDB_RANDOM_RECIPE_CACHE_KEY,
        float(MEALDB_RANDOM_RECIPE_CACHE_TTL_SECONDS),
        fetch_random_recipe_components,
    )
