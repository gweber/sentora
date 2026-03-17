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
from typing import Any, Literal
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from database import get_tenant_db
from domains.agents.app_cache import (
    get_detail_matcher,
    rebuild_app_summaries,
)
from domains.auth.entities import UserRole
from domains.sources.collections import AGENTS, INSTALLED_APPS
from middleware.auth import get_current_user, require_role

router = APIRouter()


# ── Response DTOs ──────────────────────────────────────────────────────────────


class AppEolInfo(BaseModel):
    """EOL lifecycle mapping for an application."""

    eol_product_id: str
    match_source: str
    match_confidence: float


class AppListItem(BaseModel):
    normalized_name: str
    display_name: str
    publisher: str | None
    agent_count: int
    category: str | None
    category_display: str | None
    eol: AppEolInfo | None = None


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


class NameCountRow(BaseModel):
    """A name + count pair for group/site/version breakdowns."""

    name: str
    count: int


class AppVersionEolStatus(BaseModel):
    """EOL lifecycle status for a specific version of an application."""

    version: str
    agent_count: int
    cycle: str | None = None
    is_eol: bool = False
    eol_date: str | None = None
    is_security_only: bool = False
    support_end: str | None = None


class AppEolDetail(BaseModel):
    """Full EOL lifecycle detail for an application."""

    eol_product_id: str
    product_name: str
    match_source: str
    match_confidence: float
    versions: list[AppVersionEolStatus] = Field(default_factory=list)


class AppDetailResponse(BaseModel):
    """Detail view for a single application across the fleet."""

    normalized_name: str
    display_name: str
    publisher: str | None
    risk_level: str | None
    agent_count: int
    group_count: int
    site_count: int
    versions: list[AppVersionRow]
    risk_distribution: dict[str, int]
    group_breakdown: list[NameCountRow]
    site_breakdown: list[NameCountRow]
    agents: list[AppAgentRow]
    taxonomy_match: AppTaxonomyMatch | None
    eol: AppEolDetail | None = None
    page: int = 1
    page_size: int = 100
    filtered_agent_count: int | None = None


class AppStatsResponse(BaseModel):
    """Stats, breakdowns, taxonomy, and EOL for an application (no agent list)."""

    normalized_name: str
    display_name: str
    publisher: str | None
    risk_level: str | None
    agent_count: int
    group_count: int
    site_count: int
    versions: list[AppVersionRow]
    risk_distribution: dict[str, int]
    group_breakdown: list[NameCountRow]
    site_breakdown: list[NameCountRow]
    taxonomy_match: AppTaxonomyMatch | None
    eol: AppEolDetail | None = None


class AppAgentsResponse(BaseModel):
    """Paginated agent list for an application (lightweight, no stats)."""

    agents: list[AppAgentRow]
    total: int
    page: int
    page_size: int


# ── Query parameter DTOs ───────────────────────────────────────────────────────


