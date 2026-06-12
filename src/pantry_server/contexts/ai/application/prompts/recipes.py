from __future__ import annotations

from typing import Iterable


SYSTEM_PROMPT = """You are a pantry-first recipe engine.

Output ONE recipe as raw JSON only (no markdown, no backticks):
{"title":string,"pantry_ing":string[],"extra_ing":string[],"ingredients":string[],"instructions":string[],"gap":string|null}

Rules:
- pantry_ing: items sourced from ctx/items only — the dish must centre on these.
- extra_ing: minimal buy-list to complete the dish; omit if pantry covers it.
- ingredients: all items combined in use order.
- gap: one short sentence if items can't satisfy the request, else null.
- Prefer ctx for technique and pairings when present.
- Obey prefs. Keep all strings short."""


def _strip_chunk(chunk: str) -> str:
    """Drop the 'Source: {...}\\nContent:' envelope; keep only the content text."""
    if "Content:" in chunk:
        return chunk.split("Content:", 1)[-1].strip()
    return chunk.strip()


def build_user_message(
    pantry_items: Iterable[str],
    dietary_preferences: Iterable[str],
    retrieved_context: Iterable[str],
) -> str:
    ctx   = "|".join(_strip_chunk(c) for c in retrieved_context) or "none"
    items = ";".join(str(i).strip() for i in pantry_items)       or "none"
    prefs = ",".join(str(p).strip() for p in dietary_preferences) or "none"
    return f"ctx={ctx} items={items} prefs={prefs}"
