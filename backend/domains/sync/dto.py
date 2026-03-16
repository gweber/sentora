"""Sync domain DTOs."""

from __future__ import annotations

from pydantic import BaseModel


class SyncCounts(BaseModel):
    sites_synced: int = 0
    sites_total: int = 0
    groups_synced: int = 0
    groups_total: int = 0
    agents_synced: int = 0
    agents_total: int = 0
    apps_synced: int = 0
    apps_total: int = 0
    tags_synced: int = 0
    tags_total: int = 0
    errors: int = 0


class SyncRunResponse(BaseModel):
    id: str
    started_at: str
    completed_at: str | None = None
    status: str  # running | completed | failed
    trigger: str  # manual | scheduled | phase
    mode: str = "auto"  # full | incremental | auto
    counts: SyncCounts = SyncCounts()
    phase: str | None = None  # sites | groups | agents | apps | done
    message: str | None = None


class PhaseProgress(BaseModel):
    """Per-phase progress snapshot."""

    status: str = "idle"  # idle | running | completed | failed | cancelled
    synced: int = 0
    total: int = 0
    message: str | None = None


class SyncProgressMessage(BaseModel):
    type: str  # progress | completed | failed | ping
    run_id: str
    status: str
    phase: str | None = None
    counts: SyncCounts
    message: str | None = None
    phase_details: dict[str, PhaseProgress] = {}  # per-phase status
