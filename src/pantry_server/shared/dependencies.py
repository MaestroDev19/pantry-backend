from fastapi import Depends
from supabase import Client, create_client

from pantry_server.core.config import Settings, get_settings


def get_supabase_client(settings: Settings = Depends(get_settings)) -> Client | None:
    """Server-side client: service role only (not anon/publishable)."""
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        return None
    return create_client(str(settings.supabase_url), settings.supabase_service_role_key)
