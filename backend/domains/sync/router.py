"""Sync domain router."""

from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from database import get_tenant_db
from domains.auth.entities import UserRole
from middleware.auth import get_current_user, require_role

from .manager import sync_manager

router = APIRouter()


class SyncTriggerBody(BaseModel):
    mode: str = "auto"  # "full" | "incremental" | "auto"
    phases: list[str] | None = None  # None = all phases


@router.websocket("/progress")
async def sync_progress_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint — streams SyncProgressMessage JSON to all clients.

    Incoming messages are discarded; a simple rate limit prevents a single
    client from flooding the receive loop.
    """
    from utils.ws_auth import authenticate_websocket

    payload = await authenticate_websocket(websocket)
    if payload is None:
        return

    import time

    await sync_manager.connect_accepted(websocket)
    try:
        last_msg_time = 0.0
        while True:
            await websocket.receive_text()
            now = time.monotonic()
            if now - last_msg_time < 0.1:  # max 10 msg/s per client
                continue
            last_msg_time = now
    except WebSocketDisconnect:
        sync_manager.disconnect(websocket)


@router.post("/trigger", dependencies=[Depends(require_role(UserRole.admin))])
async def trigger_sync(
    body: SyncTriggerBody = SyncTriggerBody(),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Trigger all (or selected) phases independently. Returns which phases started."""
    result = await sync_manager.trigger_all(mode=body.mode, phases=body.phases)
    if not result["phases_started"]:
        return JSONResponse({"detail": "All requested phases are already running"}, status_code=409)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action="sync.triggered",
        actor="user",
        summary=f"Sync triggered (mode={result['mode']}, phases={result['phases_started']})",
        details=result,
    )
    return JSONResponse(result)


@router.post("/refresh", dependencies=[Depends(require_role(UserRole.admin))])
async def refresh_sync(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Trigger an incremental refresh of all phases."""
    result = await sync_manager.trigger_all(mode="incremental")
    if not result["phases_started"]:
        return JSONResponse({"detail": "All phases are already running"}, status_code=409)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action="sync.triggered",
        actor="user",
        summary=f"Refresh triggered (phases={result['phases_started']})",
        details=result,
    )
    return JSONResponse(result)


@router.post("/resume", dependencies=[Depends(require_role(UserRole.admin))])
async def resume_sync(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Resume any phases that have checkpoints. Returns 404 if nothing to resume."""
    result = await sync_manager.resume_all()
    if not result["phases_resumed"]:
        return JSONResponse({"detail": "No resumable checkpoints found"}, status_code=404)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action="sync.resumed",
        actor="user",
        summary=f"Resumed phases: {result['phases_resumed']}",
        details=result,
    )
    return JSONResponse(result)


@router.post("/cancel", dependencies=[Depends(require_role(UserRole.admin))])
async def cancel_sync(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Cancel all running phases. Returns 404 if nothing is running."""
    cancelled = await sync_manager.cancel()
    if not cancelled:
        return JSONResponse({"detail": "No phases are currently running"}, status_code=404)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action="sync.cancelled",
        actor="user",
        summary="Sync cancellation requested",
    )
    return JSONResponse({"status": "cancelling"})


class PhaseTriggerBody(BaseModel):
    mode: str = "auto"  # "full" | "incremental" | "auto"


@router.post("/phase/{phase}/trigger", dependencies=[Depends(require_role(UserRole.admin))])
async def trigger_phase(
    phase: str,
    body: PhaseTriggerBody = PhaseTriggerBody(),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Trigger a single phase independently. Returns 409 if that phase is already running."""
    if phase not in sync_manager.ALL_PHASES:
        return JSONResponse({"detail": f"Unknown phase: {phase}"}, status_code=400)
    result = await sync_manager.trigger_phase(phase, mode=body.mode)
    if result is None:
        return JSONResponse({"detail": f"Phase {phase} is already running"}, status_code=409)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action=f"sync.phase.{phase}.triggered",
        actor="user",
        summary=f"Phase {phase} triggered independently (mode={body.mode})",
    )
    return JSONResponse(result)


