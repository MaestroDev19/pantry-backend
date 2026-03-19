from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from pantry_backend.core.exceptions import AppError
from pantry_backend.core.settings import get_settings
from pantry_backend.integrations.supabase_client import get_supabase_client
from pantry_backend.utils import (
    EMBEDDING_QUEUE_MAIN,
    EMBEDDINGS_TABLE_NAME,
    ITEMS_TABLE_NAME,
)
from pantry_backend.utils.date_time_styling import format_iso_date, format_iso_datetime
from pantry_backend.utils.embedding import embeddings_client


logger = logging.getLogger("pantry_backend.embedding_worker")

ITEMS_TABLE = ITEMS_TABLE_NAME
EMBEDDINGS_TABLE = EMBEDDINGS_TABLE_NAME

QUEUE_MAIN = EMBEDDING_QUEUE_MAIN
QUEUE_DLQ = "pantry_embedding_dlq"
QUEUE_DEAD = "pantry_embedding_dead"

VISIBILITY_TIMEOUT_SECONDS = 30

DEFAULT_MAX_ATTEMPTS = 8
INITIAL_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 15 * 60


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return format_iso_datetime(value=dt)


def _compute_backoff_seconds(*, attempt_count: int) -> int:
    capped_attempt = max(0, attempt_count)
    return min(
        MAX_BACKOFF_SECONDS,
        INITIAL_BACKOFF_SECONDS * (2**capped_attempt),
    )


def _get_service_client():
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise AppError("Supabase is not configured", status_code=500)
    return client


@dataclass(frozen=True)
class _QueueMessage:
    msg_id: int
    pantry_item_id: str
    attempt_count: int
    source_updated_at: Optional[str]
    last_error: Optional[str]


def _parse_queue_message(record: Dict[str, Any]) -> _QueueMessage:
    raw_payload = record.get("message") or {}
    if not isinstance(raw_payload, dict):
        raw_payload = {}

    return _QueueMessage(
        msg_id=int(record.get("msg_id") or record.get("message_id")),
        pantry_item_id=str(raw_payload.get("pantry_item_id")),
        attempt_count=int(raw_payload.get("attempt_count") or 0),
        source_updated_at=(
            str(raw_payload.get("source_updated_at"))
            if raw_payload.get("source_updated_at") is not None
            else None
        ),
        last_error=(
            str(raw_payload.get("last_error"))
            if raw_payload.get("last_error") is not None
            else None
        ),
    )


def _read_queue_messages(*, queue_name: str, batch_size: int) -> List[_QueueMessage]:
    client = _get_service_client()
    response = client.schema("pgmq_public").rpc(
        "read",
        {
            "queue_name": queue_name,
            "sleep_seconds": VISIBILITY_TIMEOUT_SECONDS,
            "n": batch_size,
        },
    ).execute()
    records = list(getattr(response, "data", None) or [])
    return [_parse_queue_message(r) for r in records]


def _delete_queue_message(*, queue_name: str, msg_id: int) -> None:
    client = _get_service_client()
    client.schema("pgmq_public").rpc(
        "delete",
        {"queue_name": queue_name, "message_id": msg_id},
    ).execute()


def _send_queue_message(
    *,
    queue_name: str,
    payload: Dict[str, Any],
    sleep_seconds: int,
) -> None:
    client = _get_service_client()
    client.schema("pgmq_public").rpc(
        "send",
        {
            "queue_name": queue_name,
            "message": payload,
            "sleep_seconds": sleep_seconds,
        },
    ).execute()

def _embedding_content_for_row(row: Dict[str, Any]) -> str:
    name = row.get("name") or ""
    category = row.get("category") or ""
    return f"{name} {category}".strip()


def _embedding_metadata_for_row(row: Dict[str, Any]) -> Dict[str, Optional[str]]:
    name = row.get("name") or ""
    category = row.get("category") or ""
    expiry_raw = row.get("expiry_date")
    return {
        "pantry_item_id": str(row["id"]) if row.get("id") is not None else None,
        "name": name or None,
        "category": category or None,
        "quantity": str(row["quantity"]) if row.get("quantity") is not None else None,
        "unit": row.get("unit"),
        "expiry_date": (
            format_iso_date(value=expiry_raw) if expiry_raw is not None else None
        ),
        "owner_id": str(row["owner_id"]) if row.get("owner_id") is not None else None,
        "household_id": (
            str(row["household_id"]) if row.get("household_id") is not None else None
        ),
        "expiry_visible": row.get("expiry_visible"),
    }

