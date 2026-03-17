"""Export domain service.

Builds the software inventory export from app_summaries, enriched
with CPE and EOL data.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.sources.collections import AGENTS, INSTALLED_APPS

from domains.export.dto import (
    CpeInfo,
    EolInfo,
    ExportMetadata,
    PaginationInfo,
    SoftwareInventoryExportResponse,
    SoftwareInventoryItem,
)
from utils.dt import utc_now

# Cache TTL in seconds (1 hour)
CACHE_TTL_SECONDS = 3600


async def build_software_inventory(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    include_eol: bool = True,
    include_cpe: bool = True,
    scope_groups: list[str] | None = None,
    scope_tags: list[str] | None = None,
    classification: str | None = None,
    page: int = 1,
    page_size: int = 1000,
) -> SoftwareInventoryExportResponse:
    """Build the CPE-enriched software inventory export.

    Reads from the pre-computed ``app_summaries`` collection and enriches
    with CPE data from library entries and EOL lifecycle data.

    Args:
        db: Motor database handle.
        include_eol: Include EOL lifecycle data.
        include_cpe: Include CPE identifiers.
        scope_groups: Filter by groups.
        scope_tags: Filter by tags.
        classification: Filter by classification status.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Full export response with metadata, inventory items, and pagination.
    """
    now = utc_now()

    # Check cache
    cache_key = _build_cache_key(
        include_eol=include_eol,
        include_cpe=include_cpe,
        scope_groups=scope_groups,
        scope_tags=scope_tags,
        classification=classification,
        page=page,
        page_size=page_size,
    )
    cached = await _get_cached(db, cache_key)
    if cached:
        return cached

    # Build query filter
    query: dict[str, Any] = {}
    if classification:
        # Map classification to category patterns
        query["category"] = {"$regex": f"^{classification}", "$options": "i"}

    # If scope filters are provided, we need to find apps seen on matching agents
    if scope_groups or scope_tags:
        agent_filter: dict[str, Any] = {}
        if scope_groups:
            agent_filter["group_name"] = {"$in": scope_groups}
        if scope_tags:
            agent_filter["tags"] = {"$all": scope_tags}

        agent_ids: list[str] = []
        async for agent in db[AGENTS].find(agent_filter, {"source_id": 1}):
            agent_ids.append(agent["source_id"])

        if agent_ids:
            app_names: set[str] = set()
            async for app in db[INSTALLED_APPS].find(
                {"agent_id": {"$in": agent_ids}},
                {"normalized_name": 1},
            ):
                app_names.add(app["normalized_name"])
            query["normalized_name"] = {"$in": list(app_names)}
        else:
            # No matching agents — return empty
            return SoftwareInventoryExportResponse(
                export_metadata=ExportMetadata(
                    generated_at=now,
                    total_agents=0,
                    total_unique_apps=0,
                    filters_applied=_build_filter_info(scope_groups, scope_tags, classification),
                ),
                software_inventory=[],
                pagination=PaginationInfo(
                    page=page,
                    page_size=page_size,
                    total_items=0,
                    total_pages=0,
                ),
            )

    # Count totals
    total_items = await db["app_summaries"].count_documents(query)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    skip = (page - 1) * page_size

    # Load CPE data if requested
    cpe_lookup: dict[str, CpeInfo] = {}
    if include_cpe:
        cpe_lookup = await _build_cpe_lookup(db)

    # Fetch app summaries
    items: list[SoftwareInventoryItem] = []
    async for doc in (
        db["app_summaries"].find(query).sort("agent_count", -1).skip(skip).limit(page_size)
    ):
        nname = doc["normalized_name"]
        display_name = doc.get("display_name", nname)
        publisher = doc.get("publisher")
        agent_count = doc.get("agent_count", 0)
        category = doc.get("category_display") or doc.get("category")

        # Most common version from pre-computed app_summaries cache
        doc_versions = doc.get("versions")
        version = doc_versions[0]["version"] if doc_versions else None

        # Build CPE info
        cpe_info = cpe_lookup.get(nname) if include_cpe else None

        # Build EOL info
        eol_info = None
        if include_eol and "eol_match" in doc:
            match = doc["eol_match"]
            eol_info = EolInfo(
                product_id=match.get("eol_product_id"),
                cycle=match.get("matched_cycle"),
                eol_date=match.get("eol_date"),
                is_eol=match.get("is_eol", False),
                is_security_only=match.get("is_security_only", False),
                support_end=match.get("support_end"),
            )

        items.append(
            SoftwareInventoryItem(
                app_name=display_name,
                app_version=version,
                publisher=publisher,
                classification=category,
                install_count=agent_count,
                agent_count=agent_count,
                cpe=cpe_info,
                eol=eol_info,
                taxonomy_categories=[category] if category else [],
            )
        )

    # Get total agent count
    total_agents = await db[AGENTS].estimated_document_count()

    result = SoftwareInventoryExportResponse(
        export_metadata=ExportMetadata(
            generated_at=now,
            total_agents=total_agents,
            total_unique_apps=total_items,
            filters_applied=_build_filter_info(scope_groups, scope_tags, classification),
        ),
        software_inventory=items,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )

    # Cache the result
    await _cache_result(db, cache_key, result)

    return result


async def _build_cpe_lookup(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, CpeInfo]:
    """Build a CPE lookup from library entries.

    Args:
        db: Motor database handle.

    Returns:
        Mapping of normalized app name → CPE info.
    """
    lookup: dict[str, CpeInfo] = {}
    async for entry in db["library_entries"].find(
        {"source": "nist_cpe"},
        {"upstream_id": 1, "markers": 1, "name": 1},
    ):
        upstream_id = entry.get("upstream_id", "")
        # upstream_id is "vendor:product" (dedup key from nist_cpe adapter)
        if ":" not in upstream_id:
            continue
        vendor, _, product = upstream_id.partition(":")
        if not vendor or not product:
            continue

        cpe_info = CpeInfo(
            cpe_uri=f"cpe:2.3:a:{vendor}:{product}:*:*:*:*:*:*:*:*",
            vendor=vendor,
            product=product,
            match_confidence=0.9,
        )

        # Map via marker patterns
        for marker in entry.get("markers", []):
            pattern = marker.get("pattern", "").lower().strip("*")
            if pattern and len(pattern) > 2:
                lookup[pattern] = cpe_info

    return lookup


def _build_cache_key(**kwargs: object) -> str:
    """Build a deterministic cache key from export parameters.

    Args:
        **kwargs: Export filter parameters.

    Returns:
        SHA256 hex digest of the serialized parameters.
    """
    serialized = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def _get_cached(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    cache_key: str,
) -> SoftwareInventoryExportResponse | None:
    """Look up a cached export result.

    Args:
        db: Motor database handle.
        cache_key: Cache key hash.

    Returns:
        Cached response or ``None`` if expired/missing.
    """
    doc = await db["export_cache"].find_one({"cache_key": cache_key})
    if not doc:
        return None

    created_at = doc.get("created_at")
    if created_at and (utc_now() - created_at).total_seconds() > CACHE_TTL_SECONDS:
        return None

    try:
        return SoftwareInventoryExportResponse.model_validate(doc["data"])
    except Exception:
        return None


async def _cache_result(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    cache_key: str,
    result: SoftwareInventoryExportResponse,
) -> None:
    """Cache an export result.

    Args:
        db: Motor database handle.
        cache_key: Cache key hash.
        result: Export response to cache.
    """
    try:
        await db["export_cache"].update_one(
            {"cache_key": cache_key},
            {
                "$set": {
                    "cache_key": cache_key,
                    "data": result.model_dump(mode="json"),
                    "created_at": utc_now(),
                }
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning("Failed to cache export result: {}", exc)


def _build_filter_info(
    scope_groups: list[str] | None,
    scope_tags: list[str] | None,
    classification: str | None,
) -> dict[str, Any]:
    """Build filter info dict for export metadata.

    Args:
        scope_groups: Group filter.
        scope_tags: Tag filter.
        classification: Classification filter.

    Returns:
        Dict describing the applied filters.
    """
    filters: dict[str, Any] = {}
    if scope_groups:
        filters["scope_groups"] = scope_groups
    if scope_tags:
        filters["scope_tags"] = scope_tags
    if classification:
        filters["classification"] = classification
    return filters
