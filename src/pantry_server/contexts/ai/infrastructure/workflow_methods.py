from __future__ import annotations

from typing import Any

from pantry_server.contexts.ai.application.prompts import recipes as recipe_prompts
from pantry_server.contexts.ai.application.prompts import shopping_lists as shopping_prompts
from pantry_server.shared.contracts import (
    RecipeWorkflowInput,
    RecipeWorkflowOutput,
    ShoppingWorkflowInput,
    ShoppingWorkflowOutput,
)


# ── recipe ────────────────────────────────────────────────────────────────────

def _build_recipe_prompt(
    request: RecipeWorkflowInput,
    retrieved_context: list[str],
) -> str:
    return recipe_prompts.build_user_message(
        pantry_items=request.pantry_items,
        dietary_preferences=request.dietary_preferences,
        retrieved_context=retrieved_context,
    )


def _normalize_recipe(payload: Any) -> RecipeWorkflowOutput | None:
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return None

    title        = str(payload.get("title", "")).strip()
    ingredients  = payload.get("ingredients") or []
    instructions = payload.get("instructions") or payload.get("steps") or []

    # Support both the compact keys the new prompt emits and the verbose
    # fallback keys in case an older cached response arrives.
    pantry_ing  = payload.get("pantry_ing")  or payload.get("pantry_ingredients")  or []
    extra_ing   = payload.get("extra_ing")   or payload.get("additional_ingredients") or []
    gap         = payload.get("gap")         or payload.get("pantry_coverage_note") or None

    norm = lambda lst: [str(i) for i in lst if str(i).strip()]  # noqa: E731

    ingredients_n  = norm(ingredients)
    instructions_n = norm(instructions)

    if not title or not ingredients_n or not instructions_n:
        return None

    return RecipeWorkflowOutput(
        title=title,
        ingredients=ingredients_n,
        instructions=instructions_n,
        pantry_ingredients=norm(pantry_ing),
        additional_ingredients=norm(extra_ing),
        pantry_coverage_note=str(gap).strip() if gap else None,
    )


# ── shopping ──────────────────────────────────────────────────────────────────

def _build_shopping_prompt(
    request: ShoppingWorkflowInput,
    retrieved_context: list[str],
) -> str:
    return shopping_prompts.build_user_message(
        pantry_items=request.pantry_items,
        recipe_goal=request.recipe_goal,
        servings=request.servings,
        retrieved_context=retrieved_context,
    )


def _normalize_shopping_list(payload: Any) -> ShoppingWorkflowOutput | None:
    if not isinstance(payload, dict):
        return None
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        return None
    normalized: list[str] = []
    for item in raw_items:
        value = item.get("name") if isinstance(item, dict) else str(item)
        if value and str(value).strip():
            normalized.append(str(value).strip())
    return ShoppingWorkflowOutput(items=normalized) if normalized else None
