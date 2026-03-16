"""Tenant management router.

Super-admin CRUD endpoints for managing tenants.
Only available when multi-tenancy is enabled.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from config import get_settings
from db_indexes import ensure_all_indexes
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from middleware.auth import get_current_user, require_role

from . import repository
from .dto import (
    TenantCreateRequest,
    TenantListResponse,
    TenantResponse,
    TenantUpdateRequest,
)
from .entities import Tenant

router = APIRouter()


def _to_response(t: Tenant) -> TenantResponse:
    return TenantResponse(
        id=t.id,
        name=t.name,
        slug=t.slug,
        database_name=t.database_name,
        created_at=t.created_at,
        disabled=t.disabled,
        plan=t.plan,
    )


def _check_enabled() -> None:
    """Raise 404 if multi-tenancy is not enabled."""
    if not get_settings().multi_tenancy_enabled:
        raise HTTPException(status_code=404, detail="Multi-tenancy is not enabled")


def _get_master_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Return the master database for tenant registry operations."""
    from database import get_client

    settings = get_settings()
    return get_client()[settings.master_db_name]


@router.get(
    "/",
    response_model=TenantListResponse,
    dependencies=[Depends(require_role(UserRole.super_admin))],
)
async def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> TenantListResponse:
    """List all tenants (super-admin only)."""
    _check_enabled()
    db = _get_master_db()
    tenants, total = await repository.list_all(db, skip=skip, limit=limit)
    return TenantListResponse(
        tenants=[_to_response(t) for t in tenants],
        total=total,
    )


@router.post(
    "/",
    response_model=TenantResponse,
    status_code=201,
    dependencies=[Depends(require_role(UserRole.super_admin))],
)
async def create_tenant(
    payload: TenantCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
) -> TenantResponse:
    """Create a new tenant with an isolated database."""
    _check_enabled()
    db = _get_master_db()

    # Check slug uniqueness
    existing = await repository.get_by_slug(db, payload.slug)
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Tenant with slug '{payload.slug}' already exists"
        )

    tenant = Tenant(name=payload.name, slug=payload.slug, plan=payload.plan)
    created = await repository.create(db, tenant)

    # Ensure indexes on the new tenant database
    try:
        from database import get_client

        tenant_db = get_client()[created.database_name]
        await ensure_all_indexes(tenant_db)
        logger.info("Indexes created for tenant database '{}'", created.database_name)
    except Exception as exc:
        logger.opt(exception=True).error(
            "Failed to create indexes for tenant '{}': {}", created.slug, exc
        )
        # Record the failure so it can be retried later
        await repository.update(
            _get_master_db(),
            created.slug,
            {"index_status": "failed", "index_error": str(exc)},
        )

    await audit(
        db,
        domain="tenant",
        action="tenant.created",
        actor=current_user.sub,
        summary=f"Created tenant '{created.name}' (slug={created.slug})",
        details={"slug": created.slug, "database": created.database_name},
    )

    return _to_response(created)


@router.get(
    "/{slug}",
    response_model=TenantResponse,
    dependencies=[Depends(require_role(UserRole.super_admin))],
)
async def get_tenant(slug: str) -> TenantResponse:
    """Get a tenant by slug."""
    _check_enabled()
    db = _get_master_db()
    tenant = await repository.get_by_slug(db, slug)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")
    return _to_response(tenant)


@router.patch(
    "/{slug}",
    response_model=TenantResponse,
    dependencies=[Depends(require_role(UserRole.super_admin))],
)
async def update_tenant(
    slug: str,
    payload: TenantUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user),
) -> TenantResponse:
    """Update a tenant."""
    _check_enabled()
    db = _get_master_db()

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = await repository.update(db, slug, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    await audit(
        db,
        domain="tenant",
        action="tenant.updated",
        actor=current_user.sub,
        summary=f"Updated tenant '{slug}': {', '.join(f'{k}={v}' for k, v in updates.items())}",
        details={"slug": slug, "changes": updates},
    )

    return _to_response(updated)


@router.delete(
    "/{slug}",
    status_code=204,
    dependencies=[Depends(require_role(UserRole.super_admin))],
)
async def delete_tenant(slug: str, current_user: TokenPayload = Depends(get_current_user)) -> None:
    """Delete a tenant and optionally drop its database."""
    _check_enabled()
    db = _get_master_db()

    tenant = await repository.get_by_slug(db, slug)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    deleted = await repository.delete(db, slug)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")

    # Note: we do NOT auto-drop the tenant database for safety.
    # Admins must manually drop it via MongoDB CLI if desired.
    logger.warning(
        "Tenant '{}' deleted. Database '{}' was NOT dropped — drop manually if needed.",
        slug,
        tenant.database_name,
    )

    await audit(
        db,
        domain="tenant",
        action="tenant.deleted",
        actor=current_user.sub,
        summary=f"Deleted tenant '{slug}'",
        details={"slug": slug, "database": tenant.database_name},
    )
