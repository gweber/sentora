"""Admin router — backup and restore endpoints.

All endpoints require the ``admin`` role.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, status
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.admin.dto import (
    BackupListResponse,
    BackupResponse,
    BackupStartedResponse,
    RestoreRequest,
    RestoreResponse,
)
from domains.auth.entities import UserRole
from middleware.auth import require_role
from utils.backup import BackupManager
from utils.distributed_lock import DistributedLock
from utils.ws_auth import authenticate_websocket
from utils.ws_broadcast import WsBroadcaster

router = APIRouter(dependencies=[Depends(require_role(UserRole.admin))])

#: Separate router for WebSocket endpoints (no HTTP auth dependency).
#: WebSocket auth is handled by ``authenticate_websocket`` inside each handler.
ws_router = APIRouter()

#: WebSocket broadcaster for backup progress events.
backup_ws = WsBroadcaster("backup")


def _record_to_response(record) -> BackupResponse:  # noqa: ANN001
    """Convert a BackupRecord dataclass to a BackupResponse DTO."""
    return BackupResponse(**asdict(record))


async def _run_backup_with_progress(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    triggered_by: str,
) -> None:
    """Run a backup as a background task, broadcasting progress via WebSocket.

    Phases: started → dumping → finalising → completed/failed.

    Args:
        db: The Motor database handle.
        triggered_by: Who initiated the backup (e.g. "manual").
    """
    lock = DistributedLock(db, "backup_operation", ttl_seconds=600)
    acquired = await lock.acquire()
    if not acquired:
        await backup_ws.broadcast(
            {
                "type": "failed",
                "backup_id": "",
                "phase": "lock",
                "progress_percent": 0,
                "message": "Another backup or restore operation is already in progress",
            }
        )
        return

    try:
        await backup_ws.broadcast(
            {
                "type": "progress",
                "backup_id": "",
                "phase": "started",
                "progress_percent": 5,
                "message": "Backup started",
            }
        )

        # Small yield so the WS message gets sent before blocking mongodump
        await asyncio.sleep(0.05)

        await backup_ws.broadcast(
            {
                "type": "progress",
                "backup_id": "",
                "phase": "dumping",
                "progress_percent": 15,
                "message": "Running database dump...",
            }
        )

        t0 = time.monotonic()
        record = await BackupManager.create_backup(db, triggered_by=triggered_by)
        duration = time.monotonic() - t0

        if record.status == "completed":
            await backup_ws.broadcast(
                {
                    "type": "progress",
                    "backup_id": record.id,
                    "phase": "finalising",
                    "progress_percent": 85,
                    "message": "Computing checksum...",
                }
            )
            # Brief pause so the 85% state is visible
            await asyncio.sleep(0.2)

            await backup_ws.broadcast(
                {
                    "type": "completed",
                    "backup_id": record.id,
                    "phase": "completed",
                    "progress_percent": 100,
                    "message": f"Backup completed in {duration:.1f}s",
                    "record": asdict(record),
                }
            )
        else:
            await backup_ws.broadcast(
                {
                    "type": "failed",
                    "backup_id": record.id,
                    "phase": "failed",
                    "progress_percent": 0,
                    "message": record.error or "Backup failed",
                    "record": asdict(record),
                }
            )
    except Exception as exc:
        logger.error("Backup background task failed: {}", exc)
        await backup_ws.broadcast(
            {
                "type": "failed",
                "backup_id": "",
                "phase": "failed",
                "progress_percent": 0,
                "message": str(exc),
            }
        )
    finally:
        await lock.release()


@router.post("/backup", response_model=BackupStartedResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_backup(
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> BackupStartedResponse:
    """Trigger a manual backup.

    Returns immediately with 202 Accepted. Progress is streamed via
    the ``/admin/backup/progress`` WebSocket endpoint.
    """
    background_tasks.add_task(_run_backup_with_progress, db, "manual")

    return BackupStartedResponse(
        backup_id="",
        status="accepted",
        message="Backup started. Connect to /api/v1/admin/backup/progress for live updates.",
    )


@ws_router.websocket("/backup/progress")
async def backup_progress_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time backup progress.

    Clients receive JSON messages with ``type``, ``backup_id``,
    ``phase``, ``progress_percent``, and ``message`` fields.
    """
    payload = await authenticate_websocket(
        websocket,
        allowed_roles={UserRole.admin},
    )
    if payload is None:
        return

    backup_ws.connect_accepted(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        backup_ws.disconnect(websocket)


@router.get("/backups", response_model=BackupListResponse)
async def list_backups(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum records to return"),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> BackupListResponse:
    """List all backups with pagination, sorted by timestamp descending."""
    records, total = await BackupManager.list_backups(db, skip=skip, limit=limit)
    return BackupListResponse(
        backups=[_record_to_response(r) for r in records],
        total=total,
    )


@router.get("/backups/{backup_id}", response_model=BackupResponse)
async def get_backup(
    backup_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> BackupResponse:
    """Get a single backup by ID."""
    record = await BackupManager.get_backup(db, backup_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup '{backup_id}' not found",
        )
    return _record_to_response(record)


@router.post("/restore", response_model=RestoreResponse)
async def restore_backup(
    body: RestoreRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> RestoreResponse:
    """Restore the database from a backup.

    The restore operation runs as a background task. Uses a distributed
    lock to prevent concurrent backup/restore operations.
    """

    # Verify backup exists before starting
    record = await BackupManager.get_backup(db, body.backup_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup '{body.backup_id}' not found",
        )

    async def _run_restore() -> None:
        lock = DistributedLock(db, "backup_operation", ttl_seconds=600)
        acquired = await lock.acquire()
        if not acquired:
            logger.error("Restore aborted — could not acquire lock")
            return
        try:
            await BackupManager.restore_from_backup(db, body.backup_id)
        except Exception as exc:
            logger.error("Restore from {} failed: {}", body.backup_id, exc)
        finally:
            await lock.release()

    background_tasks.add_task(_run_restore)

    return RestoreResponse(
        status="accepted",
        message=f"Restore from backup '{body.backup_id}' started in background",
    )


@router.post("/backups/{backup_id}/verify")
async def verify_backup(
    backup_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, bool]:
    """Verify the integrity of a backup by checking its SHA-256 checksum."""
    try:
        valid = await BackupManager.verify_backup(db, backup_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {"valid": valid}


@router.delete("/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backup(
    backup_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> None:
    """Delete a backup (files and record)."""
    deleted = await BackupManager.delete_backup(db, backup_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup '{backup_id}' not found",
        )
