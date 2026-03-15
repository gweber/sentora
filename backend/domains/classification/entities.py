"""Classification domain entities.

These Pydantic models represent the canonical in-memory and MongoDB-persisted
shapes for classification results and runs. No HTTP or DTO concerns here —
the service layer converts between entities and DTOs.

MongoDB storage notes
---------------------
- Classification results are stored in the ``classification_results`` collection,
  one document per agent (upserted by ``agent_id``).
- The ``id`` field maps to MongoDB ``_id`` via ``alias="_id"``.
- Classification runs are stored in the ``classification_runs`` collection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from utils.dt import utc_now


class GroupMatchScore(BaseModel):
    """Score of a single fingerprint/group against an agent's installed apps.

    Attributes:
        group_id: SentinelOne group ID of the fingerprint.
        group_name: Human-readable group name (denormalised for display).
        score: Weighted match score in [0.0, 1.0].
        matched_markers: Display names of markers whose pattern was found in
            the agent's installed apps.
        missing_markers: Display names of markers whose pattern was *not* found.
    """

    group_id: str
    group_name: str
    score: float
    matched_markers: list[str]
    missing_markers: list[str]


class ClassificationResult(BaseModel):
    """Full classification result for a single agent.

    One document per agent is stored in ``classification_results``; subsequent
    classification runs upsert the document by ``agent_id``.

    Attributes:
        id: MongoDB document identifier (string ObjectId).
        run_id: ID of the ClassificationRun that produced this result.
        agent_id: SentinelOne agent ID (``s1_agent_id`` in ``s1_agents``).
        hostname: Agent hostname (denormalised for display).
        current_group_id: Group the agent currently belongs to in SentinelOne.
        current_group_name: Human-readable current group name.
        match_scores: Top-5 fingerprint match scores, sorted descending.
        classification: Verdict — ``"correct"``, ``"misclassified"``,
            ``"ambiguous"``, or ``"unclassifiable"``.
        suggested_group_id: ID of the suggested correct group (only for
            ``"misclassified"`` verdict).
        suggested_group_name: Human-readable suggested group name.
        anomaly_reasons: List of human-readable anomaly descriptions.
        computed_at: Timestamp when this result was computed.
        acknowledged: Whether an operator has acknowledged this result.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    run_id: str
    agent_id: str
    hostname: str
    current_group_id: str
    current_group_name: str
    match_scores: list[GroupMatchScore]
    classification: Literal["correct", "misclassified", "ambiguous", "unclassifiable"]
    suggested_group_id: str | None = None
    suggested_group_name: str | None = None
    anomaly_reasons: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=utc_now)
    acknowledged: bool = False


class ClassificationRun(BaseModel):
    """Metadata for a single classification pipeline execution.

    Attributes:
        id: MongoDB document identifier (string ObjectId).
        started_at: Timestamp when the run was initiated.
        completed_at: Timestamp when the run finished (None while running).
        status: Current state — ``"running"``, ``"completed"``, or ``"failed"``.
        trigger: How the run was initiated (e.g. ``"manual"`` or ``"scheduled"``).
        agents_classified: Number of agents successfully classified.
        errors: Number of agents that encountered an error during classification.
        error_log: List of error messages for debugging.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    trigger: str = "manual"
    agents_classified: int = 0
    errors: int = 0
    error_log: list[str] = Field(default_factory=list)
