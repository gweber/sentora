"""API key authentication middleware and scope enforcement.

Extends the existing auth system to support two authentication methods:
1. JWT (existing) — for user UI sessions
2. API key — for external integrations

The ``AuthContext`` dataclass unifies both auth methods so downstream
code can operate on a single type regardless of how the request was
authenticated.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.api_keys import repository as api_key_repo
from domains.api_keys.entities import expand_scopes
from domains.api_keys.service import hash_key
from utils.dt import ensure_utc, utc_now
from utils.http import client_ip
from utils.rate_limit import RateLimiter


@dataclass
class AuthContext:
    """Unified authentication context for both JWT and API key auth.

    Attributes:
        auth_type: Either "jwt" or "api_key".
        tenant_id: The tenant this request operates on.
        user_id: Username (JWT only, None for API keys).
        api_key_id: API key internal ID (API key auth only).
        api_key_name: API key display name (API key auth only).
        scopes: Expanded set of granted scopes (API key auth only).
    """

    auth_type: str  # "jwt" or "api_key"
    tenant_id: str
    user_id: str | None = None
    user_role: str | None = None
    api_key_id: str | None = None
    api_key_name: str | None = None
    scopes: set[str] = field(default_factory=set)


# ── Per-key rate limiters ────────────────────────────────────────────────────
# Keyed by api_key_id. Each key gets its own pair of limiters.
_minute_limiters: dict[str, RateLimiter] = {}
_hour_limiters: dict[str, RateLimiter] = {}


def _get_minute_limiter(key_id: str, limit: int) -> RateLimiter:
    """Get or create a per-minute rate limiter for an API key."""
    limiter = _minute_limiters.get(key_id)
    if limiter is None or limiter._max != limit:
        limiter = RateLimiter(max_requests=limit, window_seconds=60)
        _minute_limiters[key_id] = limiter
    return limiter


def _get_hour_limiter(key_id: str, limit: int) -> RateLimiter:
    """Get or create a per-hour rate limiter for an API key."""
    limiter = _hour_limiters.get(key_id)
    if limiter is None or limiter._max != limit:
        limiter = RateLimiter(max_requests=limit, window_seconds=3600)
        _hour_limiters[key_id] = limiter
    return limiter


# ── API key extraction ───────────────────────────────────────────────────────


def _extract_api_key(request: Request) -> str | None:
    """Extract an API key from the request headers.

    Checks in order:
    1. Authorization: Bearer sentora_sk_...
    2. X-API-Key: sentora_sk_...

    Returns None if no API key is present.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer sentora_sk_"):
        return auth_header[7:]  # strip "Bearer "

    api_key_header = request.headers.get("X-API-Key", "")
    if api_key_header.startswith("sentora_sk_"):
        return api_key_header

    return None


# ── API key authentication ───────────────────────────────────────────────────


async def _authenticate_api_key(
    raw_key: str,
    request: Request,
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> AuthContext:
    """Validate an API key and return an AuthContext.

    Checks: existence, active status, expiration, rate limits.
    Updates last_used metadata asynchronously.
    """
    key_hash = hash_key(raw_key)

    # Look up including grace period (for rotated keys)
    api_key = await api_key_repo.find_by_hash_including_grace(db, key_hash)

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check if key is in grace period (rotated but not yet expired)
    if not api_key.is_active:
        if api_key.grace_expires_at and ensure_utc(api_key.grace_expires_at) > utc_now():
            # In grace period — allow but log
            logger.debug(
                "API key '{}' used during rotation grace period",
                api_key.name,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key revoked",
            )

    if api_key.expires_at and ensure_utc(api_key.expires_at) < utc_now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired",
        )

    # Per-key rate limiting
    ip = client_ip(request)
    minute_limiter = _get_minute_limiter(api_key.id, api_key.rate_limit_per_minute)
    hour_limiter = _get_hour_limiter(api_key.id, api_key.rate_limit_per_hour)

    if minute_limiter.is_limited(api_key.id) or hour_limiter.is_limited(api_key.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="API key rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    # Touch last_used (fire-and-forget — don't block the response)
    try:
        await api_key_repo.touch(db, api_key.id, ip)
    except Exception:
        logger.warning("Failed to update last_used for API key '{}'", api_key.id)

    return AuthContext(
        auth_type="api_key",
        tenant_id=api_key.tenant_id,
        user_id=None,
        api_key_id=api_key.id,
        api_key_name=api_key.name,
        scopes=expand_scopes(api_key.scopes),
    )


# ── Unified auth dependency ──────────────────────────────────────────────────


async def get_auth_context(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AuthContext:
    """FastAPI dependency that authenticates via JWT or API key.

    Checks in order:
    1. API key in Authorization header or X-API-Key header
    2. JWT Bearer token (existing auth middleware)

    Returns an AuthContext with the appropriate auth_type.
    """
    # Try API key first (check prefix before doing expensive hash lookup)
    raw_key = _extract_api_key(request)
    if raw_key is not None:
        return await _authenticate_api_key(raw_key, request, db)

    # Fall back to JWT auth — manually invoke the same logic as get_current_user
    # but without relying on Depends() which can't be called dynamically.

    from domains.auth.dto import TokenPayload
    from domains.auth.service import verify_token
    from domains.auth.session_revocation import is_session_revoked
    from utils.user_revocation import is_user_revoked

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]
    try:
        payload: TokenPayload = verify_token(token)
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

    if payload.sid and is_session_revoked(payload.sid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Derive tenant_id from the request state (set by TenantMiddleware)
    # or fall back to a default tenant for on-prem
    tenant_id = getattr(getattr(request, "state", None), "tenant_id", "default")
    return AuthContext(
        auth_type="jwt",
        tenant_id=tenant_id,
        user_id=payload.sub,
        user_role=payload.role,
    )


# ── Scope enforcement ────────────────────────────────────────────────────────


def require_scope(scope: str) -> Callable[..., Any]:
    """Create a FastAPI dependency that enforces an API key scope.

    For JWT-authenticated requests, scope enforcement is skipped — those
    are governed by RBAC (``require_role``). Scope enforcement applies
    only to API key authenticated requests.

    Args:
        scope: The required scope (e.g. "agents:read").

    Returns:
        A FastAPI-compatible dependency function.
    """

    async def _check_scope(
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        if auth.auth_type == "api_key" and scope not in auth.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: {scope}",
            )
        return auth

    return _check_scope


def require_user_auth() -> Callable[..., Any]:
    """Create a dependency that rejects API key auth — user-only endpoints.

    Used for management endpoints (creating/revoking API keys) that must
    not be accessible via API keys themselves.
    """

    async def _check_user_auth(
        auth: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        if auth.auth_type != "jwt":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint requires user authentication (JWT). "
                "API keys cannot access it.",
            )
        return auth

    return _check_user_auth
