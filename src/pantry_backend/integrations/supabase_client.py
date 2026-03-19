from __future__ import annotations

from fastapi import Depends
from supabase import Client, create_client

from pantry_backend.core.settings import Settings, get_settings


def get_supabase_client(settings: Settings = Depends(get_settings)) -> Client | None:
    if settings.supabase_url is None:
        return None
    if settings.supabase_service_role_key is not None:
        return create_client(str(settings.supabase_url), settings.supabase_service_role_key)
    if settings.supabase_publishable_key is not None:
        return create_client(str(settings.supabase_url), settings.supabase_publishable_key)
    if settings.supabase_anon_key is not None:
        return create_client(str(settings.supabase_url), settings.supabase_anon_key)

    return None

