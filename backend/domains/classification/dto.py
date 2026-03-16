"""Classification domain DTOs.

Response and request data-transfer objects used by the HTTP layer. These
mirror the TypeScript interfaces on the frontend exactly; field names and
types must remain in sync.

All response DTOs use ``model_config = ConfigDict(from_attributes=True)`` so
they can be constructed directly from entity instances.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ── Shared sub-models ─────────────────────────────────────────────────────────


class GroupMatchScoreResponse(BaseModel):
    """Serialisable representation of a single group match score.

    Mirrors the TypeScript ``GroupMatchScore`` interface.
    """

    model_config = ConfigDict(from_attributes=True)

    group_id: str
    group_name: str
    score: float
    matched_markers: list[str]
    missing_markers: list[str]


# ── Classification result ─────────────────────────────────────────────────────


class ClassificationResultResponse(BaseModel):
    """Full classification result for one agent.

    Mirrors the TypeScript ``ClassificationResult`` interface. The
    ``computed_at`` field is serialised as an ISO-8601 string.
    """

    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    hostname: str
    current_group_id: str
    current_group_name: str
    match_scores: list[GroupMatchScoreResponse]
    classification: str
    suggested_group_id: str | None = None
    suggested_group_name: str | None = None
    anomaly_reasons: list[str] = Field(default_factory=list)
    computed_at: datetime
    acknowledged: bool


# ── Overview ──────────────────────────────────────────────────────────────────


class ClassificationOverviewResponse(BaseModel):
    """Aggregate statistics across all classified agents.

    Mirrors the TypeScript ``ClassificationOverview`` interface.

    Attributes:
        total: Total number of agents with a classification result.
        correct: Agents whose classification verdict is ``"correct"``.
        misclassified: Agents whose verdict is ``"misclassified"``.
        ambiguous: Agents whose verdict is ``"ambiguous"``.
        unclassifiable: Agents whose verdict is ``"unclassifiable"``.
        groups_count: Number of distinct groups present in ``s1_agents``.
        last_computed_at: ISO-8601 timestamp of the most recent classification
            result, or ``None`` if no results exist yet.
    """

    model_config = ConfigDict(from_attributes=True)

    total: int
    correct: int
    misclassified: int
    ambiguous: int
    unclassifiable: int
    groups_count: int
    last_computed_at: datetime | None = None


# ── Paginated list ────────────────────────────────────────────────────────────


class ClassificationResultListResponse(BaseModel):
    """Paginated list of classification results.

    Mirrors the TypeScript ``ClassificationResultListResponse`` interface.
    """

    model_config = ConfigDict(from_attributes=True)

    results: list[ClassificationResultResponse]
    total: int
    page: int
    limit: int


# ── Classification run ────────────────────────────────────────────────────────


class ClassificationRunResponse(BaseModel):
    """Metadata for a single classification pipeline run.

    Attributes:
        id: Run identifier.
        started_at: When the run was triggered.
        completed_at: When the run finished (``None`` while still running).
        status: ``"running"``, ``"completed"``, or ``"failed"``.
        trigger: How the run was initiated.
        agents_classified: Number of agents successfully classified.
        errors: Number of per-agent errors encountered.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    trigger: str
    agents_classified: int
    errors: int


# ── Request filter ────────────────────────────────────────────────────────────


class ClassificationResultFilter(BaseModel):
    """Query parameters for filtering and paginating classification results.

    Attributes:
        page: 1-based page number (default: 1).
        limit: Maximum results per page (default: 50).
        classification: If set, only return results with this verdict.
        group_id: If set, filter by ``current_group_id``.
        search: If set, filter by hostname substring (case-insensitive).
        acknowledged: If set, filter by acknowledgement state.
    """

    page: int = 1
    limit: int = 50
    classification: str | None = None
    group_id: str | None = None
    search: str | None = None
    acknowledged: bool | None = None
