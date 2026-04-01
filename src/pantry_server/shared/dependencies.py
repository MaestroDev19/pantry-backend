from fastapi import Depends, Header, HTTPException, status
from supabase import Client, create_client

from pantry_server.core.config import Settings, get_settings
from pantry_server.shared.contracts import AuthContext


async def get_auth_context(x_user_id: str | None = Header(default=None)) -> AuthContext:
    # TODO: Replace with Supabase JWT verification and household claims extraction.
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication header",
        )
    return AuthContext(user_id=x_user_id, household_id="dev-household", roles=["member"])


def get_supabase_client(settings: Settings = Depends(get_settings)) -> Client | None:
    """Server-side client: service role only (not anon/publishable)."""
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        return None
    return create_client(str(settings.supabase_url), settings.supabase_service_role_key)