def _process_queue_messages_batch(
    *,
    messages: List[_QueueMessage],
    source_queue_name: str,
    max_attempts: int,
) -> int:
    if not messages:
        return 0

    client = _get_service_client()
    pantry_item_ids = [msg.pantry_item_id for msg in messages]

    response = (
        client.table(ITEMS_TABLE)
        .select("*")
        .in_("id", pantry_item_ids)
        .execute()
    )
    rows = list(getattr(response, "data", None) or [])
    row_by_id = {
        str(row.get("id")): row for row in rows if row.get("id") is not None
    }

    missing_msgs = [msg for msg in messages if msg.pantry_item_id not in row_by_id]
    for msg in missing_msgs:
        _send_queue_message(
            queue_name=QUEUE_DEAD,
            payload={
                "pantry_item_id": msg.pantry_item_id,
                "attempt_count": msg.attempt_count,
                "source_updated_at": msg.source_updated_at,
                "last_error": "pantry item not found",
            },
            sleep_seconds=0,
        )
        _delete_queue_message(queue_name=source_queue_name, msg_id=msg.msg_id)

    found_msgs = [msg for msg in messages if msg.pantry_item_id in row_by_id]
    if not found_msgs:
        return len(messages)

    found_rows = [row_by_id[msg.pantry_item_id] for msg in found_msgs]
    contents = [_embedding_content_for_row(row) for row in found_rows]

    try:
        vectors = embeddings_client().embed_documents(contents)
        if len(vectors) != len(found_msgs):
            raise ValueError(
                f"embedding count mismatch (expected={len(found_msgs)} actual={len(vectors)})"
            )

        metadata_list = [_embedding_metadata_for_row(row) for row in found_rows]
        now_iso = _to_iso(_now_utc())
        embedding_rows = [
            {
                "pantry_item_id": msg.pantry_item_id,
                "content": content,
                "metadata": metadata,
                "embedding": vector,
                "created_at": now_iso,
            }
            for msg, content, metadata, vector in zip(
                found_msgs,
                contents,
                metadata_list,
                vectors,
            )
        ]

        client.table(EMBEDDINGS_TABLE).upsert(
            embedding_rows,
            on_conflict="pantry_item_id",
        ).execute()

        for msg in found_msgs:
            _delete_queue_message(queue_name=source_queue_name, msg_id=msg.msg_id)

        return len(messages)
    except Exception as exc:  # pragma: no cover
        error_text = str(exc)
        logger.warning(
            "Embedding worker batch failed; scheduling retry/dead (batch_size=%s error=%s)",
            len(found_msgs),
            error_text,
        )

        for msg in found_msgs:
            next_attempt_count = msg.attempt_count + 1
            if next_attempt_count >= max_attempts:
                queue_name = QUEUE_DEAD
                sleep_seconds = 0
            else:
                queue_name = QUEUE_DLQ
                sleep_seconds = _compute_backoff_seconds(
                    attempt_count=next_attempt_count,
                )

            _send_queue_message(
                queue_name=queue_name,
                payload={
                    "pantry_item_id": msg.pantry_item_id,
                    "attempt_count": next_attempt_count,
                    "source_updated_at": msg.source_updated_at,
                    "last_error": error_text,
                },
                sleep_seconds=sleep_seconds,
            )
            _delete_queue_message(queue_name=source_queue_name, msg_id=msg.msg_id)

        return len(messages)

def process_embedding_jobs_once(*, batch_size: int, max_attempts: int) -> int:
    dlq_messages = _read_queue_messages(queue_name=QUEUE_DLQ, batch_size=batch_size)
    remaining = max(0, batch_size - len(dlq_messages))
    main_messages = (
        _read_queue_messages(queue_name=QUEUE_MAIN, batch_size=remaining)
        if remaining > 0
        else []
    )

    processed = _process_queue_messages_batch(
        messages=dlq_messages,
        source_queue_name=QUEUE_DLQ,
        max_attempts=max_attempts,
    )
    processed += _process_queue_messages_batch(
        messages=main_messages,
        source_queue_name=QUEUE_MAIN,
        max_attempts=max_attempts,
    )
    return processed


def run_embedding_worker_loop(
    *,
    interval_seconds: int,
    batch_size: int,
    max_attempts: int,
) -> None:
    while True:
        processed = process_embedding_jobs_once(
            batch_size=batch_size,
            max_attempts=max_attempts,
        )
        if processed:
            logger.info("Processed embedding jobs", extra={"count": processed})
        time.sleep(interval_seconds)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Pantry embedding job worker")
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.embedding_batch_size,
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=settings.embedding_worker_interval,
    )
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> None:
    settings = get_settings()
    args = _parse_args(argv)
    if not settings.enable_background_workers:
        return
    if args.once:
        process_embedding_jobs_once(
            batch_size=args.batch_size,
            max_attempts=args.max_attempts,
        )
        return
    run_embedding_worker_loop(
        interval_seconds=args.interval_seconds,
        batch_size=args.batch_size,
        max_attempts=args.max_attempts,
    )


if __name__ == "__main__":  # pragma: no cover
    main()

