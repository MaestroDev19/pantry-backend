from __future__ import annotations

from typing import Final

from pantry_server.contexts.pantry.domain.models import CategoryEnum


CATEGORY_VALUES: Final[tuple[str, ...]] = tuple(category.value for category in CategoryEnum)
ITEMS_TABLE_NAME: Final[str] = "pantry_items"
EMBEDDINGS_TABLE_NAME: Final[str] = "pantry_embeddings"

INVITE_CODE_LENGTH: Final[int] = 6
MAX_INVITE_CODE_RETRIES: Final[int] = 5
DEFAULT_PERSONAL_HOUSEHOLD_NAME: Final[str] = "My Household"
POSTGRES_UNIQUE_VIOLATION_CODE: Final[str] = "23505"
