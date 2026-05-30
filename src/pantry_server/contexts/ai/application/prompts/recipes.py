from __future__ import annotations

from typing import Iterable


SYSTEM_PROMPT = """You are a pantry-based recipe engine.

Generate ONE recipe only.

Output ONLY raw JSON (no markdown, no backticks) with this exact schema:
{"title": string, "ingredients": string[], "instructions": string[]}

Rules (follow all):
- When retrieved_context is provided, prefer facts from it for pairings and technique.
- Obey dietary_preferences.
- Use ingredients from pantry_items when possible; do not invent specialty ingredients not in pantry_items.
- Keep text compact: each ingredient/instruction string should be short.
"""


_STATUS = {
    "good": "~",
    "expiring": "!",
    "expired": "!!",
}


def build_user_message(
    items: Iterable[object],
    prefs: Iterable[object],
    max_time: int,
    diff: object,
    mode: object,
) -> str:
    encoded_items = ";".join(
        f"{getattr(i, 'name')}|{getattr(i, 'quantity')}|{_STATUS.get(getattr(i, 'status', 'good'), '~')}"
        for i in items
    )
    encoded_prefs = ",".join(getattr(t, "value", str(t)) for t in prefs) or "none"
    return (
        f"items={encoded_items} "
        f"prefs={encoded_prefs} "
        f"t={max_time} d={getattr(diff, 'value', str(diff))} m={getattr(mode, 'value', str(mode))}"
    )

