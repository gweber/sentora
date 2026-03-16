"""Admin domain DTOs — backup and restore response models."""

from __future__ import annotations

from pydantic import BaseModel


class BackupResponse(BaseModel):
    """Single backup record response."""

    id: str
    timestamp: str
    size_bytes: int = 0
    checksum_sha256: str = ""
    storage_type: str = "local"
    storage_path: str = ""
    status: str = "in_progress"
    triggered_by: str = "manual"
    duration_seconds: float = 0.0
    error: str | None = None


class BackupListResponse(BaseModel):
    """Paginated list of backup records."""

    backups: list[BackupResponse]
    total: int


class RestoreRequest(BaseModel):
    """Request body for restore endpoint."""

    backup_id: str


class RestoreResponse(BaseModel):
    """Response for restore endpoint."""

    status: str
    message: str
