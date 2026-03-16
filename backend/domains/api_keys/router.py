"""API Keys domain router — CRUD, rotation, and self-info endpoints.

Management endpoints (create, list, update, revoke, rotate) require
user authentication (JWT) with admin or super_admin role.
The /current endpoint is accessible via API key auth for self-inspection.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.api_keys import service
from domains.api_keys.dto import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyCurrentResponse,
    APIKeyResponse,
    APIKeyRotateResponse,
    APIKeyUpdateRequest,
)
from domains.api_keys.middleware import AuthContext, get_auth_context

router = APIRouter()


# ── Combined auth dependency: JWT-only + admin role ──────────────────────────


async def _require_admin_user(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Require JWT user auth with admin or super_admin role.

    Rejects API key auth entirely — key management endpoints must not
    be accessible via API keys themselves.
    """
    if auth.auth_type != "jwt":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires user authentication (JWT). API keys cannot access it.",
        )
    if auth.user_role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return auth


# ── Management endpoints (JWT user-auth only, admin+) ────────────────────────


@router.post(
    "/",
    response_model=APIKeyCreateResponse,
    status_code=201,
)
async def create_api_key(
    req: APIKeyCreateRequest,
    auth: AuthContext = Depends(_require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> APIKeyCreateResponse:
    """Create a new API key. The full key is returned ONCE in the response."""
    return await service.create_api_key(
        db,
        req,
        tenant_id=auth.tenant_id,
        created_by=auth.user_id or "unknown",
    )


@router.get(
    "/",
    response_model=list[APIKeyResponse],
)
async def list_api_keys(
    auth: AuthContext = Depends(_require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[APIKeyResponse]:
    """List all API keys for the current tenant (prefix only, never the full key)."""
    return await service.list_api_keys(db, auth.tenant_id)


@router.get(
    "/current",
    response_model=APIKeyCurrentResponse,
)
async def get_current_api_key(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> APIKeyCurrentResponse:
    """Return info about the currently authenticated API key ("who am I?")."""
    if auth.auth_type != "api_key" or auth.api_key_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only accessible via API key authentication",
        )
    return await service.get_current_key_info(db, auth.api_key_id)


@router.get(
    "/{key_id}",
    response_model=APIKeyResponse,
)
async def get_api_key(
    key_id: str,
    auth: AuthContext = Depends(_require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> APIKeyResponse:
    """Get details of a specific API key."""
    return await service.get_api_key(db, key_id, auth.tenant_id)


@router.put(
    "/{key_id}",
    response_model=APIKeyResponse,
)
async def update_api_key(
    key_id: str,
    req: APIKeyUpdateRequest,
    auth: AuthContext = Depends(_require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> APIKeyResponse:
    """Update an API key's metadata (name, scopes, limits — not the key itself)."""
    return await service.update_api_key(
        db,
        key_id,
        req,
        tenant_id=auth.tenant_id,
        updated_by=auth.user_id or "unknown",
    )


@router.delete(
    "/{key_id}",
    status_code=204,
)
async def revoke_api_key(
    key_id: str,
    auth: AuthContext = Depends(_require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Revoke an API key immediately."""
    await service.revoke_api_key(
        db,
        key_id,
        tenant_id=auth.tenant_id,
        revoked_by=auth.user_id or "unknown",
    )
    return Response(status_code=204)


@router.post(
    "/{key_id}/rotate",
    response_model=APIKeyRotateResponse,
)
async def rotate_api_key(
    key_id: str,
    auth: AuthContext = Depends(_require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> APIKeyRotateResponse:
    """Rotate an API key. Creates a new key; old key remains valid for 5 minutes."""
    return await service.rotate_api_key(
        db,
        key_id,
        tenant_id=auth.tenant_id,
        rotated_by=auth.user_id or "unknown",
    )
