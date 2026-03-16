"""Sites router — read-only view of synced S1 site data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from middleware.auth import get_current_user

router = APIRouter()


@router.get("/", dependencies=[Depends(get_current_user)])
async def list_sites(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),
) -> JSONResponse:
    """List synced SentinelOne sites with pagination and group/agent counts.

    Args:
        page: Page number (1-indexed).
        limit: Maximum number of sites per page (default 100, max 500).
        db: Motor database (injected).
    """
    total = await db["s1_sites"].count_documents({})
    if total == 0:
        return JSONResponse({"sites": [], "total": 0, "page": page, "limit": limit})

    skip = (page - 1) * limit
    sites_cursor = db["s1_sites"].find({}, {"_id": 0}).sort("name", 1).skip(skip).limit(limit)
    sites = [doc async for doc in sites_cursor]

    site_ids = [s["s1_site_id"] for s in sites]

    # Count groups per site (only for current page)
    group_pipeline: list[dict[str, Any]] = [
        {"$match": {"site_id": {"$in": site_ids}}},
        {"$group": {"_id": "$site_id", "group_count": {"$sum": 1}}},
    ]
    group_counts = {
        doc["_id"]: doc["group_count"] async for doc in db["s1_groups"].aggregate(group_pipeline)
    }

    # Count agents per site (only for current page)
    agent_pipeline: list[dict[str, Any]] = [
        {"$match": {"site_id": {"$in": site_ids}}},
        {"$group": {"_id": "$site_id", "agent_count": {"$sum": 1}}},
    ]
    agent_counts = {
        doc["_id"]: doc["agent_count"] async for doc in db["s1_agents"].aggregate(agent_pipeline)
    }

    for site in sites:
        sid = site["s1_site_id"]
        site["group_count"] = group_counts.get(sid, 0)
        site["agent_count"] = agent_counts.get(sid, 0)

    return JSONResponse({"sites": sites, "total": total, "page": page, "limit": limit})