@router.post("/phase/{phase}/resume", dependencies=[Depends(require_role(UserRole.admin))])
async def resume_phase(
    phase: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Resume a single phase from its checkpoint."""
    if phase not in sync_manager.ALL_PHASES:
        return JSONResponse({"detail": f"Unknown phase: {phase}"}, status_code=400)
    result = await sync_manager.resume_phase(phase)
    if result is None:
        runner = sync_manager.get_runner(phase)
        if runner and runner.is_running:
            return JSONResponse({"detail": f"Phase {phase} is already running"}, status_code=409)
        return JSONResponse({"detail": f"No checkpoint for phase {phase}"}, status_code=404)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action=f"sync.phase.{phase}.resumed",
        actor="user",
        summary=f"Phase {phase} resumed from checkpoint",
    )
    return JSONResponse(result)


@router.post("/phase/{phase}/cancel", dependencies=[Depends(require_role(UserRole.admin))])
async def cancel_phase(
    phase: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Cancel a single running phase."""
    if phase not in sync_manager.ALL_PHASES:
        return JSONResponse({"detail": f"Unknown phase: {phase}"}, status_code=400)
    cancelled = await sync_manager.cancel_phase(phase)
    if not cancelled:
        return JSONResponse({"detail": f"Phase {phase} is not running"}, status_code=404)
    from audit.log import audit

    await audit(
        db,
        domain="sync",
        action=f"sync.phase.{phase}.cancelled",
        actor="user",
        summary=f"Phase {phase} cancellation requested",
    )
    return JSONResponse({"status": "cancelling"})


@router.get("/phases", dependencies=[Depends(get_current_user)])
async def get_phase_status() -> JSONResponse:
    """Return the current status of all phase runners."""
    return JSONResponse(sync_manager.phase_status())


@router.get("/checkpoint", dependencies=[Depends(get_current_user)])
async def get_checkpoint(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Return the current sync checkpoint, if any.

    The checkpoint reflects progress of the most recent (possibly failed) sync run.
    It is cleared on successful completion and created fresh on each new trigger.
    """
    checkpoint = await db["s1_sync_checkpoint"].find_one({"_id": "current"}, {"_id": 0})
    # Also return per-phase checkpoints
    phase_checkpoints: dict = {}
    async for doc in db["s1_sync_checkpoint"].find(
        {"_id": {"$regex": "^phase:"}},
    ):
        phase_name = doc["_id"].replace("phase:", "")
        doc.pop("_id", None)
        phase_checkpoints[phase_name] = doc
    return JSONResponse({"checkpoint": checkpoint, "phases": phase_checkpoints})


@router.get("/status", dependencies=[Depends(get_current_user)])
async def get_sync_status(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    import asyncio
    from datetime import datetime

    from .dto import SyncRunResponse

    current = sync_manager.current_run
    last = sync_manager.last_completed_run
    if last is None and current is None:
        doc = await db["s1_sync_runs"].find_one(
            {"status": {"$in": ["completed", "failed"]}},
            {"_id": 0},
            sort=[("completed_at", -1)],
        )
        if doc:
            last = SyncRunResponse(**doc)
    from .app_filters import active_filter

    agents, groups, sites, apps, tags = await asyncio.gather(
        db["s1_agents"].count_documents({}),
        db["s1_groups"].count_documents({}),
        db["s1_sites"].count_documents({}),
        db["s1_installed_apps"].count_documents(active_filter()),
        db["s1_tags"].count_documents({}),
    )

    # Build per-phase schedule info
    schedule: dict[str, dict] = {}
    try:
        from domains.config import repository as config_repo
        from utils.dt import utc_now

        cfg = await config_repo.get(db)
        meta = await db["s1_sync_meta"].find_one({"_id": "global"}) or {}
        utc_now()

        timestamp_keys = {
            "sites": "sites_synced_at",
            "groups": "groups_synced_at",
            "agents": "agents_synced_at",
            "apps": "apps_synced_at",
            "tags": "tags_synced_at",
        }
        for phase in sync_manager.ALL_PHASES:
            per_phase = getattr(cfg, f"schedule_{phase}_minutes", 0)
            interval = per_phase if per_phase > 0 else cfg.refresh_interval_minutes
            last_synced = meta.get(timestamp_keys[phase])
            next_run_at = None
            if interval > 0 and last_synced:
                try:
                    last_dt = datetime.fromisoformat(last_synced)
                    from datetime import timedelta

                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=UTC)
                    next_dt = last_dt + timedelta(minutes=interval)
                    next_run_at = next_dt.isoformat()
                except (ValueError, TypeError):
                    pass
            schedule[phase] = {
                "interval_minutes": interval,
                "last_synced_at": last_synced,
                "next_run_at": next_run_at,
            }
    except Exception:
        pass

    return JSONResponse(
        {
            "current_run": current.model_dump() if current else None,
            "last_completed_run": last.model_dump() if last else None,
            "db_counts": {
                "agents": agents,
                "groups": groups,
                "sites": sites,
                "apps": apps,
                "tags": tags,
            },
            "phases": sync_manager.phase_status(),
            "schedule": schedule,
        }
    )


@router.post("/backfill-app-names", dependencies=[Depends(require_role(UserRole.admin))])
async def backfill_app_names(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Backfill ``installed_app_names`` onto all ``s1_agents`` documents.

    Runs an aggregation over ``s1_installed_apps``, groups by ``agent_id``,
    and bulk-writes the resulting compact string array onto each agent document.
    Executes as a background task; returns immediately with a count of agents
    queued for update.
    """
    import asyncio

    from pymongo import UpdateOne

    async def _run() -> None:
        try:
            from .app_filters import active_match_stage

            pipeline = [
                active_match_stage(),
                {"$group": {"_id": "$agent_id", "names": {"$addToSet": "$normalized_name"}}},
            ]
            ops: list = []
            updated = 0
            async for grp in db["s1_installed_apps"].aggregate(pipeline):
                if not grp.get("_id"):
                    continue
                ops.append(
                    UpdateOne(
                        {"s1_agent_id": grp["_id"]},
                        {"$set": {"installed_app_names": [n for n in grp["names"] if n]}},
                    )
                )
                if len(ops) >= 1000:
                    result = await db["s1_agents"].bulk_write(ops, ordered=False)
                    updated += result.modified_count
                    ops.clear()
            if ops:
                result = await db["s1_agents"].bulk_write(ops, ordered=False)
                updated += result.modified_count
            from loguru import logger

            logger.info("Backfill complete: installed_app_names written to {} agents", updated)
            from audit.log import audit

            await audit(
                db,
                domain="sync",
                action="sync.backfill_completed",
                actor="system",
                summary="App name backfill completed",
                details={"updated": updated},
            )
        except Exception as exc:
            from loguru import logger

            logger.error("Backfill failed: {}", exc)
            from audit.log import audit

            await audit(
                db,
                domain="sync",
                action="sync.backfill_failed",
                actor="system",
                status="failure",
                summary=f"App name backfill failed: {exc}",
            )
            raise

    asyncio.create_task(_run())
    return JSONResponse({"status": "started"})


@router.post("/renormalize-apps", dependencies=[Depends(require_role(UserRole.admin))])
async def renormalize_apps(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Re-apply the current ``normalize_app_name`` logic to every app in
    ``s1_installed_apps``, then rebuild ``installed_app_names`` on all agents.

    Use this after upgrading the normalizer (e.g. to strip version suffixes)
    so that existing data matches the new logic without a full re-sync.
    Runs as a background task; returns immediately.
    """
    import asyncio

    from pymongo import UpdateOne

    from .normalizer import normalize_app_name

    async def _run() -> None:
        from loguru import logger

        try:
            # Step 1 — re-normalize all s1_installed_apps.normalized_name
            ops: list = []
            updated_apps = 0
            async for doc in db["s1_installed_apps"].find({}, {"_id": 1, "name": 1, "version": 1}):
                new_name = normalize_app_name(
                    doc.get("name") or "", version=doc.get("version") or ""
                )
                if not new_name:
                    continue
                ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"normalized_name": new_name}}))
                if len(ops) >= 1000:
                    result = await db["s1_installed_apps"].bulk_write(ops, ordered=False)
                    updated_apps += result.modified_count
                    ops.clear()
            if ops:
                result = await db["s1_installed_apps"].bulk_write(ops, ordered=False)
                updated_apps += result.modified_count
            logger.info("Renormalize — updated normalized_name on {} app records", updated_apps)

            # Step 2 — rebuild installed_app_names on agents (active apps only)
            from .app_filters import active_match_stage

            pipeline = [
                active_match_stage(),
                {"$group": {"_id": "$agent_id", "names": {"$addToSet": "$normalized_name"}}},
            ]
            agent_ops: list = []
            updated_agents = 0
            async for grp in db["s1_installed_apps"].aggregate(pipeline):
                if not grp.get("_id"):
                    continue
                agent_ops.append(
                    UpdateOne(
                        {"s1_agent_id": grp["_id"]},
                        {"$set": {"installed_app_names": [n for n in grp["names"] if n]}},
                    )
                )
                if len(agent_ops) >= 1000:
                    result = await db["s1_agents"].bulk_write(agent_ops, ordered=False)
                    updated_agents += result.modified_count
                    agent_ops.clear()
            if agent_ops:
                result = await db["s1_agents"].bulk_write(agent_ops, ordered=False)
                updated_agents += result.modified_count
            logger.info("Renormalize — rebuilt installed_app_names on {} agents", updated_agents)
            from audit.log import audit

            await audit(
                db,
                domain="sync",
                action="sync.renormalize_completed",
                actor="system",
                summary="App renormalization completed",
                details={"updated_apps": updated_apps, "updated_agents": updated_agents},
            )
        except Exception as exc:
            from loguru import logger as _log

            _log.error("Renormalize failed: {}", exc)
            from audit.log import audit

            await audit(
                db,
                domain="sync",
                action="sync.renormalize_failed",
                actor="system",
                status="failure",
                summary=f"App renormalization failed: {exc}",
            )
            raise

    asyncio.create_task(_run())
    return JSONResponse({"status": "started"})


@router.get("/tags", dependencies=[Depends(get_current_user)])
async def list_synced_tags(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Return S1 tags from the last sync, sorted by name (capped at 5000)."""
    cursor = db["s1_tags"].find({}, {"_id": 0}).sort("name", 1).limit(5000)
    docs = [doc async for doc in cursor]
    return JSONResponse({"tags": docs, "total": len(docs)})


@router.get("/history", dependencies=[Depends(get_current_user)])
async def get_sync_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Return sync run history from MongoDB, sorted newest-first."""
    total = await db["s1_sync_runs"].count_documents({})
    cursor = (
        db["s1_sync_runs"]
        .find({}, {"_id": 0})
        .sort("started_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    docs = [doc async for doc in cursor]
    return JSONResponse({"runs": docs, "total": total, "page": page, "limit": limit})
