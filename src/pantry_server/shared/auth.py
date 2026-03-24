from __future__ import annotations

from uuid import UUID

import anyio
from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from pantry_server.core.config import Settings, get_settings
from pantry_server.core.exceptions import AppError
from pantry_server.shared.dependencies import get_supabase_client

auth_scheme = HTTPBearer(auto_error=False)


def _get_supabase_client_dep(settings: Settings = Depends(get_settings)) -> Client:
    client = get_supabase_client(settings)
    if client is None:
        raise AppError(
            "Supabase is not configured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    supabase: Client = Depends(_get_supabase_client_dep),
):
    if not credentials:
        raise AppError(
            "Missing authentication credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_response = await anyio.to_thread.run_sync(
            lambda: supabase.auth.get_user(credentials.credentials),
        )
    except Exception as exc:
        raise AppError(
            "Could not validate credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not getattr(user_response, "user", None):
        raise AppError(
            "Invalid authentication credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_response.user


async def get_current_user_id(
    request: Request,
    user=Depends(get_current_user),
) -> UUID:
    user_id = getattr(user, "id", None)
    if not user_id:
        raise AppError(
            "Authenticated user missing user ID",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        resolved_user_id = UUID(str(user_id))
        request.state.user_id = str(resolved_user_id)
        return resolved_user_id
    except Exception as exc:
        raise AppError(
            "Authenticated user has invalid user ID",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc


async def get_current_household_id(
    user_id: UUID = Depends(get_current_user_id),
    supabase: Client = Depends(_get_supabase_client_dep),
) -> UUID:
    try:
        response = await anyio.to_thread.run_sync(
            lambda: (
                supabase.table("household_members")
                .select("household_id")
                .eq("user_id", str(user_id))
                .limit(1)
                .execute()
            ),
        )
    except Exception as exc:
        raise AppError(
            "Failed to resolve household membership",
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc

    if not getattr(response, "data", None):
        raise AppError(
            "User is not a member of any household",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return UUID(response.data[0]["household_id"])