class AppListQuery(BaseModel):
    """Validated query parameters for the app list endpoint."""

    q: str = Field(default="", max_length=200, description="Search on normalised name")
    sort: Literal["agent_count", "name"] = Field(default="agent_count")
    order: Literal["asc", "desc"] = Field(default="desc")
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=100, ge=1, le=500)


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
    params: AppListQuery = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppListResponse:
    """Return a paginated list of all distinct applications in the fleet.

    Reads from the pre-computed ``app_summaries`` collection for instant response.
    Falls back to live aggregation if summaries haven't been built yet.
    """
    q, sort, order, page, limit = params.q, params.sort, params.order, params.page, params.limit
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

    apps = []
    for r in rows:
        eol_data = r.get("eol_match")
        eol_info = None
        if eol_data and isinstance(eol_data, dict):
            eol_info = AppEolInfo(
                eol_product_id=eol_data.get("eol_product_id", ""),
                match_source=eol_data.get("match_source", ""),
                match_confidence=eol_data.get("match_confidence", 0.0),
            )
        apps.append(
            AppListItem(
                normalized_name=r["normalized_name"],
                display_name=r.get("display_name") or r["normalized_name"],
                publisher=r.get("publisher"),
                agent_count=r.get("agent_count", 0),
                category=r.get("category"),
                category_display=r.get("category_display"),
                eol=eol_info,
            )
        )

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
        async for doc in db[INSTALLED_APPS].aggregate(
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
        async for doc in db[INSTALLED_APPS].aggregate(
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


# ── Export endpoint ───────────────────────────────────────────────────────────


@router.get(
    "/export/{normalized_name:path}",
    dependencies=[Depends(get_current_user)],
)
async def export_app_agents(
    normalized_name: str,
    format: Literal["csv", "json"] = Query(default="csv"),
    group_name: list[str] = Query(default=[]),
    site_name: list[str] = Query(default=[]),
    version: list[str] = Query(default=[]),
    search: str | None = Query(default=None, max_length=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:  # type: ignore[override]
    """Export all agents for an application (with filters) as CSV or JSON.

    Unlike the detail endpoint, this does not paginate — it returns the
    full filtered result set.
    """
    import csv as csv_mod
    import io

    from fastapi.responses import StreamingResponse

    from domains.sync.app_filters import active_match_stage

    normalized_name = unquote(normalized_name)

    pipeline: list[dict[str, Any]] = [
        active_match_stage(normalized_name=normalized_name),
        {
            "$group": {
                "_id": "$agent_id",
                "version": {"$first": "$version"},
                "installed_at": {"$first": "$installed_at"},
                "os_type": {"$first": "$os_type"},
            }
        },
        {
            "$lookup": {
                "from": AGENTS,
                "localField": "_id",
                "foreignField": "source_id",
                "as": "_a",
                "pipeline": [
                    {
                        "$project": {
                            "_id": 0,
                            "hostname": 1,
                            "group_name": 1,
                            "site_name": 1,
                            "os_type": 1,
                            "last_active": 1,
                        }
                    }
                ],
            }
        },
        {"$unwind": {"path": "$_a", "preserveNullAndEmptyArrays": True}},
    ]

    # Apply filters
    filt: dict[str, Any] = {}
    if group_name:
        filt["_a.group_name"] = {"$in": group_name} if len(group_name) > 1 else group_name[0]
    if site_name:
        filt["_a.site_name"] = {"$in": site_name} if len(site_name) > 1 else site_name[0]
    if version:
        filt["version"] = {"$in": version} if len(version) > 1 else version[0]
    if search:
        filt["_a.hostname"] = {"$regex": re.escape(search), "$options": "i"}
    if filt:
        pipeline.append({"$match": filt})

    pipeline.append({"$sort": {"_a.hostname": 1}})

    rows: list[dict[str, str]] = []
    async for doc in db[INSTALLED_APPS].aggregate(pipeline):
        a = doc.get("_a") or {}
        rows.append(
            {
                "hostname": a.get("hostname") or doc["_id"],
                "group": a.get("group_name") or "",
                "site": a.get("site_name") or "",
                "os": a.get("os_type") or doc.get("os_type") or "",
                "version": doc.get("version") or "",
                "installed_at": doc.get("installed_at") or "",
                "last_active": a.get("last_active") or "",
            }
        )

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", normalized_name)

    if format == "json":
        from fastapi.responses import JSONResponse

        return JSONResponse(
            content=rows,
            headers={"Content-Disposition": f'attachment; filename="{safe_name}-agents.json"'},
        )

    # CSV
    buf = io.StringIO()
    writer = csv_mod.DictWriter(
        buf,
        fieldnames=["hostname", "group", "site", "os", "version", "installed_at", "last_active"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-agents.csv"'},
    )


# ── Split endpoints: stats + agents ──────────────────────────────────────────


@router.get(
    "/stats/{normalized_name:path}",
    response_model=AppStatsResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_app_stats(
    normalized_name: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppStatsResponse:
    """Return pre-computed stats, breakdowns, taxonomy, and EOL for an application.

    Reads from the ``app_summaries`` materialized collection — a single
    ``find_one()`` instead of an expensive aggregation pipeline.  The
    cache is rebuilt after every sync.

    Use ``/agents/{name}`` for the paginated agent list.
    """
    from fastapi import HTTPException

    normalized_name = unquote(normalized_name)

    doc = await db["app_summaries"].find_one(
        {"normalized_name": normalized_name},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Application not found")

    versions = [
        AppVersionRow(version=v["version"], count=v["count"]) for v in doc.get("versions", [])
    ]

    # Taxonomy match (in-memory, fast)
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

    # EOL lifecycle evaluation (per-version)
    eol_detail: AppEolDetail | None = None
    eol_match = doc.get("eol_match")
    if eol_match:
        pid = eol_match.get("eol_product_id", "")
        if pid:
            from domains.eol.matching import extract_cycle_match
            from domains.eol.repository import get_all_products_with_cycles

            all_cycles = await get_all_products_with_cycles(db)
            cycles = all_cycles.get(pid, [])
            product_doc = await db["eol_products"].find_one({"product_id": pid}, {"name": 1})
            product_name = product_doc["name"] if product_doc else pid
            version_eol: list[AppVersionEolStatus] = []
            for v in versions:
                cycle = extract_cycle_match(v.version, cycles)
                if cycle:
                    version_eol.append(
                        AppVersionEolStatus(
                            version=v.version,
                            agent_count=v.count,
                            cycle=cycle.cycle,
                            is_eol=cycle.is_eol,
                            eol_date=(cycle.eol_date.isoformat() if cycle.eol_date else None),
                            is_security_only=cycle.is_security_only,
                            support_end=(
                                cycle.support_end.isoformat() if cycle.support_end else None
                            ),
                        )
                    )
                else:
                    version_eol.append(AppVersionEolStatus(version=v.version, agent_count=v.count))
            eol_detail = AppEolDetail(
                eol_product_id=pid,
                product_name=product_name,
                match_source=eol_match.get("match_source", ""),
                match_confidence=eol_match.get("match_confidence", 0.0),
                versions=version_eol,
            )

    return AppStatsResponse(
        normalized_name=normalized_name,
        display_name=doc.get("display_name") or normalized_name,
        publisher=doc.get("publisher"),
        risk_level=doc.get("risk_level"),
        agent_count=doc.get("agent_count", 0),
        group_count=doc.get("group_count", 0),
        site_count=doc.get("site_count", 0),
        versions=versions,
        risk_distribution=doc.get("risk_distribution", {}),
        group_breakdown=[
            NameCountRow(name=g["name"], count=g["count"]) for g in doc.get("group_breakdown", [])
        ],
        site_breakdown=[
            NameCountRow(name=s["name"], count=s["count"]) for s in doc.get("site_breakdown", [])
        ],
        taxonomy_match=taxonomy_match,
        eol=eol_detail,
    )


@router.get(
    "/agents/{normalized_name:path}",
    response_model=AppAgentsResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_app_agents(
    normalized_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    group_name: list[str] = Query(default=[]),
    site_name: list[str] = Query(default=[]),
    version: list[str] = Query(default=[]),
    search: str | None = Query(default=None, max_length=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppAgentsResponse:
    """Return a paginated, filterable agent list for an application.

    Lightweight — only runs the agent lookup pipeline with pagination.
    Use ``/stats/{name}`` for stats and breakdowns.
    """
    normalized_name = unquote(normalized_name)
    from domains.sync.app_filters import active_match_stage

    base_match = active_match_stage(normalized_name=normalized_name)
    skip = (page - 1) * page_size

    pipeline: list[dict[str, Any]] = [
        base_match,
        {
            "$group": {
                "_id": "$agent_id",
                "version": {"$first": "$version"},
                "installed_at": {"$first": "$installed_at"},
                "os_type": {"$first": "$os_type"},
            }
        },
        {
            "$lookup": {
                "from": AGENTS,
                "localField": "_id",
                "foreignField": "source_id",
                "as": "_a",
                "pipeline": [
                    {
                        "$project": {
                            "_id": 0,
                            "hostname": 1,
                            "group_id": 1,
                            "group_name": 1,
                            "site_id": 1,
                            "site_name": 1,
                            "os_type": 1,
                            "last_active": 1,
                        }
                    }
                ],
            }
        },
        {"$unwind": {"path": "$_a", "preserveNullAndEmptyArrays": True}},
    ]

    agent_filter: dict[str, Any] = {}
    if group_name:
        agent_filter["_a.group_name"] = (
            {"$in": group_name} if len(group_name) > 1 else group_name[0]
        )
    if site_name:
        agent_filter["_a.site_name"] = {"$in": site_name} if len(site_name) > 1 else site_name[0]
    if version:
        agent_filter["version"] = {"$in": version} if len(version) > 1 else version[0]
    if search:
        agent_filter["_a.hostname"] = {"$regex": re.escape(search), "$options": "i"}
    if agent_filter:
        pipeline.append({"$match": agent_filter})

    pipeline.append(
        {
            "$facet": {
                "count": [{"$count": "n"}],
                "rows": [
                    {"$sort": {"_a.hostname": 1}},
                    {"$skip": skip},
                    {"$limit": page_size},
                ],
            }
        }
    )

    result = await db[INSTALLED_APPS].aggregate(pipeline).to_list(1)
    facet = result[0] if result else {"count": [], "rows": []}
    total = facet["count"][0]["n"] if facet["count"] else 0

    agents: list[AppAgentRow] = []
    for doc in facet.get("rows", []):
        a = doc.get("_a") or {}
        agents.append(
            AppAgentRow(
                agent_id=doc["_id"],
                hostname=a.get("hostname") or doc["_id"],
                group_id=a.get("group_id") or "",
                group_name=a.get("group_name") or "",
                site_id=a.get("site_id") or "",
                site_name=a.get("site_name") or "",
                os_type=a.get("os_type") or doc.get("os_type") or "",
                version=doc.get("version"),
                installed_at=doc.get("installed_at"),
                last_active=a.get("last_active"),
            )
        )

    return AppAgentsResponse(agents=agents, total=total, page=page, page_size=page_size)


# ── Detail endpoint (legacy — kept for backwards compatibility) ──────────────


@router.get(
    "/{normalized_name:path}",
    response_model=AppDetailResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_app_detail(
    normalized_name: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    group_name: list[str] = Query(default=[]),
    site_name: list[str] = Query(default=[]),
    version: list[str] = Query(default=[]),
    search: str | None = Query(default=None, max_length=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppDetailResponse:
    """Return fleet-wide detail for a normalised application name.

    Aggregates across ``installed_apps`` to build:

    - Per-agent rows (hostname, group, site, OS, version, installed_at)
    - Version distribution sorted by prevalence
    - Risk-level distribution from source metadata
    - Taxonomy entry if any pattern matches the normalised name

    Returns 404 when no installed-app records exist for the name.

    Performance: stats+breakdown run as one pipeline, the paginated agent
    list runs concurrently via ``asyncio.gather``.
    """
    import asyncio

    from fastapi import HTTPException

    normalized_name = unquote(normalized_name)
    group_names = group_name
    site_names = site_name
    version_filters = version

    from domains.sync.app_filters import active_match_stage

    base_match = active_match_stage(normalized_name=normalized_name)

    # ── Combined stats + breakdown pipeline ──────────────────────────────
    # Single aggregation: group by agent_id once, then $lookup once for
    # breakdown data.  Eliminates a second full collection scan.
    stats_breakdown_pipeline: list[dict[str, Any]] = [
        base_match,
        {
            "$group": {
                "_id": "$agent_id",
                "name": {"$first": "$name"},
                "publisher": {"$first": "$publisher"},
                "version": {"$first": "$version"},
                "risk_level": {"$first": "$risk_level"},
            }
        },
        # Lookup agent details for group/site breakdown
        {
            "$lookup": {
                "from": AGENTS,
                "localField": "_id",
                "foreignField": "source_id",
                "as": "_a",
                "pipeline": [
                    {
                        "$project": {
                            "group_id": 1,
                            "group_name": 1,
                            "site_id": 1,
                            "site_name": 1,
                            "_id": 0,
                        }
                    }
                ],
            }
        },
        {"$unwind": {"path": "$_a", "preserveNullAndEmptyArrays": True}},
        {
            "$facet": {
                "total": [{"$count": "n"}],
                "top_name": [
                    {"$group": {"_id": "$name", "c": {"$sum": 1}}},
                    {"$sort": {"c": -1}},
                    {"$limit": 1},
                ],
                "top_publisher": [
                    {"$group": {"_id": "$publisher", "c": {"$sum": 1}}},
                    {"$sort": {"c": -1}},
                    {"$limit": 1},
                ],
                "top_risk": [
                    {"$group": {"_id": "$risk_level", "c": {"$sum": 1}}},
                    {"$sort": {"c": -1}},
                    {"$limit": 1},
                ],
                "versions": [
                    {"$group": {"_id": {"$ifNull": ["$version", "unknown"]}, "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 50},
                ],
                "risk_dist": [
                    {
                        "$group": {
                            "_id": {"$ifNull": ["$risk_level", "unknown"]},
                            "count": {"$sum": 1},
                        }
                    },
                ],
                "by_group": [
                    {
                        "$group": {
                            "_id": "$_a.group_id",
                            "name": {"$first": "$_a.group_name"},
                            "count": {"$sum": 1},
                        }
                    },
                    {"$match": {"_id": {"$ne": None}}},
                    {"$sort": {"count": -1}},
                ],
                "by_site": [
                    {
                        "$group": {
                            "_id": "$_a.site_id",
                            "name": {"$first": "$_a.site_name"},
                            "count": {"$sum": 1},
                        }
                    },
                    {"$match": {"_id": {"$ne": None}}},
                    {"$sort": {"count": -1}},
                ],
            }
        },
    ]

    # ── Paginated + filtered agent list (runs concurrently) ──────────────
    skip = (page - 1) * page_size
    agent_pipeline: list[dict[str, Any]] = [
        base_match,
        {
            "$group": {
                "_id": "$agent_id",
                "version": {"$first": "$version"},
                "installed_at": {"$first": "$installed_at"},
                "os_type": {"$first": "$os_type"},
            }
        },
        {
            "$lookup": {
                "from": AGENTS,
                "localField": "_id",
                "foreignField": "source_id",
                "as": "_a",
                "pipeline": [
                    {
                        "$project": {
                            "_id": 0,
                            "hostname": 1,
                            "group_id": 1,
                            "group_name": 1,
                            "site_id": 1,
                            "site_name": 1,
                            "os_type": 1,
                            "last_active": 1,
                        }
                    }
                ],
            }
        },
        {"$unwind": {"path": "$_a", "preserveNullAndEmptyArrays": True}},
    ]

    # Apply server-side filters (multi-select uses $in)
    agent_filter: dict[str, Any] = {}
    if group_names:
        agent_filter["_a.group_name"] = (
            {"$in": group_names} if len(group_names) > 1 else group_names[0]
        )
    if site_names:
        agent_filter["_a.site_name"] = {"$in": site_names} if len(site_names) > 1 else site_names[0]
    if version_filters:
        agent_filter["version"] = (
            {"$in": version_filters} if len(version_filters) > 1 else version_filters[0]
        )
    if search:
        agent_filter["_a.hostname"] = {
            "$regex": re.escape(search),
            "$options": "i",
        }
    has_filters = bool(agent_filter)
    if agent_filter:
        agent_pipeline.append({"$match": agent_filter})

    agent_pipeline.append(
        {
            "$facet": {
                "count": [{"$count": "n"}],
                "rows": [
                    {"$sort": {"_a.hostname": 1}},
                    {"$skip": skip},
                    {"$limit": page_size},
                ],
            }
        }
    )

    # ── Run both pipelines concurrently ──────────────────────────────────
    stats_future = db[INSTALLED_APPS].aggregate(stats_breakdown_pipeline).to_list(1)
    agents_future = db[INSTALLED_APPS].aggregate(agent_pipeline).to_list(1)
    facet_result, agent_result = await asyncio.gather(stats_future, agents_future)

    if not facet_result or not facet_result[0].get("total"):
        raise HTTPException(status_code=404, detail="Application not found")

    f = facet_result[0]
    total_agent_count = f["total"][0]["n"] if f["total"] else 0
    display_name = (f["top_name"][0]["_id"] if f["top_name"] else None) or normalized_name
    publisher = f["top_publisher"][0]["_id"] if f["top_publisher"] else None
    risk_level = f["top_risk"][0]["_id"] if f["top_risk"] else None
    versions = [AppVersionRow(version=v["_id"], count=v["count"]) for v in f.get("versions", [])]
    risk_counts = {r["_id"]: r["count"] for r in f.get("risk_dist", [])}

    group_breakdown = [
        NameCountRow(name=g.get("name") or g["_id"], count=g["count"])
        for g in f.get("by_group", [])
    ]
    site_breakdown = [
        NameCountRow(name=s.get("name") or s["_id"], count=s["count"]) for s in f.get("by_site", [])
    ]
    true_group_count = len(group_breakdown)
    true_site_count = len(site_breakdown)

    agent_facet = agent_result[0] if agent_result else {"count": [], "rows": []}
    filtered_count = agent_facet["count"][0]["n"] if agent_facet["count"] else total_agent_count

    agents: list[AppAgentRow] = []
    for doc in agent_facet.get("rows", []):
        a = doc.get("_a") or {}
        agents.append(
            AppAgentRow(
                agent_id=doc["_id"],
                hostname=a.get("hostname") or doc["_id"],
                group_id=a.get("group_id") or "",
                group_name=a.get("group_name") or "",
                site_id=a.get("site_id") or "",
                site_name=a.get("site_name") or "",
                os_type=a.get("os_type") or doc.get("os_type") or "",
                version=doc.get("version"),
                installed_at=doc.get("installed_at"),
                last_active=a.get("last_active"),
            )
        )

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

    # ── EOL lifecycle evaluation (per-version) ──────────────────────────
    eol_detail: AppEolDetail | None = None
    summary_doc = await db["app_summaries"].find_one(
        {"normalized_name": normalized_name}, {"eol_match": 1}
    )
    if summary_doc and summary_doc.get("eol_match"):
        eol_match = summary_doc["eol_match"]
        pid = eol_match.get("eol_product_id", "")
        if pid:
            from domains.eol.matching import extract_cycle_match
            from domains.eol.repository import get_product

            # Single product lookup — not a full collection scan
            product_doc = await get_product(db, pid)
            cycles = []
            product_name = pid
            if product_doc:
                product_name = product_doc.get("name", pid)
                from datetime import date as _date

                from domains.eol.repository import _parse_date

                today = _date.today()
                for c in product_doc.get("cycles", []):
                    from domains.eol.entities import EOLCycle

                    eol_d = _parse_date(c.get("eol_date"))
                    sup_d = _parse_date(c.get("support_end"))
                    cycles.append(
                        EOLCycle(
                            cycle=str(c.get("cycle", "")),
                            eol_date=eol_d,
                            support_end=sup_d,
                            is_eol=bool(eol_d and eol_d < today),
                            is_security_only=bool(
                                sup_d and sup_d < today and (not eol_d or eol_d >= today)
                            ),
                        )
                    )

            # Evaluate each version against EOL cycles
            version_eol: list[AppVersionEolStatus] = []
            for v in versions:
                cycle = extract_cycle_match(v.version, cycles)
                if cycle:
                    version_eol.append(
                        AppVersionEolStatus(
                            version=v.version,
                            agent_count=v.count,
                            cycle=cycle.cycle,
                            is_eol=cycle.is_eol,
                            eol_date=(cycle.eol_date.isoformat() if cycle.eol_date else None),
                            is_security_only=cycle.is_security_only,
                            support_end=(
                                cycle.support_end.isoformat() if cycle.support_end else None
                            ),
                        )
                    )
                else:
                    version_eol.append(
                        AppVersionEolStatus(
                            version=v.version,
                            agent_count=v.count,
                        )
                    )

            eol_detail = AppEolDetail(
                eol_product_id=pid,
                product_name=product_name,
                match_source=eol_match.get("match_source", ""),
                match_confidence=eol_match.get("match_confidence", 0.0),
                versions=version_eol,
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
        group_breakdown=group_breakdown,
        site_breakdown=site_breakdown,
        agents=agents,
        taxonomy_match=taxonomy_match,
        eol=eol_detail,
        page=page,
        page_size=page_size,
        filtered_agent_count=filtered_count if has_filters else None,
    )
