"""Fingerprint domain entities.

These Pydantic models represent the canonical in-memory and MongoDB-persisted
shapes for fingerprints and their suggestions. No HTTP or DTO concerns here —
the service layer converts between entities and DTOs.

MongoDB storage notes
---------------------
- Fingerprints are stored in the ``fingerprints`` collection.
- The ``id`` field maps to MongoDB ``_id`` via ``alias="_id"``.
- Suggestions are stored in a separate ``fingerprint_suggestions`` collection,
  keyed by ``group_id``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from utils.dt import utc_now


class FingerprintMarker(BaseModel):
    """A single pattern-based marker within a fingerprint.

    Attributes:
        id: Unique marker identifier (string ObjectId).
        pattern: Glob pattern matched against ``normalized_name`` in installed
            apps (supports ``*`` and ``?`` wildcards).
        display_name: Human-readable label shown in the UI.
        category: Marker category key (e.g. ``"name_pattern"``).
        weight: Contribution weight used in scoring (0.1–2.0, default 1.0).
        source: How the marker was created — ``"manual"``, ``"statistical"``,
            or ``"seed"``.
        confidence: Statistical confidence of the marker (0.0–1.0).
        added_at: Timestamp when the marker was added.
        added_by: Identifier of the user or system that added the marker.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    pattern: str
    display_name: str
    category: str = "name_pattern"
    weight: float = 1.0
    source: Literal["manual", "statistical", "seed", "library"] = "manual"
    confidence: float = 1.0
    added_at: datetime = Field(default_factory=utc_now)
    added_by: str = "system"


class Fingerprint(BaseModel):
    """A fingerprint associated with a SentinelOne agent group.

    Attributes:
        id: MongoDB document identifier (string ObjectId).
        group_id: SentinelOne group ID this fingerprint belongs to.
        group_name: Human-readable group name (denormalised for display).
        markers: Ordered list of glob-pattern markers used for scoring.
        created_at: Timestamp of creation.
        updated_at: Timestamp of the most recent update.
        created_by: Identifier of the user or system that created the fingerprint.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    group_id: str
    group_name: str = ""
    site_name: str = ""
    account_name: str = ""
    markers: list[FingerprintMarker] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = "system"


class ProposedMarker(BaseModel):
    """A single marker proposed by the auto-fingerprint engine.

    Attributes:
        normalized_name: Lowercase normalised app name used as the pattern.
        display_name: Human-readable label shown in the UI.
        lift: Lift statistic — how many times more likely an agent in this
            group is to have this app compared to a random fleet agent.
        group_coverage: Fraction of group agents that have this app (0.0–1.0).
        outside_coverage: Fraction of non-group agents with this app (0.0–1.0).
        agent_count_in_group: Absolute in-group agent count.
        agent_count_outside: Absolute out-of-group agent count.
        shared_with_groups: Group IDs of other groups that also propose this app.
    """

    normalized_name: str
    display_name: str
    lift: float
    group_coverage: float
    outside_coverage: float
    agent_count_in_group: int
    agent_count_outside: int
    shared_with_groups: list[str] = Field(default_factory=list)


class AutoFingerprintProposal(BaseModel):
    """A complete auto-computed fingerprint proposal for one group.

    Attributes:
        id: MongoDB document identifier.
        group_id: SentinelOne group ID this proposal targets.
        group_name: Human-readable group name.
        proposed_markers: Ranked list of proposed markers (lift desc).
        quality_score: Mean lift across proposed markers.
        total_groups: Total number of groups analysed in this run.
        coverage_min: ``coverage_min`` threshold used in computation.
        outside_max: ``outside_max`` threshold used in computation.
        lift_min: ``lift_min`` threshold used in computation.
        top_k: ``top_k`` cap used in computation.
        status: Workflow state — ``"pending"``, ``"applied"``, or ``"dismissed"``.
        computed_at: Timestamp of the computation run.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    group_id: str
    group_name: str
    group_size: int = 0
    proposed_markers: list[ProposedMarker] = Field(default_factory=list)
    quality_score: float = 0.0
    total_groups: int = 0
    coverage_min: float = 0.60
    outside_max: float = 0.25
    lift_min: float = 2.0
    top_k: int = 10
    status: Literal["pending", "applied", "dismissed"] = "pending"
    computed_at: datetime = Field(default_factory=utc_now)


class FingerprintSuggestion(BaseModel):
    """A TF-IDF-derived suggestion for a fingerprint marker.

    Suggestions are computed from installed-app frequency data and ranked by
    how strongly an app distinguishes the target group from all other agents.

    Attributes:
        id: Unique suggestion identifier (string ObjectId).
        group_id: SentinelOne group ID this suggestion targets.
        normalized_name: Lowercase normalised app name (as stored in
            ``s1_installed_apps``).
        display_name: Human-readable version of the app name.
        score: TF-IDF relevance score (higher is more distinctive).
        group_coverage: Fraction of agents *in* the group that have this app
            (0.0–1.0).
        outside_coverage: Fraction of agents *outside* the group that have
            this app (0.0–1.0).
        agent_count_in_group: Absolute number of in-group agents with this app.
        agent_count_outside: Absolute number of out-of-group agents with this app.
        status: Workflow state — ``"pending"``, ``"accepted"``, or ``"rejected"``.
        computed_at: Timestamp when the suggestion batch was computed.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    group_id: str
    normalized_name: str
    display_name: str
    score: float
    group_coverage: float
    outside_coverage: float
    agent_count_in_group: int
    agent_count_outside: int
    status: Literal["pending", "accepted", "rejected"] = "pending"
    computed_at: datetime = Field(default_factory=utc_now)
