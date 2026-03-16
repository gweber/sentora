"""Library service — business logic for library entries, subscriptions, and ingestion.

Orchestrates repository calls, enforces business rules, converts between
entities and DTOs. No HTTP concerns.

Library entries and ingestion runs live in the shared library database.
Subscriptions and fingerprints live in the tenant database.
"""

from __future__ import annotations

import re

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.library import repository
from domains.library.dto import (
    LibraryEntryCreateRequest,
    LibraryEntryListResponse,
    LibraryEntryResponse,
    LibraryEntryUpdateRequest,
    LibraryMarkerResponse,
    LibraryStatsResponse,
    SubscriptionListResponse,
    SubscriptionResponse,
)
from domains.library.entities import LibraryEntry, LibraryMarker, LibrarySubscription
from errors import LibraryEntryNotFoundError, LibraryError, SubscriptionConflictError
from utils.dt import utc_now

# ── Conversions ──────────────────────────────────────────────────────────────


def _marker_to_response(m: LibraryMarker) -> LibraryMarkerResponse:
    return LibraryMarkerResponse(
        id=m.id,
        pattern=m.pattern,
        display_name=m.display_name,
        category=m.category,
        weight=m.weight,
        source_detail=m.source_detail,
        added_at=m.added_at.isoformat(),
        added_by=m.added_by,
    )


def _entry_to_response(e: LibraryEntry) -> LibraryEntryResponse:
    return LibraryEntryResponse(
        id=e.id,
        name=e.name,
        vendor=e.vendor,
        category=e.category,
        description=e.description,
        tags=e.tags,
        markers=[_marker_to_response(m) for m in e.markers],
        source=e.source,
        upstream_id=e.upstream_id,
        upstream_version=e.upstream_version,
        version=e.version,
        status=e.status,
        subscriber_count=e.subscriber_count,
        submitted_by=e.submitted_by,
        reviewed_by=e.reviewed_by,
        created_at=e.created_at.isoformat(),
        updated_at=e.updated_at.isoformat(),
    )


def _sub_to_response(s: LibrarySubscription, entry_name: str = "") -> SubscriptionResponse:
    return SubscriptionResponse(
        id=s.id,
        group_id=s.group_id,
        library_entry_id=s.library_entry_id,
        entry_name=entry_name,
        synced_version=s.synced_version,
        auto_update=s.auto_update,
        subscribed_at=s.subscribed_at.isoformat(),
        subscribed_by=s.subscribed_by,
        last_synced_at=s.last_synced_at.isoformat() if s.last_synced_at else None,
    )


# ── Library entry CRUD (shared library DB) ───────────────────────────────────


async def list_entries(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    status: str | None = "published",
    source: str | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> LibraryEntryListResponse:
    skip = (page - 1) * page_size
    entries, total = await repository.list_entries(
        db,
        status=status,
        source=source,
        category=category,
        search=search,
        skip=skip,
        limit=page_size,
    )
    return LibraryEntryListResponse(
        entries=[_entry_to_response(e) for e in entries],
        total=total,
    )


async def get_entry(
    db: AsyncIOMotorDatabase,
    entry_id: str,  # type: ignore[type-arg]
) -> LibraryEntryResponse:
    entry = await repository.get_entry(db, entry_id)
    if entry is None:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")
    return _entry_to_response(entry)


async def create_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    request: LibraryEntryCreateRequest,
    submitted_by: str = "system",
) -> LibraryEntryResponse:
    now = utc_now()
    markers: list[LibraryMarker] = []
    if request.markers:
        for m in request.markers:
            markers.append(
                LibraryMarker(
                    pattern=m.pattern,
                    display_name=m.display_name or request.name,
                    category=m.category,
                    weight=m.weight,
                    source_detail=m.source_detail,
                    added_by=submitted_by,
                    added_at=now,
                )
            )

    entry = LibraryEntry(
        name=request.name,
        vendor=request.vendor,
        category=request.category,
        description=request.description,
        tags=request.tags,
        markers=markers,
        source="manual",
        upstream_id=f"manual:{ObjectId()}",
        status="draft",
        submitted_by=submitted_by,
        created_at=now,
        updated_at=now,
    )
    await repository.insert_entry(db, entry)
    return _entry_to_response(entry)


async def update_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    request: LibraryEntryUpdateRequest,
) -> LibraryEntryResponse:
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        return await get_entry(db, entry_id)

    ok = await repository.update_entry(db, entry_id, updates)
    if not ok:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")
    return await get_entry(db, entry_id)


