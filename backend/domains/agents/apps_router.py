"""Apps router — fleet-wide application inventory and per-app detail.

GET /api/v1/apps/
  Paginated list from the pre-computed ``app_summaries`` collection.
  No heavy aggregation — reads are instant.

GET /api/v1/apps/{normalized_name}
  Returns aggregate detail: per-agent list, version distribution, publisher,
  risk-level breakdown, and taxonomy match (if any).

POST /api/v1/apps/rebuild-cache
  Force-rebuild the app_summaries materialized view.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from database import get_tenant_db
from domains.agents.app_cache import (
    get_detail_matcher,
    rebuild_app_summaries,
)
from domains.auth.entities import UserRole
from middleware.auth import get_current_user, require_role

router = APIRouter()


# ── Response DTOs ──────────────────────────────────────────────────────────────


class AppListItem(BaseModel):
    normalized_name: str
    display_name: str
    publisher: str | None
    agent_count: int
    category: str | None
    category_display: str | None


class AppListResponse(BaseModel):
    apps: list[AppListItem]
    total: int
    page: int
    limit: int


class AppVersionRow(BaseModel):
    version: str
    count: int


class AppAgentRow(BaseModel):
    agent_id: str
    hostname: str
    group_id: str
    group_name: str
    site_id: str
    site_name: str
    os_type: str
    version: str | None
    installed_at: str | None
    last_active: str | None


class AppTaxonomyMatch(BaseModel):
    name: str
    category: str
    subcategory: str | None
    publisher: str | None
    is_universal: bool


class AppDetailResponse(BaseModel):
    normalized_name: str
    display_name: str
    publisher: str | None
    risk_level: str | None
    agent_count: int
    group_count: int
    site_count: int
    versions: list[AppVersionRow]
    risk_distribution: dict[str, int]
    agents: list[AppAgentRow]
    taxonomy_match: AppTaxonomyMatch | None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _most_common(values: list[str | None]) -> str | None:
    """Return the most frequently occurring non-null value, or None."""
    from collections import Counter

    non_null = [v for v in values if v]
    if not non_null:
        return None
    return Counter(non_null).most_common(1)[0][0]


# ── List endpoint (must be before the path catch-all) ─────────────────────────


@router.get("/", response_model=AppListResponse, dependencies=[Depends(get_current_user)])
async def list_apps(
    q: str = Query(default="", description="Case-insensitive search on normalised name"),
    sort: str = Query(default="agent_count", description="Sort field: agent_count | name"),
    order: str = Query(default="desc", description="Sort order: asc | desc"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppListResponse:
    """Return a paginated list of all distinct applications in the fleet.

    Reads from the pre-computed ``app_summaries`` collection for instant response.
    Falls back to live aggregation if summaries haven't been built yet.
    """
    collection = "app_summaries"

    # Check if materialized view exists
    count_check = await db[collection].estimated_document_count()
    if count_check == 0:
        # Fall back to live aggregation (first run before any sync)
        return await _list_apps_live(db, q, sort, order, page, limit)

    # Build filter
    query_filter: dict = {}
    if q:
        query_filter["normalized_name"] = {"$regex": re.escape(q), "$options": "i"}

    # Count
    total = await db[collection].count_documents(query_filter)

    # Sort
    sort_field = "agent_count" if sort == "agent_count" else "normalized_name"
    sort_dir = -1 if order == "desc" else 1

    # Fetch page
    cursor = (
        db[collection]
        .find(query_filter, {"_id": 0})
        .sort(sort_field, sort_dir)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    rows = [doc async for doc in cursor]

    apps = [
        AppListItem(
            normalized_name=r["normalized_name"],
            display_name=r.get("display_name") or r["normalized_name"],
            publisher=r.get("publisher"),
            agent_count=r.get("agent_count", 0),
            category=r.get("category"),
            category_display=r.get("category_display"),
        )
        for r in rows
    ]

    return AppListResponse(apps=apps, total=total, page=page, limit=limit)


async def _list_apps_live(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    q: str,
    sort: str,
    order: str,
    page: int,
    limit: int,
) -> AppListResponse:
    """Fallback: live aggregation when app_summaries hasn't been built yet."""
    from domains.agents.app_cache import get_taxonomy_matcher
    from domains.sync.app_filters import active_filter

    match_stage: dict = active_filter()
    if q:
        match_stage["normalized_name"] = {"$regex": re.escape(q), "$options": "i"}

    pipeline: list[dict] = [{"$match": match_stage}]
    pipeline.extend(
        [
            {
                "$group": {
                    "_id": "$normalized_name",
                    "display_name": {"$first": "$name"},
                    "publisher": {"$first": "$publisher"},
                    "agents": {"$addToSet": "$agent_id"},
                }
            },
            {"$addFields": {"agent_count": {"$size": "$agents"}}},
            {"$project": {"agents": 0}},
        ]
    )

    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = [
        doc
        async for doc in db["s1_installed_apps"].aggregate(
            count_pipeline,
            allowDiskUse=True,
        )
    ]
    total = count_result[0]["total"] if count_result else 0

    sort_field = "agent_count" if sort == "agent_count" else "_id"
    sort_dir = -1 if order == "desc" else 1
    pipeline.append({"$sort": {sort_field: sort_dir}})
    pipeline.append({"$skip": (page - 1) * limit})
    pipeline.append({"$limit": limit})

    rows = [
        doc
        async for doc in db["s1_installed_apps"].aggregate(
            pipeline,
            allowDiskUse=True,
        )
    ]

    matcher = await get_taxonomy_matcher(db)

    apps: list[AppListItem] = []
    for r in rows:
        nname = r["_id"]
        cat, cat_display = matcher.match(nname)
        apps.append(
            AppListItem(
                normalized_name=nname,
                display_name=r.get("display_name") or nname,
                publisher=r.get("publisher"),
                agent_count=r["agent_count"],
                category=cat,
                category_display=cat_display,
            )
        )

    return AppListResponse(apps=apps, total=total, page=page, limit=limit)


