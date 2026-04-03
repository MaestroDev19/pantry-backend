from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import UUID

import anyio
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from pantry_server.core.config import Settings, get_settings
from pantry_server.core.exceptions import AppError
from pantry_server.observability.logging_events import log_auth_failure
from pantry_server.observability.metrics import record_auth_failure
from pantry_server.shared.dependencies import get_supabase_client

auth_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("pantry_server.auth")


def _auth_fail(*, reason: str) -> None:
    record_auth_failure(reason=reason)
    log_auth_failure(logger, reason=reason)


def _get_supabase_client_dep(settings: Settings = Depends(get_settings)) -> Client:
    client = get_supabase_client(settings)
    if client is None:
        _auth_fail(reason="supabase_not_configured")
        raise AppError(
            "Supabase is not configured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return client


def _get_supabase_client_optional(settings: Settings = Depends(get_settings)) -> Client | None:
    return get_supabase_client(settings)


async def get_current_user(
    settings: Settings = Depends(get_settings),
    x_user_id: str | None = Header(default=None, alias="x-user-id"),
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    supabase: Client | None = Depends(_get_supabase_client_optional),
):
    if settings.auth_allow_x_user_id_header and x_user_id is not None and x_user_id.strip() != "":
        try:
            uid = UUID(x_user_id.strip())
        except ValueError as exc:
            _auth_fail(reason="invalid_x_user_id")
            raise AppError(
                "Invalid X-User-ID header",
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc
        return SimpleNamespace(id=str(uid))

    if supabase is None:
        _auth_fail(reason="supabase_not_configured")
        raise AppError(
            "Supabase is not configured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not credentials:
        _auth_fail(reason="missing_credentials")
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
        _auth_fail(reason="token_validation_failed")
        raise AppError(
            "Could not validate credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not getattr(user_response, "user", None):
        _auth_fail(reason="invalid_token")
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
        _auth_fail(reason="missing_user_id")
        raise AppError(
            "Authenticated user missing user ID",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        resolved_user_id = UUID(str(user_id))
        request.state.user_id = str(resolved_user_id)
        return resolved_user_id
    except Exception as exc:
        _auth_fail(reason="invalid_user_id")
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
        _auth_fail(reason="household_membership_resolve_failed")
        raise AppError(
            "Failed to resolve household membership",
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc

    if not getattr(response, "data", None):
        _auth_fail(reason="no_household_membership")
        raise AppError(
            "User is not a member of any household",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return UUID(response.data[0]["household_id"])