async def delete_entry(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
) -> None:
    # Clean up subscriptions in tenant DB first
    await repository.delete_subscriptions_by_entry(tenant_db, entry_id)
    ok = await repository.delete_entry(library_db, entry_id)
    if not ok:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")


async def publish_entry(
    db: AsyncIOMotorDatabase, entry_id: str, reviewer: str
) -> LibraryEntryResponse:  # type: ignore[type-arg]
    ok = await repository.update_entry(
        db,
        entry_id,
        {
            "status": "published",
            "reviewed_by": reviewer,
        },
    )
    if not ok:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")
    return await get_entry(db, entry_id)


async def deprecate_entry(db: AsyncIOMotorDatabase, entry_id: str) -> LibraryEntryResponse:  # type: ignore[type-arg]
    ok = await repository.update_entry(db, entry_id, {"status": "deprecated"})
    if not ok:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")
    return await get_entry(db, entry_id)


# ── Subscriptions (library_db for entries, tenant_db for subscriptions + fingerprints) ──


async def subscribe(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    group_id: str,
    subscribed_by: str = "system",
    auto_update: bool = True,
) -> SubscriptionResponse:
    # Validate entry exists (shared DB)
    entry = await repository.get_entry(library_db, entry_id)
    if entry is None:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")

    # Check for existing subscription (tenant DB)
    existing = await repository.get_subscription_by_group_entry(tenant_db, group_id, entry_id)
    if existing:
        raise SubscriptionConflictError(
            f"Group '{group_id}' is already subscribed to entry '{entry_id}'"
        )

    sub = LibrarySubscription(
        group_id=group_id,
        library_entry_id=entry_id,
        subscribed_by=subscribed_by,
        auto_update=auto_update,
    )
    await repository.insert_subscription(tenant_db, sub)
    await repository.increment_subscriber_count(library_db, entry_id, 1)

    # Sync markers into the group's fingerprint (tenant DB)
    await _sync_markers_to_group(tenant_db, entry, group_id)
    await repository.update_subscription(
        tenant_db,
        sub.id,
        {
            "synced_version": entry.version,
            "last_synced_at": utc_now(),
        },
    )

    return _sub_to_response(sub, entry_name=entry.name)


async def unsubscribe(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    group_id: str,
) -> None:
    sub = await repository.get_subscription_by_group_entry(tenant_db, group_id, entry_id)
    if sub is None:
        raise LibraryError("Subscription not found")

    # Remove library markers from the group's fingerprint (tenant DB)
    await _remove_library_markers(tenant_db, entry_id, group_id)
    await repository.delete_subscription(tenant_db, sub.id)
    await repository.increment_subscriber_count(library_db, entry_id, -1)


