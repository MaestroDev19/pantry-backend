from __future__ import annotations

from fastapi import APIRouter

from pantry_backend.core.settings import get_settings
from pantry_backend.integrations.supabase_client import get_supabase_client


router = APIRouter()

@router.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello, World!"}

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict[str, object]:
    settings = get_settings()
    supabase = get_supabase_client(settings)

    return {
        "status": "ok" if supabase is not None else "degraded",
        "integrations": {"supabase": {"configured": supabase is not None}},
    }

