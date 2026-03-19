from __future__ import annotations

from typing import Iterable


SYSTEM_PROMPT = """Role: Pantry recipe engine.

Encoding legend (never repeated in user messages):
- Items format: name|qty|s  where s: ~=good  !=expiring  !!=expired
- have: 1=owned  0=missing
- Prefs: comma-separated dietary tags, or "none"
- d: easy|medium|hard   m: mine|household

Rules:
1. Output EXACTLY 3 recipes; prioritise ! and !! items.
2. Strictly obey prefs.
3. Never invent owned items; flag missing via have:0.
4. Output ONLY raw JSON array. No markdown, no fences.

Schema:
[{"title":"≤5w","time":0,"diff":"easy|medium|hard","servings":0,
"ing":[{"n":"≤4w","q":"str","have":1|0,"owner":"str|null"}],
"steps":["≤5 steps, ≤12w each"],"note":"str|null"}]"""


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

