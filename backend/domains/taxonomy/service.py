"""Taxonomy service — orchestrates CRUD operations on taxonomy entries.

Business logic lives here; the repository handles only data access. This
layer enforces uniqueness, applies partial updates, and converts DTOs to
entities and back. No HTTP concerns — the router calls the service.
"""

from __future__ import annotations

import fnmatch
import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.agents.app_cache import invalidate_taxonomy_cache
from domains.taxonomy import repository
from domains.taxonomy.dto import (
    AppMatch,
    CategoryCreateRequest,
    CategoryDeleteResponse,
    CategoryListResponse,
    CategorySummary,
    CategoryUpdateRequest,
    CategoryUpdateResponse,
    GroupCount,
    PatternPreviewRequest,
    PatternPreviewResponse,
    SoftwareEntryCreateRequest,
    SoftwareEntryListResponse,
    SoftwareEntryResponse,
    SoftwareEntryUpdateRequest,
)
from domains.taxonomy.entities import SoftwareEntry
from errors import SoftwareEntryNotFoundError, TaxonomyError
from utils.dt import utc_now


def _to_response(entry: SoftwareEntry) -> SoftwareEntryResponse:
    """Convert a SoftwareEntry entity to its response DTO.

    Args:
        entry: Domain entity to convert.

    Returns:
        SoftwareEntryResponse suitable for returning from the API.
    """
    return SoftwareEntryResponse(
        id=entry.id,
        name=entry.name,
        patterns=entry.patterns,
        publisher=entry.publisher,
        category=entry.category,
        category_display=entry.category_display,
        subcategory=entry.subcategory,
        industry=entry.industry,
        description=entry.description,
        is_universal=entry.is_universal,
        user_added=entry.user_added,
        created_at=entry.created_at.isoformat(),
        updated_at=entry.updated_at.isoformat(),
    )


async def list_categories(db: AsyncIOMotorDatabase) -> CategoryListResponse:  # type: ignore[type-arg]
    """Return all taxonomy categories with their entry counts.

    Categories are first-class entities in the taxonomy_categories collection,
    joined with entry counts from software_taxonomy.

    Args:
        db: Motor database handle.

    Returns:
        CategoryListResponse with all categories sorted alphabetically.
    """
    raw = await repository.list_categories(db)
    categories = [
        CategorySummary(
            key=r["key"], display=r.get("display") or r["key"], entry_count=r["entry_count"]
        )
        for r in raw
    ]
    return CategoryListResponse(categories=categories, total=len(categories))


async def create_category(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    request: CategoryCreateRequest,
) -> CategorySummary:
    """Create a new taxonomy category.

    Args:
        db: Motor database handle.
        request: Category key and display label.

    Returns:
        CategorySummary for the newly created category.

    Raises:
        TaxonomyError: If a category with that key already exists.
    """
    existing = await repository.get_category(db, request.key)
    if existing:
        raise TaxonomyError(f"Category '{request.key}' already exists")

    await repository.insert_category(db, request.key, request.display)
    return CategorySummary(key=request.key, display=request.display, entry_count=0)


async def update_category(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    category_key: str,
    request: CategoryUpdateRequest,
) -> CategoryUpdateResponse:
    """Rename a category's key and/or display label across all its entries.

    Args:
        db: Motor database handle.
        category_key: The existing category key.
        request: New key and/or display label (both optional, at least one required).

    Returns:
        CategoryUpdateResponse with the old/new keys and count of modified entries.

    Raises:
        TaxonomyError: If the category does not exist or no fields were provided.
    """
    if request.key is None and request.display is None:
        raise TaxonomyError("Provide at least one of: key, display")

    # Check category exists in taxonomy_categories collection
    cat_doc = await repository.get_category(db, category_key)
    if cat_doc is None:
        raise TaxonomyError(f"Category '{category_key}' not found")

    # AUDIT-039: Rename entries FIRST so that if this step fails, the old
    # category key still points at the correct entries (safe rollback).
    # Then update the category document.  This ordering is more resilient
    # than the reverse because a failure after the entry rename but before
    # the doc update leaves entries orphaned under the new key — but the
    # doc update is a single-document write that is unlikely to fail.
    # True atomicity would require a MongoDB transaction (replica-set only).
    modified = await repository.update_category(
        db,
        category_key,
        new_key=request.key,
        new_display=request.display,
    )

    await repository.update_category_doc(
        db,
        category_key,
        new_key=request.key,
        new_display=request.display,
    )
    new_key = request.key if request.key is not None else category_key
    new_display = (
        request.display if request.display is not None else (cat_doc.get("display") or category_key)
    )
    invalidate_taxonomy_cache()
    return CategoryUpdateResponse(
        old_key=category_key,
        new_key=new_key,
        display=new_display,
        entries_updated=modified,
    )


