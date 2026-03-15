"""Audit log router.

GET /api/v1/audit/ — paginated, filterable view of the audit_log collection.
Entries are returned newest-first.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.ws import audit_ws
from database import get_tenant_db
from domains.auth.entities import UserRole
from middleware.auth import require_role

router = APIRouter()


def _serialise_entry(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert non-JSON-serialisable values in an audit entry to strings.

    MongoDB returns ``datetime`` objects for BSON dates.  ``JSONResponse``
    uses ``json.dumps`` without a custom default, so we must convert them
    before responding.
    """
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


@router.get("/", dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))])
async def list_audit_log(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    domain: str | None = Query(None, description="Filter by domain (sync, config, fingerprint, …)"),
    actor: str | None = Query(None, description="Filter by actor (user, system, scheduler)"),
    action: str | None = Query(None, description="Filter by action substring"),
    status: str | None = Query(None, description="Filter by status (success, failure, info)"),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Return paginated audit log entries, newest first.

    All filter parameters are optional and can be combined.
    """
    query: dict = {}
    if domain:
        query["domain"] = domain
    if actor:
        query["actor"] = actor
    if action:
        query["action"] = {"$regex": re.escape(action), "$options": "i"}
    if status:
        query["status"] = status

    skip = (page - 1) * limit
    total = await db["audit_log"].count_documents(query)
    cursor = (
        db["audit_log"]
        .find(query, {"_id": 0})
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )
    entries = [_serialise_entry(doc) async for doc in cursor]

    return JSONResponse({"entries": entries, "total": total, "page": page, "limit": limit})


@router.websocket("/ws")
async def audit_live(websocket: WebSocket) -> None:
    """WebSocket endpoint — pushes new audit entries to all connected clients.

    Authentication is performed via the ``Sec-WebSocket-Protocol`` header
    (subprotocol ``bearer.<token>``) to prevent token leakage in logs.
    """
    from utils.ws_auth import authenticate_websocket

    payload = await authenticate_websocket(
        websocket,
        allowed_roles={UserRole.analyst, UserRole.admin, UserRole.super_admin},
    )
    if payload is None:
        return
    audit_ws.connect_accepted(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive; client pings
    except WebSocketDisconnect:
        audit_ws.disconnect(websocket)
