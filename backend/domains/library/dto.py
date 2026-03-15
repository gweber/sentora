"""Library domain DTOs — request and response models for the API boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Library entry DTOs ───────────────────────────────────────────────────


class LibraryMarkerResponse(BaseModel):
    id: str
    pattern: str
    display_name: str
    category: str
    weight: float
    source_detail: str
    added_at: str
    added_by: str


class LibraryEntryResponse(BaseModel):
    id: str
    name: str
    vendor: str
    category: str
    description: str
    tags: list[str]
    markers: list[LibraryMarkerResponse]
    source: str
    upstream_id: str | None
    upstream_version: str | None
    version: int
    status: str
    subscriber_count: int
    submitted_by: str
    reviewed_by: str | None
    created_at: str
    updated_at: str


class LibraryEntryListResponse(BaseModel):
    entries: list[LibraryEntryResponse]
    total: int


class MarkerInput(BaseModel):
    pattern: str
    display_name: str = ""
    category: str = "name_pattern"
    weight: float = 1.0
    source_detail: str = ""


class LibraryEntryCreateRequest(BaseModel):
    name: str
    vendor: str = ""
    category: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    markers: list[MarkerInput] | None = None


class LibraryEntryUpdateRequest(BaseModel):
    name: str | None = None
    vendor: str | None = None
    category: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: Literal["draft", "pending_review", "published", "deprecated"] | None = None


# ── Subscription DTOs ────────────────────────────────────────────────────


class SubscriptionResponse(BaseModel):
    id: str
    group_id: str
    library_entry_id: str
    entry_name: str = ""
    synced_version: int
    auto_update: bool
    subscribed_at: str
    subscribed_by: str
    last_synced_at: str | None


class SubscribeRequest(BaseModel):
    group_id: str
    auto_update: bool = True


class SubscriptionListResponse(BaseModel):
    subscriptions: list[SubscriptionResponse]
    total: int


# ── Ingestion DTOs ───────────────────────────────────────────────────────


class IngestionRunResponse(BaseModel):
    id: str
    source: str
    status: str
    started_at: str
    completed_at: str | None
    entries_created: int
    entries_updated: int
    entries_skipped: int
    errors: list[str]


class IngestionRunListResponse(BaseModel):
    runs: list[IngestionRunResponse]
    total: int


class SourceInfo(BaseModel):
    name: str
    description: str
    status: str = "idle"
    last_run: IngestionRunResponse | None = None


class SourceListResponse(BaseModel):
    sources: list[SourceInfo]


# ── Per-source progress (WebSocket) ─────────────────────────────────────


class SourceProgress(BaseModel):
    """Per-source status snapshot included in WebSocket broadcasts."""

    status: str = "idle"  # idle | running | completed | failed | cancelled
    synced: int = 0
    total: int = 0
    message: str | None = None


class IngestionProgressMessage(BaseModel):
    """Real-time ingestion progress sent over WebSocket.

    Attributes:
        type: Message kind — ``progress``, ``completed``, ``failed``,
            ``source_completed``, ``source_failed``, ``source_cancelled``.
        run_id: Identifier of the current ingestion run (per source).
        source: Adapter key that triggered this message (e.g. ``nist_cpe``).
        status: Overall ingestion status.
        message: Human-readable status line.
        entries_created: Entries created so far (for the triggering source).
        entries_updated: Entries updated so far.
        entries_skipped: Entries skipped so far.
        total_processed: Total entries processed.
        error_count: Number of errors encountered.
        source_details: Per-source breakdown of status and progress.
    """

    type: str  # "progress" | "completed" | "failed" | "source_completed" | ...
    run_id: str
    source: str
    status: str
    message: str | None = None
    entries_created: int = 0
    entries_updated: int = 0
    entries_skipped: int = 0
    total_processed: int = 0
    error_count: int = 0
    source_details: dict[str, SourceProgress] | None = None


# ── Ingestion command DTOs ────────────────────────────────────────────────


class TriggerAllRequest(BaseModel):
    """Request body for triggering multiple sources in parallel."""

    sources: list[str] | None = None


# ── Stats DTOs ───────────────────────────────────────────────────────────


class LibraryStatsResponse(BaseModel):
    total_entries: int
    by_source: dict[str, int]
    by_status: dict[str, int]
    total_subscriptions: int
