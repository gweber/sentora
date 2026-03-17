"""Groups router — lists groups from the synced groups collection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.sources.collections import GROUPS
from middleware.auth import get_current_user

router = APIRouter()


@router.get("/", dependencies=[Depends(get_current_user)])
async def list_groups(
    site_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),
) -> JSONResponse:
    """List groups with pagination and fingerprint presence flag.

    Args:
        site_id: Optional site ID to filter groups by.
        page: Page number (1-indexed).
        limit: Maximum number of groups per page (default 200, max 1000).
        db: Motor database (injected).
    """
    match: dict = {}
    if site_id:
        match["site_id"] = site_id

    total = await db[GROUPS].count_documents(match)
    if total == 0:
        return JSONResponse({"groups": [], "total": 0, "page": page, "limit": limit})

    skip = (page - 1) * limit
    cursor = db[GROUPS].find(match, {"_id": 0}).sort("name", 1).skip(skip).limit(limit)
    raw_groups = [doc async for doc in cursor]

    group_ids = [g["source_id"] for g in raw_groups if g.get("source_id")]
    fingerprints_cursor = db["fingerprints"].find(
        {"group_id": {"$in": group_ids}},
        {"_id": 0, "group_id": 1},
    )
    fingerprinted_ids = {doc["group_id"] async for doc in fingerprints_cursor}

    groups = [
        {
            "group_id": g["source_id"],
            "group_name": g.get("name"),
            "description": g.get("description"),
            "type": g.get("type", ""),
            "is_default": g.get("is_default", False),
            "filter_name": g.get("filter_name"),
            "site_id": g.get("site_id", ""),
            "site_name": g.get("site_name", ""),
            "agent_count": g.get("agent_count", 0),
            "os_types": g.get("os_types", []),
            "created_at": g.get("created_at"),
            "updated_at": g.get("updated_at"),
            "has_fingerprint": g["source_id"] in fingerprinted_ids,
        }
        for g in raw_groups
    ]

    return JSONResponse({"groups": groups, "total": total, "page": page, "limit": limit})
