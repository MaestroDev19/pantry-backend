from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from pantry_backend.core.settings import get_settings
from pantry_backend.embedding_worker import process_embedding_jobs_once


router = APIRouter(prefix="/api", tags=["internal-worker"])


@router.post("/run-embedding-worker")
async def run_embedding_worker(request: Request):
    settings = get_settings()
    secret = request.headers.get("x-internal-secret")
    if not secret or secret != settings.embedding_worker_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    processed = process_embedding_jobs_once(
        batch_size=settings.embedding_batch_size,
        max_attempts=8,
    )
    return {"processed": processed}


__all__ = ["router"]

