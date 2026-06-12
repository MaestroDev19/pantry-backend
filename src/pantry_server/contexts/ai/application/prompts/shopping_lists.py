from __future__ import annotations

from typing import Iterable


SYSTEM_PROMPT = """You are a shopping list engine.

Output raw JSON only (no markdown, no backticks):
{"items":string[]}

Rules:
- items: only ingredients missing from the user's pantry that are needed for the goal.
- Use ctx for brand or quantity hints when present.
- Keep each item string short (name + quantity where relevant)."""


def _strip_chunk(chunk: str) -> str:
    if "Content:" in chunk:
        return chunk.split("Content:", 1)[-1].strip()
    return chunk.strip()


def build_user_message(
    pantry_items: Iterable[str],
    recipe_goal: str,
    servings: int,
    retrieved_context: Iterable[str] = (),
) -> str:
    ctx   = "|".join(_strip_chunk(c) for c in retrieved_context) or "none"
    items = ";".join(str(i).strip() for i in pantry_items)       or "none"
    return f"ctx={ctx} goal={recipe_goal.strip()} items={items} srv={servings}"