async def delete_category(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    category_key: str,
) -> CategoryDeleteResponse:
    """Delete all entries in a category.

    Args:
        db: Motor database handle.
        category_key: The category key to delete.

    Returns:
        CategoryDeleteResponse with the key and count of deleted entries.

    Raises:
        TaxonomyError: If the category does not exist.
    """
    cat_doc = await repository.get_category(db, category_key)
    if cat_doc is None:
        raise TaxonomyError(f"Category '{category_key}' not found")

    # Delete all entries in this category
    deleted = await repository.delete_category(db, category_key)
    # Delete the category document itself
    await repository.delete_category_doc(db, category_key)
    invalidate_taxonomy_cache()
    return CategoryDeleteResponse(key=category_key, entries_deleted=deleted)


async def get_entries_by_category(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    category: str,
) -> SoftwareEntryListResponse:
    """Return all taxonomy entries in a given category.

    Args:
        db: Motor database handle.
        category: Category key (e.g. "scada_hmi").

    Returns:
        SoftwareEntryListResponse with entries sorted by name.
    """
    entries = await repository.list_by_category(db, category)
    return SoftwareEntryListResponse(
        entries=[_to_response(e) for e in entries],
        total=len(entries),
    )


async def search_taxonomy(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    query: str,
    limit: int = 50,
) -> SoftwareEntryListResponse:
    """Search taxonomy entries by name.

    Args:
        db: Motor database handle.
        query: Search string — matched case-insensitively against entry names.
        limit: Maximum results.

    Returns:
        SoftwareEntryListResponse with matching entries.
    """
    entries = await repository.search(db, query, limit=limit)
    return SoftwareEntryListResponse(
        entries=[_to_response(e) for e in entries],
        total=len(entries),
    )


async def get_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
) -> SoftwareEntryResponse:
    """Fetch a single taxonomy entry by ID.

    Args:
        db: Motor database handle.
        entry_id: String ObjectId of the entry.

    Returns:
        The entry as a response DTO.

    Raises:
        SoftwareEntryNotFoundError: If no entry with that ID exists.
    """
    entry = await repository.get_by_id(db, entry_id)
    if entry is None:
        raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found")
    return _to_response(entry)


async def add_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    request: SoftwareEntryCreateRequest,
) -> SoftwareEntryResponse:
    """Create a new user-defined taxonomy entry.

    Args:
        db: Motor database handle.
        request: Validated creation payload.

    Returns:
        The newly created entry as a response DTO.
    """
    # Auto-create category if it doesn't exist yet
    existing_cat = await repository.get_category(db, request.category)
    if not existing_cat:
        await repository.insert_category(
            db,
            request.category,
            request.category_display or request.category,
        )

    now = utc_now()
    entry = SoftwareEntry(
        name=request.name,
        patterns=request.patterns,
        publisher=request.publisher,
        category=request.category,
        category_display=request.category_display,
        subcategory=request.subcategory,
        industry=request.industry,
        description=request.description,
        is_universal=request.is_universal,
        user_added=True,
        created_at=now,
        updated_at=now,
    )
    inserted = await repository.insert(db, entry)
    invalidate_taxonomy_cache()
    return _to_response(inserted)


async def edit_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    request: SoftwareEntryUpdateRequest,
) -> SoftwareEntryResponse:
    """Apply a partial update to an existing taxonomy entry.

    Args:
        db: Motor database handle.
        entry_id: String ObjectId of the entry to update.
        request: Partial update payload (only non-None fields are applied).

    Returns:
        The updated entry as a response DTO.

    Raises:
        SoftwareEntryNotFoundError: If the entry does not exist.
    """
    # Build the update dict from non-None fields only
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        # Nothing to update — fetch and return current state
        entry = await repository.get_by_id(db, entry_id)
        if entry is None:
            raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found")
        return _to_response(entry)

    modified = await repository.update(db, entry_id, updates)
    if not modified:
        raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found")

    entry = await repository.get_by_id(db, entry_id)
    if entry is None:
        raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found after update")
    invalidate_taxonomy_cache()
    return _to_response(entry)


async def delete_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
) -> None:
    """Delete a taxonomy entry.

    Args:
        db: Motor database handle.
        entry_id: String ObjectId of the entry to delete.

    Raises:
        SoftwareEntryNotFoundError: If the entry does not exist.
    """
    deleted = await repository.delete(db, entry_id)
    if not deleted:
        raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found")
    invalidate_taxonomy_cache()


async def toggle_universal(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
) -> SoftwareEntryResponse:
    """Toggle the ``is_universal`` flag on an entry.

    Universal entries are excluded from fingerprint suggestion computation.

    Args:
        db: Motor database handle.
        entry_id: String ObjectId of the entry to toggle.

    Returns:
        The updated entry as a response DTO.

    Raises:
        SoftwareEntryNotFoundError: If the entry does not exist.
    """
    entry = await repository.get_by_id(db, entry_id)
    if entry is None:
        raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found")

    await repository.update(db, entry_id, {"is_universal": not entry.is_universal})

    updated = await repository.get_by_id(db, entry_id)
    if updated is None:
        raise SoftwareEntryNotFoundError(f"Taxonomy entry '{entry_id}' not found after toggle")
    return _to_response(updated)


