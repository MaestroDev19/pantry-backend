from __future__ import annotations

from typing import Final


INVITE_CODE_LENGTH: Final[int] = 6
MAX_INVITE_CODE_RETRIES: Final[int] = 5
DEFAULT_PERSONAL_HOUSEHOLD_NAME: Final[str] = "My Household"
POSTGRES_UNIQUE_VIOLATION_CODE: Final[str] = "23505"

PANTRY_HOUSEHOLD_CACHE_TTL_SECONDS: Final[int] = 60
PANTRY_USER_CACHE_TTL_SECONDS: Final[int] = 60


__all__ = [
    "INVITE_CODE_LENGTH",
    "MAX_INVITE_CODE_RETRIES",
    "DEFAULT_PERSONAL_HOUSEHOLD_NAME",
    "POSTGRES_UNIQUE_VIOLATION_CODE",
    "PANTRY_HOUSEHOLD_CACHE_TTL_SECONDS",
    "PANTRY_USER_CACHE_TTL_SECONDS",
]

from __future__ import annotations

from typing import Final

from pantry_backend.models.pantry import CategoryEnum, UnitEnum

DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200

ITEMS_TABLE_NAME: Final[str] = "pantry_items"
EMBEDDINGS_TABLE_NAME: Final[str] = "pantry_embeddings"
EMBEDDING_QUEUE_MAIN: Final[str] = "pantry_embedding_queue"

PANTRY_HOUSEHOLD_CACHE_TTL_SECONDS: Final[int] = 60
PANTRY_USER_CACHE_TTL_SECONDS: Final[int] = 60

CATEGORY_VALUES: Final[tuple[str, ...]] = tuple(category.value for category in CategoryEnum)
UNIT_VALUES: Final[tuple[str, ...]] = tuple(unit.value for unit in UnitEnum)

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PANTRY_HOUSEHOLD_CACHE_TTL_SECONDS",
    "PANTRY_USER_CACHE_TTL_SECONDS",
    "CATEGORY_VALUES",
    "UNIT_VALUES",
    "ITEMS_TABLE_NAME",
    "EMBEDDINGS_TABLE_NAME",
    "EMBEDDING_QUEUE_MAIN",
]
