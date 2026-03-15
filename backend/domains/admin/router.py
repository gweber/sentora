"""Admin router — backup and restore endpoints.

All endpoints require the ``admin`` role.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.admin.dto import (
    BackupListResponse,
    BackupResponse,
    RestoreRequest,
    RestoreResponse,
)
from domains.auth.entities import UserRole
from middleware.auth import require_role
from utils.backup import BackupManager
from utils.distributed_lock import DistributedLock

router = APIRouter(dependencies=[Depends(require_role(UserRole.admin))])


def _record_to_response(record) -> BackupResponse:  # noqa: ANN001
    """Convert a BackupRecord dataclass to a BackupResponse DTO."""
    return BackupResponse(**asdict(record))


@router.post("/backup", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def trigger_backup(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> BackupResponse:
    """Trigger a manual backup.

    Uses a distributed lock to prevent concurrent backup operations.
    """
    lock = DistributedLock(db, "backup_operation", ttl_seconds=600)

    acquired = await lock.acquire()
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another backup or restore operation is already in progress",
        )

    try:
        record = await BackupManager.create_backup(db, triggered_by="manual")
        return _record_to_response(record)
    finally:
        await lock.release()


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
