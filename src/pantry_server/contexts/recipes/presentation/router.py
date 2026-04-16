from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends
import httpx

from pantry_server.core.exceptions import AppError
from pantry_server.contexts.ai.infrastructure.gemini_workflow import GeminiAiWorkflow
from pantry_server.contexts.recipes.presentation.models import GenerateRecipeResponse
from pantry_server.shared.auth import get_current_user_id
from pantry_server.shared.contracts import RecipeWorkflowInput
from pantry_server.shared.pantry_read_cache import get_or_set_coroutine
from pantry_server.middleware.fixed_window_limiter import FixedWindowRateLimiter
from pantry_server.middleware.rate_limit import WINDOW_SECONDS

router = APIRouter()
workflow = GeminiAiWorkflow()
RECIPE_KNOWLEDGE_BASE = [
    "Tomato and olive oil pair well with rice and pasta.",
    "Use pantry staples first to reduce waste.",
    "Seasoning in layers improves flavor.",
]

MEALDB_RANDOM_RECIPE_CACHE_TTL_SECONDS = 24 * 60 * 60
MEALDB_RANDOM_RECIPE_RATE_LIMIT_PER_MINUTE = 5

_mealdb_random_recipe_limiter = FixedWindowRateLimiter(window_seconds=WINDOW_SECONDS)
_MEALDB_RANDOM_RECIPE_CACHE_KEY = "mealdb:random_recipe_components"


async def get_recipes_from_mealdb() -> list[dict[str, object]]:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://www.themealdb.com/api/json/v1/1/random.php")
        response.raise_for_status()
        return response.json()["meals"]


async def _fetch_random_recipe_components() -> dict[str, object]:
    meals = await get_recipes_from_mealdb()
    if not meals:
        raise AppError(
            "MealDB did not return any meals",
            status_code=502,
            error_code="mealdb_bad_response",
        )
    # MealDB returns `{"meals": [ ... ]}`; we only need the first meal.
    return mealdb_to_recipe_components(meals[0])


def mealdb_to_recipe_components(meal: dict[str, Any]) -> dict[str, object]:
    # Extract and normalize title
    title = str(meal.get("strMeal") or "").strip()

    # Efficient extraction of ingredients with comprehensions
    ingredients = [
        (f"{(meal.get(f'strMeasure{i}') or '').strip()} {(meal.get(f'strIngredient{i}') or '').strip()}" if (meal.get(f'strIngredient{i}') or "").strip() else "").strip()
        for i in range(1, 21)
    ]
    ingredients = [ing for ing in ingredients if ing]  # filter empty strings

    # Process raw instructions
    raw_instructions = str(meal.get("strInstructions") or "").strip()
    # Heuristic: split on newline; if single paragraph, fall back to sentences
    steps = [chunk.strip() for chunk in raw_instructions.replace("\r\n", "\n").split("\n") if chunk.strip()]
    if len(steps) <= 1:
        # Fallback: split on periods
        steps = [s.strip() for s in raw_instructions.split(".") if s.strip()]

    # Normalize and optimize tags extraction
    tags = [t.strip().lower() for t in (meal.get("strTags") or "").split(",") if t.strip()]

    return {
        "id": str(meal.get("idMeal") or "").strip(),
        "title": title,
        "ingredients": ingredients,
        "instructions": steps[:8],  # limit steps for token/cost control
        "provider_recipe_id": str(meal.get("idMeal") or "").strip(),
        "tags": tags,
        "category": str(meal.get("strCategory") or "").strip().lower(),
    }

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
    


@router.get("/get-random-recipe")
async def get_random_recipe(
    _user_id: UUID = Depends(get_current_user_id)
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

    # Cache MealDB response for up to 24 hours; after expiry, next request re-fetches.
    return await get_or_set_coroutine(
        _MEALDB_RANDOM_RECIPE_CACHE_KEY,
        float(MEALDB_RANDOM_RECIPE_CACHE_TTL_SECONDS),
        _fetch_random_recipe_components,
    )