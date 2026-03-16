"""Taxonomy FastAPI router.

Mounts at /api/v1/taxonomy. All routes are async and depend on the Motor
database via FastAPI dependency injection. DTOs are used at every boundary —
entities never leak out of the service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.entities import UserRole
from domains.taxonomy import service
from domains.taxonomy.dto import (
    CategoryCreateRequest,
    CategoryDeleteResponse,
    CategoryListResponse,
    CategorySummary,
    CategoryUpdateRequest,
    CategoryUpdateResponse,
    PatternPreviewRequest,
    PatternPreviewResponse,
    SoftwareEntryCreateRequest,
    SoftwareEntryListResponse,
    SoftwareEntryResponse,
    SoftwareEntryUpdateRequest,
)
from middleware.auth import get_current_user, require_role

router = APIRouter()


@router.get(
    "/",
    response_model=CategoryListResponse,
    summary="List all taxonomy categories",
    dependencies=[Depends(get_current_user)],
)
async def list_categories(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),
) -> CategoryListResponse:  # type: ignore[type-arg]
    """Return all software taxonomy categories with their entry counts.

    Args:
        db: Motor database (injected).

    Returns:
        CategoryListResponse with all categories sorted by display name.
    """
    return await service.list_categories(db)


@router.post(
    "/category",
    response_model=CategorySummary,
    status_code=201,
    summary="Create a new taxonomy category",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def create_category(
    body: CategoryCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> CategorySummary:
    """Create a new empty taxonomy category.

    Args:
        body: Category key and display label.
        db: Motor database (injected).

    Returns:
        The newly created CategorySummary with HTTP 201.
    """
    return await service.create_category(db, body)


@router.get(
    "/search",
    response_model=SoftwareEntryListResponse,
    summary="Search taxonomy entries",
    dependencies=[Depends(get_current_user)],
)
async def search_taxonomy(
    q: str = Query(min_length=1, description="Search term"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SoftwareEntryListResponse:
    """Search taxonomy entries by name (case-insensitive substring match).

    Args:
        q: Search query string.
        limit: Maximum results to return.
        db: Motor database (injected).

    Returns:
        SoftwareEntryListResponse with matching entries.
    """
    return await service.search_taxonomy(db, q, limit=limit)


@router.get(
    "/category/{category}",
    response_model=SoftwareEntryListResponse,
    summary="Get entries in a category",
    dependencies=[Depends(get_current_user)],
)
async def get_entries_by_category(
    category: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SoftwareEntryListResponse:
    """Return all software entries in a specific taxonomy category.

    Args:
        category: Category key (e.g. "scada_hmi").
        db: Motor database (injected).

    Returns:
        SoftwareEntryListResponse with entries sorted by name.
    """
    return await service.get_entries_by_category(db, category)


@router.patch(
    "/category/{category}",
    response_model=CategoryUpdateResponse,
    summary="Rename a category",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def update_category(
    category: str,
    body: CategoryUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> CategoryUpdateResponse:
    """Rename a category's key and/or display label across all its entries.

    Args:
        category: Current category key.
        body: New key and/or display label.
        db: Motor database (injected).

    Returns:
        CategoryUpdateResponse with old/new keys and count of modified entries.
    """
    return await service.update_category(db, category, body)


@router.delete(
    "/category/{category}",
    response_model=CategoryDeleteResponse,
    summary="Delete a category and all its entries",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def delete_category(
    category: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> CategoryDeleteResponse:
    """Delete all entries in a category.

    Args:
        category: Category key to delete.
        db: Motor database (injected).

    Returns:
        CategoryDeleteResponse with the key and count of deleted entries.
    """
    return await service.delete_category(db, category)


@router.get(
    "/{entry_id}",
    response_model=SoftwareEntryResponse,
    summary="Get a taxonomy entry",
    dependencies=[Depends(get_current_user)],
)
async def get_entry(
    entry_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SoftwareEntryResponse:
    """Fetch a single taxonomy entry by its ID.

    Args:
        entry_id: String ObjectId of the entry.
        db: Motor database (injected).

    Returns:
        The SoftwareEntryResponse for the entry.
    """
    return await service.get_entry(db, entry_id)


@router.post(
    "/",
    response_model=SoftwareEntryResponse,
    status_code=201,
    summary="Add a taxonomy entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def add_entry(
    body: SoftwareEntryCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SoftwareEntryResponse:
    """Add a new software entry to the taxonomy.

    Args:
        body: Validated creation payload.
        db: Motor database (injected).

    Returns:
        The newly created SoftwareEntryResponse with HTTP 201.
    """
    return await service.add_entry(db, body)


@router.patch(
    "/{entry_id}",
    response_model=SoftwareEntryResponse,
    summary="Edit a taxonomy entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def edit_entry(
    entry_id: str,
    body: SoftwareEntryUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SoftwareEntryResponse:
    """Partially update an existing taxonomy entry.

    Args:
        entry_id: String ObjectId of the entry.
        body: Partial update payload.
        db: Motor database (injected).

    Returns:
        The updated SoftwareEntryResponse.
    """
    return await service.edit_entry(db, entry_id, body)


@router.delete(
    "/{entry_id}",
    status_code=204,
    summary="Delete a taxonomy entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def delete_entry(
    entry_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> None:
    """Delete a taxonomy entry by ID.

    Args:
        entry_id: String ObjectId of the entry.
        db: Motor database (injected).
    """
    await service.delete_entry(db, entry_id)


@router.post(
    "/{entry_id}/toggle-universal",
    response_model=SoftwareEntryResponse,
    summary="Toggle universal exclusion flag",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def toggle_universal(
    entry_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SoftwareEntryResponse:
    """Toggle whether an entry is excluded from fingerprint suggestions.

    Args:
        entry_id: String ObjectId of the entry.
        db: Motor database (injected).

    Returns:
        The updated SoftwareEntryResponse.
    """
    return await service.toggle_universal(db, entry_id)


@router.post(
    "/preview",
    response_model=PatternPreviewResponse,
    summary="Preview pattern matches",
    dependencies=[Depends(get_current_user)],
)
async def preview_pattern(
    body: PatternPreviewRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> PatternPreviewResponse:
    """Preview which installed applications and agents would match a glob pattern.

    Useful for validating patterns before saving them to a taxonomy entry.

    Args:
        body: Pattern preview request.
        db: Motor database (injected).

    Returns:
        PatternPreviewResponse with match count and sample agents.
    """
    return await service.preview_pattern(db, body)
