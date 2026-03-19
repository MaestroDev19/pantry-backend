from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from supabase import Client

from pantry_backend.core.cache import get_cache
from pantry_backend.core.exceptions import AppError
from pantry_backend.core.rate_limit import limiter
from pantry_backend.integrations.supabase_client import get_supabase_client
from pantry_backend.models.pantry import (
    PantryItem,
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
)
from pantry_backend.services import (
    PantryService,
    get_current_household_id,
    get_current_user_id,
)
from pantry_backend.utils import (
    PANTRY_HOUSEHOLD_CACHE_TTL_SECONDS,
    PANTRY_USER_CACHE_TTL_SECONDS,
)


router = APIRouter(prefix="/pantry", tags=["pantry"])


def _invalidate_household_cache(household_id: UUID) -> None:
    cache = get_cache()
    cache.delete(f"pantry:household:{household_id}")


def _invalidate_user_cache(household_id: UUID, user_id: UUID) -> None:
    cache = get_cache()
    cache.delete(f"pantry:user:{household_id}:{user_id}")


def _get_cached_household_items(household_id: UUID) -> list[PantryItem] | None:
    cache = get_cache()
    cache_key = f"pantry:household:{household_id}"
    return cache.get(cache_key)


def _set_cached_household_items(household_id: UUID, items: list[PantryItem]) -> None:
    cache = get_cache()
    cache_key = f"pantry:household:{household_id}"
    cache.set(cache_key, items, ttl_seconds=PANTRY_HOUSEHOLD_CACHE_TTL_SECONDS)


def _get_cached_user_items(
    household_id: UUID,
    user_id: UUID,
) -> list[PantryItem] | None:
    cache = get_cache()
    cache_key = f"pantry:user:{household_id}:{user_id}"
    return cache.get(cache_key)


def _set_cached_user_items(
    household_id: UUID,
    user_id: UUID,
    items: list[PantryItem],
) -> None:
    cache = get_cache()
    cache_key = f"pantry:user:{household_id}:{user_id}"
    cache.set(cache_key, items, ttl_seconds=PANTRY_USER_CACHE_TTL_SECONDS)


def get_pantry_service(supabase: Client = Depends(get_supabase_client)) -> PantryService:
    return PantryService(supabase)


@router.post(
    "/add-item",
    response_model=PantryItemUpsertResponse,
)
@limiter.limit("10/minute")
async def add_single_pantry_item(
    request: Request,
    *,
    pantry_item: PantryItemUpsert,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemUpsertResponse:
    result = await pantry_service.add_pantry_item_single(
        pantry_item,
        household_id,
        user_id,
    )
    if result is None:
        raise AppError(
            "Failed to add pantry item",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    return result


@router.post(
    "/bulk-add",
    response_model=PantryItemsBulkCreateResponse,
)
@limiter.limit("5/minute")
async def add_multiple_pantry_items(
    request: Request,
    *,
    pantry_items: PantryItemsBulkCreateRequest,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemsBulkCreateResponse:
    if not pantry_items.items:
        raise AppError(
            "No pantry items provided",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = await pantry_service.add_pantry_item_bulk(
        pantry_items.items,
        household_id,
        user_id,
    )
    if result is None:
        raise AppError(
            "Bulk pantry add failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    return result


@router.get(
    "/household-items",
    response_model=list[PantryItem],
)
async def get_all_pantry_items(
    *,
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> list[PantryItem]:
    cached_items = _get_cached_household_items(household_id)
    if cached_items is not None:
        return cached_items

    items = await pantry_service.get_household_pantry_items(household_id)
    if items is None:
        return []

    _set_cached_household_items(household_id, items)
    return items


@router.get(
    "/my-items",
    response_model=list[PantryItem],
)
async def get_my_pantry_items(
    *,
    user_id: UUID = Depends(get_current_user_id),
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> list[PantryItem]:
    cached_items = _get_cached_user_items(household_id, user_id)
    if cached_items is not None:
        return cached_items

    items = await pantry_service.get_my_pantry_items(household_id, user_id)
    if items is None:
        return []

    _set_cached_user_items(household_id, user_id, items)
    return items


@router.put(
    "/update-item",
    response_model=PantryItemUpsertResponse,
)
@limiter.limit("10/minute")
async def update_pantry_item(
    request: Request,
    *,
    pantry_item: PantryItemUpsert,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemUpsertResponse:
    result = await pantry_service.update_pantry_item(
        pantry_item,
        household_id,
        user_id,
    )
    if result is None:
        raise AppError(
            "Pantry item not found or could not be updated",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    return result


@router.delete(
    "/delete-item",
    response_model=PantryItemUpsertResponse,
)
@limiter.limit("10/minute")
async def delete_pantry_item(
    request: Request,
    *,
    item_id: UUID,
    household_id: UUID = Depends(get_current_household_id),
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> PantryItemUpsertResponse:
    result = await pantry_service.delete_pantry_item(
        item_id,
        household_id,
        user_id,
    )
    if result is None:
        raise AppError(
            "Pantry item not found for deletion",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    _invalidate_household_cache(household_id)
    _invalidate_user_cache(household_id, user_id)
    return result


__all__ = ["router"]

