"""Fingerprint domain DTOs (Data Transfer Objects).

DTOs define the API contract. Request DTOs use ``ConfigDict(strict=True)`` to
reject extra fields and enforce type coercion. Response DTOs mirror the
TypeScript interface shapes expected by the frontend.

No domain entities are exposed directly from the router — the service layer
converts entities ↔ DTOs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Request DTOs ──────────────────────────────────────────────────────────────


class MarkerCreateRequest(BaseModel):
    """Payload for adding a new marker to a fingerprint.

    Attributes:
        pattern: Glob pattern matched against ``normalized_name`` in installed
            apps. Supports ``*`` (any sequence) and ``?`` (single character).
        display_name: Human-readable label for the marker.
        category: Marker category key (defaults to ``"name_pattern"``).
        weight: Contribution weight for scoring (0.1–2.0, default 1.0).
        source: How this marker was created (defaults to ``"manual"``).
    """

    model_config = ConfigDict(strict=True)

    pattern: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=200)
    category: str = "name_pattern"
    weight: float = Field(default=1.0, ge=0.1, le=2.0)
    source: Literal["manual", "statistical", "seed", "library"] = "manual"


class MarkerUpdateRequest(BaseModel):
    """Payload for partially updating an existing marker.

    All fields are optional — only provided (non-None) fields are applied.

    Attributes:
        weight: New contribution weight (0.1–2.0).
        pattern: New glob pattern.
        display_name: New human-readable label.
    """

    model_config = ConfigDict(strict=True)

    weight: float | None = Field(default=None, ge=0.1, le=2.0)
    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)


class MarkerReorderRequest(BaseModel):
    """Payload for reordering markers within a fingerprint.

    Attributes:
        marker_ids: Complete ordered list of marker IDs. Every existing marker
            ID must be present; the fingerprint's markers array is replaced with
            this ordering.
    """

    model_config = ConfigDict(strict=True)

    marker_ids: list[str] = Field(min_length=1)


# ── Response DTOs ─────────────────────────────────────────────────────────────


class FingerprintMarkerResponse(BaseModel):
    """Response shape for a single fingerprint marker.

    Mirrors the ``FingerprintMarker`` TypeScript interface.

    Attributes:
        id: Unique marker identifier.
        pattern: Glob pattern.
        display_name: Human-readable label.
        category: Marker category key.
        weight: Contribution weight (0.1–2.0).
        source: How the marker was created.
        confidence: Statistical confidence (0.0–1.0).
        added_at: ISO-8601 timestamp when the marker was added.
        added_by: User or system that added the marker.
    """

    id: str
    pattern: str
    display_name: str
    category: str
    weight: float
    source: Literal["manual", "statistical", "seed", "library"]
    confidence: float
    added_at: str
    added_by: str


class FingerprintResponse(BaseModel):
    """Response shape for a fingerprint document.

    Mirrors the ``Fingerprint`` TypeScript interface.

    Attributes:
        id: MongoDB document identifier.
        group_id: SentinelOne group ID.
        group_name: Human-readable group name.
        markers: Ordered list of marker responses.
        created_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 last-updated timestamp.
        created_by: User or system that created the fingerprint.
    """

    id: str
    group_id: str
    group_name: str
    site_name: str
    account_name: str
    markers: list[FingerprintMarkerResponse]
    created_at: str
    updated_at: str
    created_by: str


class ProposedMarkerResponse(BaseModel):
    """Response shape for a single auto-proposed marker."""

    normalized_name: str
    display_name: str
    lift: float
    group_coverage: float
    outside_coverage: float
    agent_count_in_group: int
    agent_count_outside: int
    shared_with_groups: list[str]


class AutoFingerprintProposalResponse(BaseModel):
    """Response shape for an auto-fingerprint proposal."""

    id: str
    group_id: str
    group_name: str
    group_size: int
    proposed_markers: list[ProposedMarkerResponse]
    quality_score: float
    total_groups: int
    coverage_min: float
    outside_max: float
    lift_min: float
    top_k: int
    status: Literal["pending", "applied", "dismissed"]
    computed_at: str


class ApplyProposalResponse(BaseModel):
    """Response shape for a proposal apply operation."""

    added: int
    skipped: int
    status: Literal["applied"]


class FingerprintExportMarker(BaseModel):
    """A single marker in the export format.

    Attributes:
        pattern: Glob pattern.
        display_name: Human-readable label.
        category: Marker category key.
        weight: Contribution weight (0.1–2.0).
        source: How the marker was created.
        confidence: Statistical confidence (0.0–1.0).
    """

    pattern: str
    display_name: str
    category: str
    weight: float
    source: Literal["manual", "statistical", "seed", "library"]
    confidence: float


class FingerprintExportItem(BaseModel):
    """Export shape for a single fingerprint with its markers.

    Attributes:
        group_id: SentinelOne group ID.
        markers: List of markers in portable format (no internal IDs).
    """

    group_id: str
    markers: list[FingerprintExportMarker]


class FingerprintImportRequest(BaseModel):
    """Request payload for importing fingerprints from JSON.

    Attributes:
        items: List of fingerprint export items to import.
    """

    model_config = ConfigDict(strict=True)

    items: list[FingerprintExportItem] = Field(min_length=1)


class FingerprintImportResponse(BaseModel):
    """Summary response for a fingerprint import operation.

    Attributes:
        imported: Number of fingerprints successfully imported/updated.
        skipped: Number of fingerprints skipped (e.g. group_id not found).
        errors: List of error messages for individual failures.
    """

    imported: int
    skipped: int
    errors: list[str]


class FingerprintSuggestionResponse(BaseModel):
    """Response shape for a TF-IDF computed fingerprint suggestion.

    Mirrors the ``FingerprintSuggestion`` TypeScript interface.

    Attributes:
        id: Unique suggestion identifier.
        group_id: SentinelOne group ID this suggestion targets.
        normalized_name: Lowercase normalised app name.
        display_name: Human-readable app name.
        score: TF-IDF relevance score.
        group_coverage: Fraction of in-group agents with this app (0.0–1.0).
        outside_coverage: Fraction of out-of-group agents with this app (0.0–1.0).
        agent_count_in_group: Absolute count of in-group agents with this app.
        agent_count_outside: Absolute count of out-of-group agents with this app.
        status: Workflow state (``"pending"``, ``"accepted"``, or ``"rejected"``).
        computed_at: ISO-8601 timestamp of the computation batch.
    """

    id: str
    group_id: str
    normalized_name: str
    display_name: str
    score: float
    group_coverage: float
    outside_coverage: float
    agent_count_in_group: int
    agent_count_outside: int
    status: Literal["pending", "accepted", "rejected"]
    computed_at: str
