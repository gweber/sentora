"""Classification domain service layer."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

import domains.classification.repository as repo
from audit.log import audit
from domains.classification.classifier import classification_manager
from domains.classification.dto import (
    ClassificationOverviewResponse,
    ClassificationResultFilter,
    ClassificationResultListResponse,
    ClassificationResultResponse,
    ClassificationRunResponse,
    GroupMatchScoreResponse,
)
from domains.classification.entities import ClassificationResult, ClassificationRun
from errors import ClassificationNotFoundError


def _result_to_response(result: ClassificationResult) -> ClassificationResultResponse:
    return ClassificationResultResponse(
        agent_id=result.agent_id,
        hostname=result.hostname,
        current_group_id=result.current_group_id,
        current_group_name=result.current_group_name,
        match_scores=[
            GroupMatchScoreResponse(
                group_id=s.group_id,
                group_name=s.group_name,
                score=s.score,
                matched_markers=s.matched_markers,
                missing_markers=s.missing_markers,
            )
            for s in result.match_scores
        ],
        classification=result.classification,
        suggested_group_id=result.suggested_group_id,
        suggested_group_name=result.suggested_group_name,
        anomaly_reasons=result.anomaly_reasons,
        computed_at=result.computed_at,
        acknowledged=result.acknowledged,
    )


def _run_to_response(run: ClassificationRun) -> ClassificationRunResponse:
    return ClassificationRunResponse(
        id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        trigger=run.trigger,
        agents_classified=run.agents_classified,
        errors=run.errors,
    )


async def get_overview(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> ClassificationOverviewResponse:
    data = await repo.get_overview(db)
    return ClassificationOverviewResponse(
        total=data["total"],
        correct=data["correct"],
        misclassified=data["misclassified"],
        ambiguous=data["ambiguous"],
        unclassifiable=data["unclassifiable"],
        groups_count=data["groups_count"],
        last_computed_at=data.get("last_computed_at"),
    )


async def list_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    f: ClassificationResultFilter,
) -> ClassificationResultListResponse:
    results, total = await repo.list_results(db, f)
    return ClassificationResultListResponse(
        results=[_result_to_response(r) for r in results],
        total=total,
        page=f.page,
        limit=f.limit,
    )


async def get_by_agent(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    agent_id: str,
) -> ClassificationResultResponse:
    result = await repo.get_by_agent_id(db, agent_id)
    if result is None:
        raise ClassificationNotFoundError(
            f"No classification result found for agent '{agent_id}'.",
            {"agent_id": agent_id},
        )
    return _result_to_response(result)


async def trigger_classification(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    trigger: str = "manual",
) -> ClassificationRunResponse | None:
    run = await classification_manager.trigger(db, trigger=trigger)
    if run is None:
        return None
    await audit(
        db,
        domain="classification",
        action="classification.triggered",
        actor="user" if trigger == "manual" else "system",
        summary=f"Classification run triggered ({trigger})",
        details={"run_id": run.id, "trigger": trigger},
    )
    return _run_to_response(run)


async def acknowledge(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    agent_id: str,
) -> None:
    found = await repo.acknowledge(db, agent_id)
    if not found:
        raise ClassificationNotFoundError(
            f"No classification result found for agent '{agent_id}'.",
            {"agent_id": agent_id},
        )
    await audit(
        db,
        domain="classification",
        action="anomaly.acknowledged",
        actor="user",
        summary=f"Anomaly acknowledged for agent {agent_id}",
        details={"agent_id": agent_id},
    )
