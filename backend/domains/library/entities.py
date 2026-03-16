"""Library domain entities.

Pydantic models for the fingerprint library: reusable fingerprint templates,
subscriptions that link library entries to S1 groups, and ingestion run tracking.

MongoDB collections:
- ``library_entries``: shared fingerprint templates
- ``library_subscriptions``: group-to-entry subscriptions
- ``library_ingestion_runs``: source ingestion history
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from utils.dt import utc_now

SourceType = Literal[
    "manual",
    "nist_cpe",
    "mitre",
    "chocolatey",
    "winget",
    "homebrew",
    "homebrew_cask",
    "community",
]

EntryStatus = Literal["draft", "pending_review", "published", "deprecated"]


class LibraryMarker(BaseModel):
    """A single pattern-based marker within a library entry."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    pattern: str
    display_name: str
    category: str = "name_pattern"
    weight: float = 1.0
    source_detail: str = ""
    added_at: datetime = Field(default_factory=utc_now)
    added_by: str = "system"


class LibraryEntry(BaseModel):
    """A reusable fingerprint template in the shared library.

    Attributes:
        id: MongoDB document identifier.
        name: Human-readable name (e.g. "Google Chrome").
        vendor: Software vendor/publisher.
        category: Taxonomy category key.
        description: Free-text description.
        tags: Free-form tags for filtering.
        markers: Glob-pattern markers.
        source: How this entry was created.
        upstream_id: External identifier (CPE URI, MITRE ID, etc.).
        upstream_version: Version of the upstream data that created this.
        version: Internal version bumped on each update (for subscription sync).
        status: Workflow state.
        subscriber_count: Denormalized count of subscribing groups.
        submitted_by: Creator identifier.
        reviewed_by: Reviewer identifier (for community entries).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    name: str
    vendor: str = ""
    category: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    markers: list[LibraryMarker] = Field(default_factory=list)

    source: SourceType = "manual"
    upstream_id: str | None = None
    upstream_version: str | None = None

    version: int = 1
    status: EntryStatus = "published"
    subscriber_count: int = 0
    submitted_by: str = "system"
    reviewed_by: str | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LibrarySubscription(BaseModel):
    """Links a library entry to an S1 group's fingerprint.

    When subscribed, the library entry's markers are copied into the group's
    fingerprint with ``source="library"``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    group_id: str
    library_entry_id: str
    synced_version: int = 0
    auto_update: bool = True
    subscribed_at: datetime = Field(default_factory=utc_now)
    subscribed_by: str = "system"
    last_synced_at: datetime | None = None


class IngestionRun(BaseModel):
    """Tracks a source ingestion run."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    source: str
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    entries_created: int = 0
    entries_updated: int = 0
    entries_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
