from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import anyio
from fastapi import status
from supabase import Client
import logging

from pantry_backend.core.exceptions import AppError
from pantry_backend.ai.retriever_cache import get_retriever_cache
from pantry_backend.vectorstores.supabase_vector_store import get_vector_store
from pantry_backend.integrations.supabase_client import get_supabase_client
from pantry_backend.models.pantry import (
    BulkUpsertResult,
    PantryItem,
    PantryItemCreate,
    PantryItemUpsert,
    PantryItemUpsertResponse,
    PantryItemsBulkCreateRequest,
    PantryItemsBulkCreateResponse,
)
from pantry_backend.utils.date_time_styling import (
    format_iso_date,
    format_iso_datetime,
)


logger = logging.getLogger("pantry_backend.pantry_service")
_retriever_cache = get_retriever_cache()

_EMBEDDING_QUEUE_NAME = "pantry_embedding_queue"
_INITIAL_ATTEMPT_COUNT = 0


async def _ensure_user_in_household(
    supabase: Client,
    user_id: UUID,
    household_id: UUID,
    operation: str,
) -> None:
    membership_response = await anyio.to_thread.run_sync(
        lambda: (
            supabase.table("household_members")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("household_id", str(household_id))
            .limit(1)
            .execute()
        ),
    )
    if not getattr(membership_response, "data", None):
        logger.error(
            "%s: user not in household",
            operation,
            extra={"household_id": str(household_id), "user_id": str(user_id)},
        )
        raise AppError(
            "User is not a member of the specified household",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _job_source_updated_at_for_row(row: Dict[str, Any]) -> str:
    updated_at = row.get("updated_at")
    if updated_at is not None:
        return str(updated_at)
    return format_iso_datetime(value=datetime.now())


async def _enqueue_embedding_job(
    *,
    pantry_item_id: str,
    source_updated_at: str,
) -> bool:
    settings_client = get_supabase_client  # reuse integration helper for now
    try:
        client = settings_client.__wrapped__(  # type: ignore[attr-defined]
            get_supabase_client.__defaults__[0],  # pragma: no cover
        )
        await anyio.to_thread.run_sync(
            lambda: (
                client.schema("pgmq_public")
                .rpc(
                    "send",
                    {
                        "queue_name": _EMBEDDING_QUEUE_NAME,
                        "message": {
                            "pantry_item_id": pantry_item_id,
                            "attempt_count": _INITIAL_ATTEMPT_COUNT,
                            "source_updated_at": source_updated_at,
                        },
                        "sleep_seconds": 0,
                    },
                )
                .execute()
            ),
        )
    except Exception as exc:  # pragma: no cover - best-effort path
        logger.warning(
            "Failed to enqueue pantry embedding job",
            extra={"pantry_item_id": pantry_item_id, "reason": str(exc)},
        )
        return False
    return True


async def _enqueue_embedding_jobs_bulk(
    *,
    job_payloads: List[Dict[str, object]],
) -> int:
    if not job_payloads:
        return 0
    settings_client = get_supabase_client
    try:
        client = settings_client.__wrapped__(  # type: ignore[attr-defined]
            get_supabase_client.__defaults__[0],  # pragma: no cover
        )
        await anyio.to_thread.run_sync(
            lambda: (
                client.schema("pgmq_public")
                .rpc(
                    "send_batch",
                    {
                        "queue_name": _EMBEDDING_QUEUE_NAME,
                        "messages": job_payloads,
                        "sleep_seconds": 0,
                    },
                )
                .execute()
            ),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Failed to enqueue pantry embedding jobs (bulk)",
            extra={"count": len(job_payloads), "reason": str(exc)},
        )
        return 0
    return len(job_payloads)


class PantryService:
    def __init__(self, supabase: Client) -> None:
        self.supabase = supabase
        self.vector_store = get_vector_store()

    async def add_pantry_item_single(
        self,
        pantry_item: PantryItemUpsert,
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemUpsertResponse:
        await _ensure_user_in_household(
            self.supabase,
            user_id,
            household_id,
            "Add pantry item",
        )

        data = pantry_item.model_dump()
        data["household_id"] = str(household_id)
        data["owner_id"] = str(user_id)
        now = datetime.now()
        data["created_at"] = format_iso_datetime(value=now)
        data["updated_at"] = format_iso_datetime(value=now)
        if data.get("expiry_date"):
            data["expiry_date"] = format_iso_date(value=data["expiry_date"])

        try:
            response = await anyio.to_thread.run_sync(
                lambda: self.supabase.table("pantry_items").upsert(data).execute(),
            )
        except Exception as exc:
            logger.error(
                "Failed to create pantry item (db/network)",
                exc_info=True,
                extra={"household_id": str(household_id)},
            )
            raise AppError(
                "Failed to create pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        if not getattr(response, "data", None):
            logger.error(
                "Pantry item upsert returned no data",
                extra={"household_id": str(household_id)},
            )
            raise AppError(
                "Pantry item was not created",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        row = response.data[0]
        logger.debug(
            "Pantry item upserted",
            extra={"item_id": row.get("id"), "household_id": str(household_id)},
        )

        embedding_job_enqueued = await _enqueue_embedding_job(
            pantry_item_id=str(row["id"]),
            source_updated_at=_job_source_updated_at_for_row(row),
        )

        logger.info(
            "Pantry item added",
            extra={
                "item_id": row.get("id"),
                "household_id": str(household_id),
                "embedding_job_enqueued": embedding_job_enqueued,
            },
        )
        _retriever_cache.invalidate_household(str(household_id))
        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=True,
            old_quantity=0,
            new_quantity=float(row.get("quantity") or 0),
            message="Pantry item added successfully",
            embedding_generated=False,
        )

    async def add_pantry_item_bulk(
        self,
        pantry_items: List[PantryItemCreate],
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemsBulkCreateResponse:
        await _ensure_user_in_household(
            self.supabase,
            user_id,
            household_id,
            "Bulk add",
        )

        now = datetime.now()
        rows_to_upsert: List[Dict[str, object]] = []
        for item in pantry_items:
            data = item.model_dump()
            data["household_id"] = str(household_id)
            data["owner_id"] = str(user_id)
            data["created_at"] = format_iso_datetime(value=now)
            data["updated_at"] = format_iso_datetime(value=now)
            if data.get("expiry_date"):
                data["expiry_date"] = format_iso_date(value=data["expiry_date"])
            rows_to_upsert.append(data)

        try:
            response = await anyio.to_thread.run_sync(
                lambda: self.supabase.table("pantry_items")
                .upsert(rows_to_upsert)
                .execute(),
            )
        except Exception as exc:
            logger.error(
                "Bulk pantry create failed (db/network)",
                exc_info=True,
                extra={"household_id": str(household_id), "count": len(pantry_items)},
            )
            raise AppError(
                "Failed to create pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        if not getattr(response, "data", None):
            logger.error(
                "Bulk pantry upsert returned no data",
                extra={"household_id": str(household_id)},
            )
            raise AppError(
                "Pantry items were not created",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        created_rows: List[Dict[str, Any]] = list(response.data)

        job_payloads: List[Dict[str, object]] = [
            {
                "pantry_item_id": str(row["id"]),
                "attempt_count": _INITIAL_ATTEMPT_COUNT,
                "source_updated_at": _job_source_updated_at_for_row(row),
            }
            for row in created_rows
        ]

        embeddings_queued = await _enqueue_embedding_jobs_bulk(
            job_payloads=job_payloads,
        )

        bulk_results: List[BulkUpsertResult] = [
            BulkUpsertResult(
                name=row.get("name") or "",
                success=True,
                is_new=True,
                item_id=row.get("id"),
                old_quantity=0.0,
                new_quantity=float(row.get("quantity") or 0),
                error=None,
            )
            for row in created_rows
        ]

        total_requested = len(pantry_items)
        successful = len(bulk_results)
        failed = total_requested - successful

        logger.info(
            "Bulk pantry items added",
            extra={
                "household_id": str(household_id),
                "successful": successful,
                "total": total_requested,
                "embedding_jobs_enqueued": embeddings_queued,
            },
        )
        return PantryItemsBulkCreateResponse(
            total_requested=total_requested,
            successful=successful,
            failed=failed,
            new_items=successful,
            updated_items=0,
            results=bulk_results,
            embeddings_queued=embeddings_queued,
        )

    async def get_my_pantry_items(
        self,
        household_id: UUID,
        user_id: UUID,
    ) -> List[PantryItem]:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .select("*")
                    .eq("household_id", str(household_id))
                    .eq("owner_id", str(user_id))
                    .execute()
                ),
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch pantry items",
                exc_info=True,
                extra={"household_id": str(household_id), "user_id": str(user_id)},
            )
            raise AppError(
                "Failed to fetch pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        return response.data or []

    async def get_household_pantry_items(
        self,
        household_id: UUID,
    ) -> List[PantryItem]:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .select("*")
                    .eq("household_id", str(household_id))
                    .execute()
                ),
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch household pantry items",
                exc_info=True,
                extra={"household_id": str(household_id)},
            )
            raise AppError(
                "Failed to fetch household pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        return response.data or []

    async def update_pantry_item(
        self,
        pantry_item: PantryItemUpsert,
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemUpsertResponse:
        data = pantry_item.model_dump()
        data["updated_at"] = format_iso_datetime(value=datetime.now())
        if data.get("expiry_date"):
            data["expiry_date"] = format_iso_date(value=data["expiry_date"])

        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .update(data)
                    .eq("household_id", str(household_id))
                    .eq("owner_id", str(user_id))
                    .execute()
                ),
            )
        except Exception as exc:
            logger.error(
                "Failed to update pantry item",
                exc_info=True,
                extra={"household_id": str(household_id), "user_id": str(user_id)},
            )
            raise AppError(
                "Failed to update pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        if not getattr(response, "data", None):
            logger.error(
                "Update pantry item: not found or not owned",
                extra={"household_id": str(household_id), "user_id": str(user_id)},
            )
            raise AppError(
                "Pantry item not found or not owned by user",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        row = response.data[0]
        logger.info(
            "Pantry item updated",
            extra={"item_id": str(row.get("id")), "household_id": str(household_id)},
        )

        await _enqueue_embedding_job(
            pantry_item_id=str(row["id"]),
            source_updated_at=_job_source_updated_at_for_row(row),
        )
        _retriever_cache.invalidate_household(str(household_id))
        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=False,
            old_quantity=0.0,
            new_quantity=float(row.get("quantity") or 0),
            message="Pantry item updated successfully",
            embedding_generated=False,
        )

    async def delete_pantry_item(
        self,
        item_id: UUID,
        household_id: UUID,
        user_id: UUID,
    ) -> PantryItemUpsertResponse:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("pantry_items")
                    .delete()
                    .eq("id", str(item_id))
                    .eq("household_id", str(household_id))
                    .eq("owner_id", str(user_id))
                    .execute()
                ),
            )
        except Exception as exc:
            logger.error(
                "Failed to delete pantry item",
                exc_info=True,
                extra={"item_id": str(item_id), "household_id": str(household_id)},
            )
            raise AppError(
                "Failed to delete pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        if not getattr(response, "data", None):
            logger.error(
                "Delete pantry item: not found or not owned",
                extra={"item_id": str(item_id), "household_id": str(household_id)},
            )
            raise AppError(
                "Pantry item not found or not owned by user",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        row = response.data[0]
        logger.info(
            "Pantry item deleted",
            extra={"item_id": str(item_id), "household_id": str(household_id)},
        )
        _retriever_cache.invalidate_household(str(household_id))
        return PantryItemUpsertResponse(
            id=row["id"],
            is_new=False,
            old_quantity=float(row.get("quantity") or 0),
            new_quantity=0.0,
            message="Pantry item deleted successfully",
            embedding_generated=False,
        )


__all__ = ["PantryService"]

