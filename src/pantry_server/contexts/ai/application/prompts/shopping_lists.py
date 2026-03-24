from __future__ import annotations

from typing import Iterable


SYSTEM_PROMPT = """Role: Pantry shopping list engine.

Rules:
1. Build one shopping list from recipe_goal and pantry inventory.
2. Prioritize essentials first, then optional upgrades.
3. Never output markdown. Output ONLY raw JSON object.

Schema:
{"goal":"str","items":[{"name":"str","quantity":"str","priority":"high|medium|low","reason":"str"}]}"""


def build_user_message(
    pantry_items: Iterable[str],
    recipe_goal: str,
    servings: int,
) -> str:
    encoded_items = ",".join(pantry_items) or "none"
    return f"pantry_items={encoded_items} recipe_goal={recipe_goal} servings={servings}"
