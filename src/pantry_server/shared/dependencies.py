from __future__ import annotations

from fastapi import Depends
from supabase import create_client

from pantry_server.shared.supabase_types import Client

from pantry_server.contexts.households.application.household_service import HouseholdService
from pantry_server.contexts.pantry.application.pantry_service import PantryService
from pantry_server.core.config import Settings, get_settings
from pantry_server.core.exceptions import AppError


def get_supabase_client(settings: Settings = Depends(get_settings)) -> Client | None:
    """Server-side client: service role only (not anon/publishable)."""
    supabase_url = settings.supabase_url
    service_role_key = settings.supabase_service_role_key or settings.supabase_secret_key

    if supabase_url is None or not service_role_key:
        return None
    return create_client(str(supabase_url), service_role_key)


def require_supabase_client(
    supabase: Client | None = Depends(get_supabase_client),
) -> Client:
    if supabase is None:
        raise AppError("Supabase is not configured", status_code=503)
    return supabase


def get_pantry_service(supabase: Client = Depends(require_supabase_client)) -> PantryService:
    return PantryService(supabase)


def get_household_service(
    supabase: Client = Depends(require_supabase_client),
) -> HouseholdService:
    return HouseholdService(supabase)
