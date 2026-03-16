"""Agents domain router — read-only queries over synced S1 agent data."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from middleware.auth import get_current_user


def _json_response(data: object, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(data),
        status_code=status_code,
    )


router = APIRouter()


@router.get("/", dependencies=[Depends(get_current_user)])
async def list_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(500, ge=1, le=500),
    site_id: str | None = Query(None),
    group_id: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),
) -> JSONResponse:
    """List agents with pagination and optional filters."""
    query: dict = {}
    if site_id:
        query["site_id"] = site_id
    if group_id:
        query["group_id"] = group_id
    if search:
        query["hostname"] = {"$regex": re.escape(search), "$options": "i"}

    skip = (page - 1) * limit

    total = await db["s1_agents"].count_documents(query)

    cursor = db["s1_agents"].find(query, {"_id": 0}).sort("hostname", 1).skip(skip).limit(limit)
    agents = [doc async for doc in cursor]

    return _json_response({"agents": agents, "total": total, "page": page, "limit": limit})


@router.get("/{agent_id}", dependencies=[Depends(get_current_user)])
async def get_agent(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),
) -> JSONResponse:
    """Get full agent detail including installed apps and classification."""
    agent = await db["s1_agents"].find_one({"s1_agent_id": agent_id}, {"_id": 0})
    if not agent:
        return JSONResponse({"detail": "Agent not found"}, status_code=404)

    from domains.sync.app_filters import active_filter

    apps_cursor = (
        db["s1_installed_apps"].find(active_filter(agent_id=agent_id), {"_id": 0}).limit(500)
    )
    installed_apps = [doc async for doc in apps_cursor]

    classification = await db["classification_results"].find_one({"agent_id": agent_id}, {"_id": 0})

    agent["installed_apps"] = installed_apps
    agent["classification"] = classification

    return _json_response(agent)


@router.get("/{agent_id}/apps", dependencies=[Depends(get_current_user)])
async def get_agent_apps(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),
) -> JSONResponse:
    """Get installed applications for a specific agent."""
    agent = await db["s1_agents"].find_one({"s1_agent_id": agent_id}, {"_id": 0})
    if agent is None:
        return JSONResponse({"detail": "Agent not found"}, status_code=404)
    from domains.sync.app_filters import active_filter

    cursor = (
        db["s1_installed_apps"]
        .find(
            active_filter(agent_id=agent_id),
            {
                "_id": 0,
                "name": 1,
                "normalized_name": 1,
                "version": 1,
                "publisher": 1,
                "size": 1,
                "installed_at": 1,
                "synced_at": 1,
            },
        )
        .limit(1000)
    )
    apps = [doc async for doc in cursor]
    return _json_response(apps)
