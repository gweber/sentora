"""Authentication middleware — JWT extraction, session validation, and role-based access control.

Provides FastAPI dependencies for securing endpoints:
- ``get_current_user``: extracts and validates JWT from Authorization header,
  checks the in-memory user revocation cache, and validates the server-side
  session (if ``sid`` claim is present).
- ``require_role(*roles)``: dependency factory for RBAC.
- ``require_platform_role()``: deployment-mode-aware role check.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.auth.service import verify_token
from domains.auth.session_revocation import is_session_revoked
from utils.user_revocation import is_user_revoked

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> TokenPayload:
    """Extract and validate the JWT from the Authorization header.

    Performs three checks:
    1. JWT signature and expiry validation.
    2. In-memory user revocation cache (disabled accounts).
    3. In-memory session revocation cache (revoked sessions).

    This ensures that a revoked session or disabled user is rejected
    within ~30 seconds (cache refresh interval) without a database call
    on every request.

    Args:
        credentials: Bearer token extracted by FastAPI's HTTPBearer.

    Returns:
        Decoded TokenPayload with ``sub`` (username), ``role``, and ``sid``.

    Raises:
        HTTPException 401: If the token is missing, invalid, expired,
            the user has been disabled/revoked, or the session is revoked.
    """
    try:
        payload = verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if is_user_revoked(payload.sub):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check session revocation (if session ID is present in the token)
    if payload.sid:
        if is_session_revoked(payload.sid):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        from loguru import logger

        logger.debug(
            "Token for user {} has no session ID — skipping session check",
            payload.sub,
        )

    return payload


def require_role(*roles: UserRole) -> Callable[..., Any]:
    """Create a FastAPI dependency that enforces role-based access.

    Usage::

        @router.post("/admin-only", dependencies=[Depends(require_role(UserRole.admin))])
        async def admin_endpoint(): ...

    Args:
        *roles: One or more UserRole values that are allowed.

    Returns:
        A FastAPI-compatible dependency function.
    """

    async def _check_role(
        payload: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        # super_admin has all permissions
        if payload.role == UserRole.super_admin.value:
            return payload
        if payload.role not in {r.value for r in roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return _check_role


def require_platform_role() -> Callable[..., Any]:
    """Require super_admin in SaaS mode, admin in on-prem mode.

    Use this for platform-level operations (library sources, tenant management)
    that should be accessible to the top-level admin regardless of deployment mode.

    Returns:
        A FastAPI-compatible dependency function.
    """

    async def _check_platform_role(
        payload: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        from config import get_settings

        settings = get_settings()
        required = UserRole.admin if settings.is_onprem else UserRole.super_admin

        # super_admin always passes
        if payload.role == UserRole.super_admin.value:
            return payload
        if payload.role != required.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return _check_platform_role
