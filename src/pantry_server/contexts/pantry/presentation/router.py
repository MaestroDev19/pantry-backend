from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from supabase import Client

from pantry_server.contexts.pantry.application.pantry_service import PantryService
from pantry_server.contexts.pantry.domain.entities import PantryItem
from pantry_server.contexts.pantry.presentation.models import (
    PantryItemBulkCreateRequest,
    PantryItemUpdateRequest,
    PantryItemWriteRequest,
)
from pantry_server.core.config import get_settings
from pantry_server.core.exceptions import AppError
from pantry_server.shared.auth import get_current_household_id, get_current_user_id
from pantry_server.shared.dependencies import get_supabase_client

router = APIRouter()


def get_pantry_service(supabase: Client | None = Depends(get_supabase_client)) -> PantryService:
    if supabase is None:
        raise AppError("Supabase is not configured", status_code=503)
    return PantryService(supabase)


def validate_embedding_worker_secret(
    x_worker_secret: str | None = Header(default=None, alias="x-worker-secret"),
) -> None:
    expected = get_settings().embedding_worker_secret
    if not expected or x_worker_secret != expected:
        raise AppError("Unauthorized worker request", status_code=401)


@router.post("/add-single-item")
async def add_single_item(
    payload: PantryItemWriteRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, PantryItem]:
    """JSON body: name, category (enum: produce|dairy|meat|grains|canned|frozen|spices|other),
    quantity (>0), unit (enum: piece|gram|kilogram|milliliter|liter|cup|tablespoon|teaspoon),
    optional expiry_date (ISO date). Server adds owner_id, household_id, embedding_status."""
    item = await pantry_service.add_single_item(
        owner_id=user_id,
        household_id=household_id,
        item_data=payload.model_dump(mode="json", exclude_none=True),
    )
    return {"item": item}


@router.post("/add-bulk-items")
async def add_bulk_items(
    payload: PantryItemBulkCreateRequest,
    user_id: UUID = Depends(get_current_user_id),
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, list[PantryItem]]:
    items = await pantry_service.add_bulk_items(
        owner_id=user_id,
        household_id=household_id,
        items_data=[item.model_dump(mode="json", exclude_none=True) for item in payload.items],
    )
    return {"items": items}


@router.get("/get-my-items")
async def get_my_items(
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, list[PantryItem]]:
    items = await pantry_service.get_my_items(owner_id=user_id)
    return {"items": items}


@router.get("/get-household-pantry")
async def get_household_pantry(
    household_id: UUID = Depends(get_current_household_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, list[PantryItem]]:
    items = await pantry_service.get_household_pantry(household_id=household_id)
    return {"items": items}


@router.patch("/update-my-item/{item_id}")
async def update_my_item(
    item_id: UUID,
    payload: PantryItemUpdateRequest,
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, PantryItem]:
    item = await pantry_service.update_my_item(
        item_id=item_id,
        owner_id=user_id,
        updates=payload.model_dump(mode="json", exclude_none=True, exclude_unset=True),
    )
    return {"item": item}


@router.delete("/delete-my-item/{item_id}")
async def delete_my_item(
    item_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, str]:
    return await pantry_service.delete_my_item(item_id=item_id, owner_id=user_id)


@router.post("/internal/embedding-jobs/run")
async def run_embedding_jobs(
    _: None = Depends(validate_embedding_worker_secret),
    max_jobs: int = Query(default=20, ge=1, le=20),
    pantry_service: PantryService = Depends(get_pantry_service),
) -> dict[str, int]:
    return await pantry_service.process_embedding_jobs(max_jobs=max_jobs)
