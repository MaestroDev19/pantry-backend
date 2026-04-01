from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Callable
from typing import Any
from uuid import UUID

import anyio
from fastapi import status
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from postgrest.exceptions import APIError
from supabase import Client

from pantry_server.contexts.ai.infrastructure.providers.embeddings_client import embeddings_client
from pantry_server.contexts.pantry.domain.entities import PantryItem
from pantry_server.core.config import get_settings
from pantry_server.core.constants import ITEMS_TABLE_NAME
from pantry_server.core.exceptions import AppError
from pantry_server.shared.pantry_read_cache import (
    cache_key_household,
    cache_key_my_items,
    get_or_set_coroutine,
    invalidate_keys,
)

PANTRY_EMBEDDING_JOBS_TABLE_NAME = "pantry_embedding_jobs"
INLINE_EMBEDDING_TIMEOUT_SECONDS = 2.0
EMBEDDING_JOB_MAX_ATTEMPTS = 5
EMBEDDING_JOB_BATCH_SIZE = 20
EMBEDDING_BACKOFF_BASE_SECONDS = 30
MAX_BULK_ITEMS_PER_REQUEST = 100
MAX_EMBEDDING_JOB_BATCH_SIZE = 20
JITTER_MIN_RATIO = 0.5
JITTER_MAX_RATIO = 1.5

_logger = logging.getLogger(__name__)


def _log_postgrest_insert_failure(
    *,
    operation: str,
    exc: APIError,
    payload: dict[str, Any] | list[dict[str, Any]],
) -> None:
    _logger.error(
        "%s rejected by PostgREST: %s | payload=%s",
        operation,
        json.dumps(exc.json(), default=str),
        json.dumps(payload, default=str),
    )