# ── Rebuild endpoint ──────────────────────────────────────────────────────────


@router.post("/rebuild-cache", dependencies=[Depends(require_role(UserRole.admin))])
async def rebuild_cache(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Force-rebuild the app_summaries materialized view."""
    count = await rebuild_app_summaries(db)
    return {"status": "ok", "apps_cached": count}


# ── Detail endpoint ───────────────────────────────────────────────────────────


@router.get(
    "/{normalized_name:path}",
    response_model=AppDetailResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_app_detail(
    normalized_name: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppDetailResponse:
    """Return fleet-wide detail for a normalised application name.

    Aggregates across ``s1_installed_apps`` to build:

    - Per-agent rows (hostname, group, site, OS, version, installed_at)
    - Version distribution sorted by prevalence
    - Risk-level distribution from S1 metadata
    - Taxonomy entry if any pattern matches the normalised name

    Returns 404 when no installed-app records exist for the name.
    """
    from fastapi import HTTPException

    normalized_name = unquote(normalized_name)

    # ── Aggregate one row per agent that has this app ──────────────────────
    from domains.sync.app_filters import active_match_stage

    pipeline: list[dict] = [
        active_match_stage(normalized_name=normalized_name),
        {
            "$group": {
                "_id": "$agent_id",
                "name": {"$first": "$name"},
                "publisher": {"$first": "$publisher"},
                "version": {"$first": "$version"},
                "os_type": {"$first": "$os_type"},
                "risk_level": {"$first": "$risk_level"},
                "installed_at": {"$first": "$installed_at"},
            }
        },
    ]
    # Cap the agent detail to prevent multi-hundred-MB responses for universal
    # apps (e.g. "windows defender" installed on all 150k agents).  Summary
    # stats (versions, risk) are computed from the full set; agent rows are
    # capped at 500 for the response payload.
    _AGENT_DETAIL_CAP = 500

    app_rows = [doc async for doc in db["s1_installed_apps"].aggregate(pipeline)]
    if not app_rows:
        raise HTTPException(status_code=404, detail="Application not found")

    display_name = _most_common([r.get("name") for r in app_rows]) or normalized_name
    publisher = _most_common([r.get("publisher") for r in app_rows])
    risk_level = _most_common([r.get("risk_level") for r in app_rows])
    total_agent_count = len(app_rows)
    # Only fetch full agent details for the first N rows to bound response size
    capped_rows = app_rows[:_AGENT_DETAIL_CAP]
    agent_ids = [r["_id"] for r in capped_rows]
    app_by_agent = {r["_id"]: r for r in capped_rows}

    # ── Version distribution ───────────────────────────────────────────────
    version_counts: dict[str, int] = {}
    for r in app_rows:
        v = r.get("version") or "unknown"
        version_counts[v] = version_counts.get(v, 0) + 1
    versions = [
        AppVersionRow(version=v, count=c)
        for v, c in sorted(version_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # ── Group/site counts from full set (not capped) ─────────────────────
    # Use $lookup to resolve agent → group/site in MongoDB, avoiding a
    # 150k-element $in clause for universal apps.
    group_site_pipeline = [
        active_match_stage(normalized_name=normalized_name),
        {"$group": {"_id": "$agent_id"}},
        {
            "$lookup": {
                "from": "s1_agents",
                "localField": "_id",
                "foreignField": "s1_agent_id",
                "as": "_a",
                "pipeline": [{"$project": {"group_id": 1, "site_id": 1, "_id": 0}}],
            }
        },
        {"$unwind": "$_a"},
        {
            "$group": {
                "_id": None,
                "groups": {"$addToSet": "$_a.group_id"},
                "sites": {"$addToSet": "$_a.site_id"},
            }
        },
    ]
    gs_result = await db["s1_installed_apps"].aggregate(group_site_pipeline).to_list(1)
    if gs_result:
        true_group_count = len([g for g in gs_result[0].get("groups", []) if g])
        true_site_count = len([s for s in gs_result[0].get("sites", []) if s])
    else:
        true_group_count = 0
        true_site_count = 0

    # ── Risk-level distribution ────────────────────────────────────────────
    risk_counts: dict[str, int] = {}
    for r in app_rows:
        rl = r.get("risk_level") or "unknown"
        risk_counts[rl] = risk_counts.get(rl, 0) + 1

    # ── Full agent records ─────────────────────────────────────────────────
    group_ids: set[str] = set()
    site_ids: set[str] = set()
    agents: list[AppAgentRow] = []

    async for a in db["s1_agents"].find(
        {"s1_agent_id": {"$in": agent_ids}},
        {
            "_id": 0,
            "s1_agent_id": 1,
            "hostname": 1,
            "group_id": 1,
            "group_name": 1,
            "site_id": 1,
            "site_name": 1,
            "os_type": 1,
            "last_active": 1,
        },
    ):
        aid = a["s1_agent_id"]
        app = app_by_agent.get(aid, {})
        if gid := a.get("group_id"):
            group_ids.add(gid)
        if sid := a.get("site_id"):
            site_ids.add(sid)
        agents.append(
            AppAgentRow(
                agent_id=aid,
                hostname=a.get("hostname") or aid,
                group_id=a.get("group_id") or "",
                group_name=a.get("group_name") or "",
                site_id=a.get("site_id") or "",
                site_name=a.get("site_name") or "",
                os_type=a.get("os_type") or app.get("os_type") or "",
                version=app.get("version"),
                installed_at=app.get("installed_at"),
                last_active=a.get("last_active"),
            )
        )

    agents.sort(key=lambda x: x.hostname.lower())

    # ── Taxonomy pattern match (cached matcher) ───────────────────────────
    taxonomy_match: AppTaxonomyMatch | None = None
    detail_matcher = await get_detail_matcher(db)
    entry = detail_matcher.match(normalized_name)
    if entry:
        taxonomy_match = AppTaxonomyMatch(
            name=entry["name"],
            category=entry.get("category", ""),
            subcategory=entry.get("subcategory"),
            publisher=entry.get("publisher"),
            is_universal=entry.get("is_universal", False),
        )

    return AppDetailResponse(
        normalized_name=normalized_name,
        display_name=display_name,
        publisher=publisher,
        risk_level=risk_level,
        agent_count=total_agent_count,
        group_count=true_group_count,
        site_count=true_site_count,
        versions=versions,
        risk_distribution=risk_counts,
        agents=agents,
        taxonomy_match=taxonomy_match,
    )
