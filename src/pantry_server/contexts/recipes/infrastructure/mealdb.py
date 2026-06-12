from __future__ import annotations

from typing import Any

import httpx

from pantry_server.core.exceptions import AppError

MEALDB_RANDOM_URL = "https://www.themealdb.com/api/json/v1/1/random.php"


async def fetch_random_meal() -> dict[str, Any]:
    """Fetch one random meal payload from TheMealDB API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(MEALDB_RANDOM_URL)
        response.raise_for_status()
        meals = response.json().get("meals") or []
    if not meals:
        raise AppError(
            "MealDB did not return any meals",
            status_code=502,
            error_code="mealdb_bad_response",
        )
    return meals[0]


def meal_to_recipe_components(meal: dict[str, Any]) -> dict[str, object]:
    """Map a MealDB meal dict to normalized recipe component fields."""
    title = str(meal.get("strMeal") or "").strip()

    ingredients = [
        (
            f"{(meal.get(f'strMeasure{i}') or '').strip()} {(meal.get(f'strIngredient{i}') or '').strip()}"
            if (meal.get(f"strIngredient{i}") or "").strip()
            else ""
        ).strip()
        for i in range(1, 21)
    ]
    ingredients = [ing for ing in ingredients if ing]

    import re
    raw_instructions = str(meal.get("strInstructions") or "").strip()
    raw_steps = [
        chunk.strip()
        for chunk in raw_instructions.replace("\r\n", "\n").split("\n")
        if chunk.strip()
    ]
    if len(raw_steps) <= 1:
        raw_steps = [s.strip() for s in raw_instructions.split(".") if s.strip()]

    steps = []
    for step in raw_steps:
        s = step.strip()
        # Strip leading checkboxes, bullets, and symbols
        s = re.sub(r'^[▢☐☑☒•\-\*\+\s\u2022]+', '', s).strip()
        s = re.sub(r'^\[[\sXx]?\]\s*', '', s).strip()
        s = re.sub(r'(?i)^step\s*\d+\s*(?:\.|\:|\-)?\s*', '', s).strip()
        # Keep only if it contains alphanumeric characters
        if s and any(c.isalnum() for c in s):
            steps.append(s)

    tags = [t.strip().lower() for t in (meal.get("strTags") or "").split(",") if t.strip()]

    return {
        "id": str(meal.get("idMeal") or "").strip(),
        "title": title,
        "ingredients": ingredients,
        "instructions": steps[:8],
        "provider_recipe_id": str(meal.get("idMeal") or "").strip(),
        "tags": tags,
        "category": str(meal.get("strCategory") or "").strip().lower(),
    }


async def fetch_random_recipe_components() -> dict[str, object]:
    """Fetch a random MealDB meal and return normalized recipe components."""
    meal = await fetch_random_meal()
    return meal_to_recipe_components(meal)