def _patterns_to_matcher(patterns: list[str]) -> re.Pattern[str] | None:
    """Compile a list of glob patterns into a single regex for matching."""
    if not patterns:
        return None
    parts = []
    for p in patterns:
        parts.append(fnmatch.translate(p.lower()))
    # fnmatch.translate produces patterns like (?s:...), combine with OR
    combined = "|".join(parts)
    return re.compile(combined)


async def preview_pattern(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    request: PatternPreviewRequest,
) -> PatternPreviewResponse:
    """Preview which apps and agents match glob patterns.

    Uses the pre-computed ``app_summaries`` collection for fast lookups
    instead of scanning agents with regex. Returns matched app names with
    agent counts and a per-group breakdown.

    Args:
        db: Motor database handle.
        request: Pattern preview request (single or multi-pattern).

    Returns:
        PatternPreviewResponse with matched apps, totals, and group breakdown.
    """
    # Resolve patterns list (multi-pattern takes precedence)
    patterns = request.patterns or ([request.pattern] if request.pattern else [])
    if not patterns:
        return PatternPreviewResponse(
            patterns=[],
            total_apps=0,
            total_agents=0,
            app_matches=[],
            group_counts=[],
        )

    app_matches: list[AppMatch] = []
    group_counts: list[GroupCount] = []
    total_agents = 0

    try:
        # Step 1: Find matching apps in app_summaries (fast, indexed collection)
        matcher = _patterns_to_matcher(patterns)
        if matcher is None:
            return PatternPreviewResponse(
                patterns=patterns,
                total_apps=0,
                total_agents=0,
                app_matches=[],
                group_counts=[],
            )

        # Check if any pattern has a wildcard
        has_wildcard = any("*" in p or "?" in p or "[" in p for p in patterns)

        # Hard limit to prevent OOM on very large fleets
        _PREVIEW_MATCH_LIMIT = 10_000

        if has_wildcard:
            # Scan app_summaries and match in Python (fast — typically <50k docs)
            matched_names: list[str] = []
            async for doc in (
                db["app_summaries"]
                .find(
                    {},
                    {
                        "normalized_name": 1,
                        "display_name": 1,
                        "publisher": 1,
                        "agent_count": 1,
                        "_id": 0,
                    },
                )
                .limit(_PREVIEW_MATCH_LIMIT)
            ):
                nname = doc.get("normalized_name", "")
                if matcher.match(nname):
                    app_matches.append(
                        AppMatch(
                            normalized_name=nname,
                            display_name=doc.get("display_name") or nname,
                            publisher=doc.get("publisher"),
                            agent_count=doc.get("agent_count", 0),
                        )
                    )
                    matched_names.append(nname)
        else:
            # Exact match — direct indexed lookups
            exact_names = [p.lower() for p in patterns]
            matched_names = []
            async for doc in db["app_summaries"].find(
                {"normalized_name": {"$in": exact_names}},
                {
                    "normalized_name": 1,
                    "display_name": 1,
                    "publisher": 1,
                    "agent_count": 1,
                    "_id": 0,
                },
            ):
                nname = doc.get("normalized_name", "")
                app_matches.append(
                    AppMatch(
                        normalized_name=nname,
                        display_name=doc.get("display_name") or nname,
                        publisher=doc.get("publisher"),
                        agent_count=doc.get("agent_count", 0),
                    )
                )
                matched_names.append(nname)

        # Sort by agent_count desc, limit to 50
        app_matches.sort(key=lambda m: m.agent_count, reverse=True)
        app_matches = app_matches[:50]

        # Step 2: Get total unique agent count and group breakdown from s1_agents
        if matched_names:
            agent_filter: dict[str, object] = {"installed_app_names": {"$in": matched_names}}

            total_agents = await db["s1_agents"].count_documents(agent_filter)

            # Group breakdown (top 20)
            group_pipeline: list[dict[str, object]] = [
                {"$match": agent_filter},
                {"$group": {"_id": "$group_name", "agent_count": {"$sum": 1}}},
                {"$sort": {"agent_count": -1}},
                {"$limit": 20},
            ]
            async for doc in db["s1_agents"].aggregate(group_pipeline):
                group_counts.append(
                    GroupCount(
                        group_name=doc.get("_id") or "Unknown",
                        agent_count=doc["agent_count"],
                    )
                )

    except Exception as exc:
        from loguru import logger

        logger.warning("Pattern preview failed (collections may not exist yet): {}", exc)

    return PatternPreviewResponse(
        patterns=patterns,
        total_apps=len(app_matches),
        total_agents=total_agents,
        app_matches=app_matches,
        group_counts=group_counts,
    )