async def list_subscriptions_by_group(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> SubscriptionListResponse:
    subs = await repository.list_subscriptions_by_group(tenant_db, group_id)
    # Batch-fetch all referenced library entries in a single query
    entry_ids = [s.library_entry_id for s in subs]
    entries = await repository.get_entries_by_ids(library_db, entry_ids)
    entry_map = {e.id: e for e in entries}
    responses: list[SubscriptionResponse] = []
    for s in subs:
        entry = entry_map.get(s.library_entry_id)
        responses.append(_sub_to_response(s, entry_name=entry.name if entry else ""))
    return SubscriptionListResponse(subscriptions=responses, total=len(responses))


async def sync_stale_subscriptions(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> int:
    """Find and sync all stale subscriptions. Returns count synced.

    Subscriptions live in tenant_db, entries in library_db. Since they are in
    different databases, we can't use a $lookup. Instead we fetch all
    auto_update subscriptions and compare versions in application code.
    """
    stale = await repository.list_auto_update_subscriptions(tenant_db)
    # Batch-fetch all referenced library entries in a single query
    entry_ids = [sub.library_entry_id for sub in stale]
    entries = await repository.get_entries_by_ids(library_db, entry_ids)
    entry_map = {e.id: e for e in entries}
    count = 0
    for sub in stale:
        entry = entry_map.get(sub.library_entry_id)
        if entry is None:
            continue
        if entry.version <= sub.synced_version:
            continue  # not stale
        await _sync_markers_to_group(tenant_db, entry, sub.group_id)
        await repository.update_subscription(
            tenant_db,
            sub.id,
            {"synced_version": entry.version, "last_synced_at": utc_now()},
        )
        count += 1
    return count


# ── Stats ────────────────────────────────────────────────────────────────────


async def get_stats(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> LibraryStatsResponse:
    stats = await repository.get_stats(library_db, tenant_db)
    return LibraryStatsResponse(**stats)


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _sync_markers_to_group(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry: LibraryEntry,
    group_id: str,
) -> None:
    """Copy library entry markers into a group's fingerprint document.

    Markers are tagged with source="library" and added_by="library:{entry_id}"
    for provenance tracking and clean removal on unsubscribe.

    Operates on the tenant database (fingerprints collection).
    """
    from bson import ObjectId

    now = utc_now()
    provenance = f"library:{entry.id}"

    # Build new markers (pull + push done atomically below)
    new_markers = []
    for m in entry.markers:
        new_markers.append(
            {
                "_id": str(ObjectId()),
                "pattern": m.pattern,
                "display_name": m.display_name,
                "category": m.category,
                "weight": m.weight,
                "source": "library",
                "confidence": 1.0,
                "added_at": now,
                "added_by": provenance,
            }
        )

    if not new_markers:
        return

    # Atomic pull-then-push using an aggregation pipeline update (MongoDB 4.2+).
    # This prevents data loss if the server crashes between two separate
    # update operations.
    await db["fingerprints"].update_one(
        {"group_id": group_id},
        [
            # Stage 1: Remove existing markers from this library entry and
            # set defaults for fields that must exist on new documents.
            {
                "$set": {
                    "markers": {
                        "$filter": {
                            "input": {"$ifNull": ["$markers", []]},
                            "as": "m",
                            "cond": {"$ne": ["$$m.added_by", provenance]},
                        }
                    },
                    "updated_at": now,
                    "group_id": group_id,
                    "group_name": {"$ifNull": ["$group_name", ""]},
                    "site_name": {"$ifNull": ["$site_name", ""]},
                    "account_name": {"$ifNull": ["$account_name", ""]},
                    "created_at": {"$ifNull": ["$created_at", now]},
                    "created_by": {"$ifNull": ["$created_by", "library"]},
                }
            },
            # Stage 2: Append the new markers
            {
                "$set": {
                    "markers": {"$concatArrays": ["$markers", new_markers]},
                }
            },
        ],
        upsert=True,
    )


async def _remove_library_markers(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    group_id: str,
) -> None:
    """Remove all markers from a group's fingerprint that came from a library entry."""
    provenance = f"library:{entry_id}"
    await db["fingerprints"].update_one(
        {"group_id": group_id},
        {
            "$pull": {"markers": {"added_by": provenance}},
            "$set": {"updated_at": utc_now()},
        },
    )


# ── Promote to Taxonomy ─────────────────────────────────────────────────────


async def promote_preview(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
) -> dict:
    """Preview what promoting a library entry to taxonomy would do.

    Returns the proposed category, patterns, and whether it would create
    a new entry or merge into an existing one — without persisting anything.

    Args:
        library_db: Shared library database.
        tenant_db: Tenant database (taxonomy lives here).
        entry_id: Library entry ID to preview.

    Returns:
        Dict with ``name``, ``category``, ``category_display``, ``patterns``,
        ``would_merge``, ``existing_entry_name``.
    """
    entry = await repository.get_entry(library_db, entry_id)
    if entry is None:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")

    patterns = list({m.pattern.strip() for m in entry.markers if m.pattern.strip()})
    category_key = _library_category_to_taxonomy(entry.category, entry.source)
    category_display = category_key.replace("_", " ").title()

    # Check for existing taxonomy entry
    existing = await tenant_db["taxonomy_entries"].find_one(
        {
            "name": {"$regex": f"^{re.escape(entry.name)}$", "$options": "i"},
        }
    )
    existing_patterns = set(p.lower() for p in existing.get("patterns", [])) if existing else set()
    new_patterns = [p for p in patterns if p.lower() not in existing_patterns]

    # Load available categories for the frontend dropdown
    cats_cursor = tenant_db["taxonomy_categories"].find({}, {"key": 1, "display": 1, "_id": 0})
    available_categories = [
        {"key": doc["key"], "display": doc.get("display", doc["key"])} async for doc in cats_cursor
    ]

    return {
        "name": entry.name,
        "vendor": entry.vendor,
        "source": entry.source,
        "category": category_key,
        "category_display": category_display,
        "patterns": patterns,
        "new_patterns": new_patterns,
        "would_merge": existing is not None,
        "existing_entry_name": existing["name"] if existing else None,
        "available_categories": available_categories,
    }


async def promote_to_taxonomy(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    actor: str,
    category_override: str | None = None,
) -> dict:
    """Convert a library entry into a taxonomy entry.

    Extracts patterns from the library entry's markers and creates (or
    merges into) a taxonomy entry.  If a taxonomy entry with the same
    name already exists, new patterns are appended without duplicating.

    Args:
        library_db: Shared library database.
        tenant_db: Tenant database (taxonomy lives here).
        entry_id: Library entry ID to promote.
        actor: Username performing the action.

    Returns:
        Dict with ``taxonomy_entry_id``, ``name``, ``patterns_added``, ``created``.

    Raises:
        LibraryEntryNotFoundError: If the library entry doesn't exist.
    """
    from audit.log import audit
    from domains.taxonomy import repository as taxonomy_repo

    entry = await repository.get_entry(library_db, entry_id)
    if entry is None:
        raise LibraryEntryNotFoundError(f"Library entry '{entry_id}' not found")

    # Extract unique patterns from library markers
    patterns: list[str] = []
    seen: set[str] = set()
    for marker in entry.markers:
        p = marker.pattern.strip()
        if p and p.lower() not in seen:
            patterns.append(p)
            seen.add(p.lower())

    if not patterns:
        raise LibraryError(f"Library entry '{entry.name}' has no marker patterns to promote")

    # Map library category to a taxonomy category key (allow override)
    category_key = category_override or _library_category_to_taxonomy(entry.category, entry.source)
    category_display = category_key.replace("_", " ").title()

    # Ensure the taxonomy category exists
    existing_cat = await tenant_db["taxonomy_categories"].find_one({"key": category_key})
    if not existing_cat:
        from bson import ObjectId as _ObjId

        await tenant_db["taxonomy_categories"].insert_one(
            {
                "_id": str(_ObjId()),
                "key": category_key,
                "display": category_display,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
        )

    # Check if a taxonomy entry with the same name already exists
    existing = await tenant_db["taxonomy_entries"].find_one(
        {
            "name": {"$regex": f"^{re.escape(entry.name)}$", "$options": "i"},
        }
    )

    if existing:
        # Merge patterns — append new ones that don't already exist
        existing_patterns = set(p.lower() for p in existing.get("patterns", []))
        new_patterns = [p for p in patterns if p.lower() not in existing_patterns]
        if new_patterns:
            await tenant_db["taxonomy_entries"].update_one(
                {"_id": existing["_id"]},
                {
                    "$push": {"patterns": {"$each": new_patterns}},
                    "$set": {"updated_at": utc_now()},
                },
            )
        await audit(
            tenant_db,
            domain="library",
            action="library.promoted_to_taxonomy",
            actor=actor,
            summary=(
                f"Merged {len(new_patterns)} patterns from "
                f"'{entry.name}' into existing taxonomy entry"
            ),
            details={
                "library_entry_id": entry_id,
                "taxonomy_entry_id": str(existing["_id"]),
                "patterns_added": new_patterns,
            },
        )
        # Invalidate taxonomy cache so new patterns are picked up
        from domains.agents.app_cache import invalidate_taxonomy_cache

        await invalidate_taxonomy_cache()
        return {
            "taxonomy_entry_id": str(existing["_id"]),
            "name": existing["name"],
            "patterns_added": len(new_patterns),
            "created": False,
        }
    else:
        # Create a new taxonomy entry
        from domains.taxonomy.entities import SoftwareEntry

        new_entry = SoftwareEntry(
            name=entry.name,
            patterns=patterns,
            publisher=entry.vendor or None,
            category=category_key,
            category_display=category_display,
            description=entry.description or None,
            is_universal=False,
            user_added=False,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        inserted = await taxonomy_repo.insert(tenant_db, new_entry)
        inserted_id = inserted.id
        await audit(
            tenant_db,
            domain="library",
            action="library.promoted_to_taxonomy",
            actor=actor,
            summary=(
                f"Created taxonomy entry '{entry.name}' from library with {len(patterns)} patterns"
            ),
            details={
                "library_entry_id": entry_id,
                "taxonomy_entry_id": inserted_id,
                "patterns": patterns,
            },
        )
        from domains.agents.app_cache import invalidate_taxonomy_cache

        await invalidate_taxonomy_cache()
        return {
            "taxonomy_entry_id": inserted_id,
            "name": entry.name,
            "patterns_added": len(patterns),
            "created": True,
        }


def _library_category_to_taxonomy(lib_category: str, source: str) -> str:
    """Map a library adapter category to a taxonomy category key.

    Args:
        lib_category: Category from the library entry (e.g. ``"package_manager"``).
        source: Source adapter name (e.g. ``"chocolatey"``).

    Returns:
        Taxonomy category key string.
    """
    mapping = {
        "package_manager": "utilities",
        "desktop_application": "productivity",
        "attack_malware": "security_threats",
        "attack_tool": "security_tools",
    }
    return mapping.get(lib_category, lib_category)