def _response_data(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _row_to_pantry_item(
    row: dict[str, Any],
    *,
    owner_name: str | None = None,
) -> PantryItem:
    raw_owner = row.get("owner_id")
    return PantryItem(
        id=str(row["id"]),
        household_id=str(row["household_id"]),
        owner_id=str(raw_owner) if raw_owner is not None else None,
        owner_name=owner_name,
        name=str(row["name"]),
        category=str(row["category"]),
        quantity=float(row["quantity"]),
        unit=str(row["unit"]),
        expiry_date=row.get("expiry_date"),
    )


class PantryService:
    def __init__(
        self,
        supabase: Client,
        *,
        embeddings_provider: Callable[[], GoogleGenerativeAIEmbeddings] = embeddings_client,
        inline_embedding_timeout_seconds: float = INLINE_EMBEDDING_TIMEOUT_SECONDS,
    ) -> None:
        self.supabase = supabase
        self._embeddings_provider = embeddings_provider
        self._inline_embedding_timeout_seconds = inline_embedding_timeout_seconds

    async def add_single_item(
        self,
        *,
        owner_id: UUID,
        household_id: UUID,
        item_data: dict[str, object],
    ) -> PantryItem:
        payload = {
            **item_data,
            "owner_id": str(owner_id),
            "household_id": str(household_id),
            "embedding_status": "pending",
        }
        try:
            response = await anyio.to_thread.run_sync(
                lambda: self.supabase.table(ITEMS_TABLE_NAME).insert(payload).execute(),
            )
        except APIError as exc:
            _log_postgrest_insert_failure(
                operation="pantry_items insert (single)",
                exc=exc,
                payload=payload,
            )
            raise AppError(
                "Failed to add pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc
        except Exception as exc:
            _logger.exception(
                "pantry_items insert (single) failed: %s | payload=%s",
                exc,
                json.dumps(payload, default=str),
            )
            raise AppError(
                "Failed to add pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        rows = _response_data(response)
        if not rows:
            raise AppError(
                "Failed to add pantry item",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        row = rows[0]
        embedding_text = self._build_embedding_text(row)

        try:
            with anyio.fail_after(self._inline_embedding_timeout_seconds):
                vector = await anyio.to_thread.run_sync(
                    lambda: self._embeddings_provider().embed_query(embedding_text),
                )
            await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(ITEMS_TABLE_NAME)
                    .update(
                        {
                            "embedding": vector,
                            "embedding_status": "ready",
                            "embedding_updated_at": datetime.now(timezone.utc).isoformat(),
                            "embedding_error": None,
                        }
                    )
                    .eq("id", str(row["id"]))
                    .execute()
                )
            )
        except Exception:
            await self._enqueue_embedding_job(item_id=str(row["id"]))

        await self._invalidate_pantry_list_cache(owner_id=owner_id, household_id=household_id)
        return _row_to_pantry_item(row)

    @staticmethod
    def _build_embedding_text(row: dict[str, Any]) -> str:
        name = str(row.get("name", "")).strip()
        category = str(row.get("category", "")).strip()
        quantity = str(row.get("quantity", "")).strip()
        unit = str(row.get("unit", "")).strip()
        return f"name: {name}\ncategory: {category}\nquantity: {quantity}\nunit: {unit}"

    async def _enqueue_embedding_job(self, *, item_id: str) -> None:
        try:
            await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                    .upsert(
                        {"pantry_item_id": item_id, "status": "queued"},
                        on_conflict="pantry_item_id",
                        ignore_duplicates=True,
                    )
                    .execute()
                )
            )
        except Exception:
            # Preserve request success path even when enqueueing fails.
            return

    async def add_bulk_items(
        self,
        *,
        owner_id: UUID,
        household_id: UUID,
        items_data: list[dict[str, object]],
    ) -> list[PantryItem]:
        if not items_data:
            return []
        if len(items_data) > MAX_BULK_ITEMS_PER_REQUEST:
            raise AppError(
                f"Bulk add supports at most {MAX_BULK_ITEMS_PER_REQUEST} items per request",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        payload = [
            {
                **item_data,
                "owner_id": str(owner_id),
                "household_id": str(household_id),
                "embedding_status": "pending",
            }
            for item_data in items_data
        ]
        try:
            response = await anyio.to_thread.run_sync(
                lambda: self.supabase.table(ITEMS_TABLE_NAME).insert(payload).execute(),
            )
        except APIError as exc:
            _log_postgrest_insert_failure(
                operation="pantry_items insert (bulk)",
                exc=exc,
                payload=payload,
            )
            raise AppError(
                "Failed to add pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc
        except Exception as exc:
            _logger.exception(
                "pantry_items insert (bulk) failed: %s | payload=%s",
                exc,
                json.dumps(payload, default=str),
            )
            raise AppError(
                "Failed to add pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        rows = _response_data(response)
        if rows:
            job_payload = [
                {
                    "pantry_item_id": str(row["id"]),
                    "status": "queued",
                }
                for row in rows
            ]
            try:
                await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                        .upsert(
                            job_payload,
                            on_conflict="pantry_item_id",
                            ignore_duplicates=True,
                        )
                        .execute()
                    )
                )
            except Exception:
                # Bulk insert succeeds even if queue insert is temporarily unavailable.
                pass

        await self._invalidate_pantry_list_cache(owner_id=owner_id, household_id=household_id)
        return [_row_to_pantry_item(row) for row in rows]

    async def process_embedding_jobs(
        self,
        *,
        max_jobs: int = EMBEDDING_JOB_BATCH_SIZE,
        max_attempts: int = EMBEDDING_JOB_MAX_ATTEMPTS,
    ) -> dict[str, int]:
        now_iso = datetime.now(timezone.utc).isoformat()
        effective_max_jobs = min(max_jobs, MAX_EMBEDDING_JOB_BATCH_SIZE)
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                    .select("id, pantry_item_id, attempts, status, next_attempt_at")
                    .eq("status", "queued")
                    .lte("next_attempt_at", now_iso)
                    .limit(effective_max_jobs)
                    .execute()
                )
            )
        except Exception as exc:
            raise AppError(
                "Failed to fetch embedding jobs",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        jobs = _response_data(response)
        processed = 0
        retried = 0
        failed = 0

        for job in jobs:
            job_id = int(job["id"])
            pantry_item_id = str(job["pantry_item_id"])
            attempts = int(job.get("attempts", 0))
            try:
                await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                        .update(
                            {
                                "status": "processing",
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        .eq("id", job_id)
                        .execute()
                    )
                )

                item_response = await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table(ITEMS_TABLE_NAME)
                        .select("id, name, category, quantity, unit")
                        .eq("id", pantry_item_id)
                        .limit(1)
                        .execute()
                    )
                )
                item_rows = _response_data(item_response)
                if not item_rows:
                    raise ValueError(f"Pantry item not found: {pantry_item_id}")

                embedding_text = self._build_embedding_text(item_rows[0])
                with anyio.fail_after(self._inline_embedding_timeout_seconds):
                    vector = await anyio.to_thread.run_sync(
                        lambda: self._embeddings_provider().embed_query(embedding_text),
                    )

                await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table(ITEMS_TABLE_NAME)
                        .update(
                            {
                                "embedding": vector,
                                "embedding_status": "ready",
                                "embedding_updated_at": datetime.now(timezone.utc).isoformat(),
                                "embedding_error": None,
                            }
                        )
                        .eq("id", pantry_item_id)
                        .execute()
                    )
                )
                await anyio.to_thread.run_sync(
                    lambda: (
                        self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                        .update(
                            {
                                "status": "done",
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "last_error": None,
                            }
                        )
                        .eq("id", job_id)
                        .execute()
                    )
                )
                processed += 1
            except Exception as exc:
                next_attempts = attempts + 1
                error_text = str(exc)
                if next_attempts >= max_attempts:
                    await anyio.to_thread.run_sync(
                        lambda: (
                            self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                            .update(
                                {
                                    "status": "failed",
                                    "attempts": next_attempts,
                                    "last_error": error_text,
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            .eq("id", job_id)
                            .execute()
                        )
                    )
                    await anyio.to_thread.run_sync(
                        lambda: (
                            self.supabase.table(ITEMS_TABLE_NAME)
                            .update(
                                {
                                    "embedding_status": "failed",
                                    "embedding_error": error_text,
                                }
                            )
                            .eq("id", pantry_item_id)
                            .execute()
                        )
                    )
                    failed += 1
                else:
                    base_delay_seconds = EMBEDDING_BACKOFF_BASE_SECONDS * (2 ** (next_attempts - 1))
                    jitter_factor = random.uniform(JITTER_MIN_RATIO, JITTER_MAX_RATIO)
                    delay_seconds = base_delay_seconds * jitter_factor
                    next_attempt_at = (
                        datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    ).isoformat()
                    await anyio.to_thread.run_sync(
                        lambda: (
                            self.supabase.table(PANTRY_EMBEDDING_JOBS_TABLE_NAME)
                            .update(
                                {
                                    "status": "queued",
                                    "attempts": next_attempts,
                                    "next_attempt_at": next_attempt_at,
                                    "last_error": error_text,
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            .eq("id", job_id)
                            .execute()
                        )
                    )
                    retried += 1

        return {
            "selected": len(jobs),
            "processed": processed,
            "retried": retried,
            "failed": failed,
        }

    async def _invalidate_pantry_list_cache(self, *, owner_id: UUID, household_id: UUID) -> None:
        if not get_settings().pantry_read_cache_enabled:
            return
        await invalidate_keys(
            cache_key_my_items(str(owner_id)),
            cache_key_household(str(household_id)),
        )

    async def _load_my_items(self, *, owner_id: UUID) -> list[PantryItem]:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(ITEMS_TABLE_NAME)
                    .select(
                        "id, owner_id, household_id, name, category, quantity, unit, expiry_date"
                    )
                    .eq("owner_id", str(owner_id))
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to fetch pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        rows = _response_data(response)
        return [_row_to_pantry_item(row) for row in rows]

    async def _owner_names_for_household(
        self,
        *,
        household_id: UUID,
        owner_ids: list[str],
    ) -> dict[str, str | None]:
        """Resolve display names: owners must be in household_members; name from profiles."""
        if not owner_ids:
            return {}
        try:
            hm_response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("household_members")
                    .select("user_id")
                    .eq("household_id", str(household_id))
                    .in_("user_id", owner_ids)
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to fetch household members for pantry owners",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        member_rows = _response_data(hm_response)
        member_ids = [str(r["user_id"]) for r in member_rows if r.get("user_id")]
        if not member_ids:
            return {}

        try:
            prof_response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table("profiles")
                    .select("id, full_name")
                    .in_("id", member_ids)
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to fetch profiles for pantry owners",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        out: dict[str, str | None] = {}
        for row in _response_data(prof_response):
            uid = row.get("id")
            if uid is None:
                continue
            fn = row.get("full_name")
            out[str(uid)] = str(fn).strip() if isinstance(fn, str) and fn.strip() else None
        return out

    async def _load_household_pantry(self, *, household_id: UUID) -> list[PantryItem]:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(ITEMS_TABLE_NAME)
                    .select(
                        "id, owner_id, household_id, name, category, quantity, unit, expiry_date"
                    )
                    .eq("household_id", str(household_id))
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to fetch household pantry items",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        rows = _response_data(response)
        owner_ids = sorted(
            {str(r["owner_id"]) for r in rows if r.get("owner_id") is not None}
        )
        names_by_owner = await self._owner_names_for_household(
            household_id=household_id,
            owner_ids=owner_ids,
        )
        return [
            _row_to_pantry_item(
                row,
                owner_name=names_by_owner.get(str(row["owner_id"]))
                if row.get("owner_id") is not None
                else None,
            )
            for row in rows
        ]

    async def get_my_items(self, *, owner_id: UUID) -> list[PantryItem]:
        settings = get_settings()
        if not settings.pantry_read_cache_enabled or settings.pantry_read_cache_ttl_seconds <= 0:
            return await self._load_my_items(owner_id=owner_id)
        ttl = float(settings.pantry_read_cache_ttl_seconds)
        return await get_or_set_coroutine(
            cache_key_my_items(str(owner_id)),
            ttl,
            lambda: self._load_my_items(owner_id=owner_id),
        )

    async def get_household_pantry(self, *, household_id: UUID) -> list[PantryItem]:
        settings = get_settings()
        if not settings.pantry_read_cache_enabled or settings.pantry_read_cache_ttl_seconds <= 0:
            return await self._load_household_pantry(household_id=household_id)
        ttl = float(settings.pantry_read_cache_ttl_seconds)
        return await get_or_set_coroutine(
            cache_key_household(str(household_id)),
            ttl,
            lambda: self._load_household_pantry(household_id=household_id),
        )

    async def update_my_item(
        self,
        *,
        item_id: UUID,
        owner_id: UUID,
        updates: dict[str, object],
    ) -> PantryItem:
        if not updates:
            raise AppError(
                "No fields provided for update",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            response = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(ITEMS_TABLE_NAME)
                    .update(updates)
                    .eq("id", str(item_id))
                    .eq("owner_id", str(owner_id))
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to update pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        rows = _response_data(response)
        if not rows:
            raise AppError(
                "Pantry item not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        item = _row_to_pantry_item(rows[0])
        await self._invalidate_pantry_list_cache(
            owner_id=owner_id,
            household_id=UUID(item.household_id),
        )
        return item

    async def delete_my_item(self, *, item_id: UUID, owner_id: UUID) -> dict[str, str]:
        try:
            existing = await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(ITEMS_TABLE_NAME)
                    .select("id, household_id")
                    .eq("id", str(item_id))
                    .eq("owner_id", str(owner_id))
                    .limit(1)
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to delete pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        existing_rows = _response_data(existing)
        if not existing_rows:
            raise AppError(
                "Pantry item not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        household_id_raw = existing_rows[0].get("household_id")
        household_uuid = (
            UUID(str(household_id_raw)) if household_id_raw is not None else None
        )

        try:
            await anyio.to_thread.run_sync(
                lambda: (
                    self.supabase.table(ITEMS_TABLE_NAME)
                    .delete()
                    .eq("id", str(item_id))
                    .eq("owner_id", str(owner_id))
                    .execute()
                ),
            )
        except Exception as exc:
            raise AppError(
                "Failed to delete pantry item",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        if household_uuid is not None:
            await self._invalidate_pantry_list_cache(
                owner_id=owner_id,
                household_id=household_uuid,
            )
        return {"message": "Pantry item deleted"}
