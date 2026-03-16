"""Classification domain router.

Exposes the following endpoints under the ``/classification`` prefix:

- ``GET  /overview``               — Aggregate verdict statistics.
- ``GET  /results``                — Paginated, filtered list of results.
- ``GET  /results/{agent_id}``     — Single agent result.
- ``POST /trigger``                — Start a new classification run.
- ``POST /acknowledge/{agent_id}`` — Acknowledge an agent's anomaly.
- ``GET  /export``                 — Download results as CSV or JSON.
"""

from __future__ import annotations

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.entities import UserRole
from domains.classification import service
from domains.classification.dto import (
    ClassificationOverviewResponse,
    ClassificationResultFilter,
    ClassificationResultListResponse,
    ClassificationResultResponse,
    ClassificationRunResponse,
)
from errors import ClassificationNotFoundError
from middleware.auth import get_current_user, require_role

router = APIRouter()


# ── Dependency ────────────────────────────────────────────────────────────────


DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_tenant_db)]  # type: ignore[type-arg]


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get(
    "/overview",
    response_model=ClassificationOverviewResponse,
    summary="Classification overview statistics",
    dependencies=[Depends(get_current_user)],
)
async def get_overview(db: DbDep) -> ClassificationOverviewResponse:
    """Return aggregate verdict counts and metadata for the overview panel."""
    return await service.get_overview(db)


@router.get(
    "/results",
    response_model=ClassificationResultListResponse,
    summary="List classification results",
    dependencies=[Depends(get_current_user)],
)
async def get_results(
    db: DbDep,
    page: int = Query(default=1, ge=1, description="1-based page number"),
    limit: int = Query(default=50, ge=1, le=500, description="Results per page"),
    classification: str | None = Query(default=None, description="Filter by verdict"),
    group_id: str | None = Query(default=None, description="Filter by current_group_id"),
    search: str | None = Query(default=None, description="Hostname substring filter"),
    acknowledged: bool | None = Query(default=None, description="Filter by acknowledgement state"),
) -> ClassificationResultListResponse:
    """Return a paginated list of classification results with optional filters."""
    f = ClassificationResultFilter(
        page=page,
        limit=limit,
        classification=classification,
        group_id=group_id,
        search=search,
        acknowledged=acknowledged,
    )
    return await service.list_results(db, f)


@router.get(
    "/results/{agent_id}",
    response_model=ClassificationResultResponse,
    summary="Get classification result for a single agent",
    dependencies=[Depends(get_current_user)],
)
async def get_result(agent_id: str, db: DbDep) -> ClassificationResultResponse:
    """Return the classification result for the specified agent.

    Raises 404 if no result has been computed for the agent yet.
    """
    try:
        return await service.get_by_agent(db, agent_id)
    except ClassificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.post(
    "/trigger",
    response_model=ClassificationRunResponse,
    status_code=202,
    summary="Trigger a classification run",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def trigger_classification(db: DbDep) -> ClassificationRunResponse:
    """Start a new background classification run.

    Returns 409 if a run is already in progress.
    """
    run = await service.trigger_classification(db, trigger="manual")
    if run is None:
        raise HTTPException(
            status_code=409,
            detail="A classification run is already in progress.",
        )
    return run


@router.post(
    "/acknowledge/{agent_id}",
    status_code=204,
    summary="Acknowledge an agent's classification anomaly",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def acknowledge_anomaly(agent_id: str, db: DbDep) -> Response:
    """Mark the classification result for the given agent as acknowledged.

    Raises 404 if no result exists for the agent.
    """
    try:
        await service.acknowledge(db, agent_id)
    except ClassificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return Response(status_code=204)


@router.get(
    "/export",
    summary="Export classification results",
    dependencies=[Depends(get_current_user)],
)
async def export_results(
    db: DbDep,
    format: Literal["csv", "json"] = Query(default="csv", description="Export format"),
    classification: str | None = Query(default=None, description="Filter by verdict"),
    search: str | None = Query(default=None, description="Hostname substring filter"),
    group_id: str | None = Query(default=None, description="Filter by current_group_id"),
) -> Response:
    """Download classification results as CSV or JSON, respecting active filters.

    Query parameters:
    - ``format``         — ``csv`` (default) or ``json``
    - ``classification`` — verdict filter (correct / misclassified / ambiguous / unclassifiable)
    - ``search``         — hostname substring filter
    - ``group_id``       — filter by SentinelOne group ID

    CSV columns: hostname, current_group, classification, suggested_group,
    top_score, computed_at, acknowledged.
    """
    f = ClassificationResultFilter(
        page=1,
        limit=10_000,
        classification=classification,
        search=search,
        group_id=group_id,
    )
    response_dto = await service.list_results(db, f)
    results = response_dto.results
    truncated = response_dto.total > len(results)

    if format == "json":
        import json

        payload = json.dumps(
            {
                "results": [r.model_dump(mode="json") for r in results],
                "truncated": truncated,
                "total": response_dto.total,
            },
            default=str,
        )
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="classification_results.json"'},
        )

    # CSV export
    from utils.csv_sanitize import sanitize_csv_cell as _sanitize_csv_cell

    def _generate_csv() -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "hostname",
                "current_group",
                "classification",
                "suggested_group",
                "top_score",
                "computed_at",
                "acknowledged",
            ]
        )
        for r in results:
            top_score = r.match_scores[0].score if r.match_scores else 0.0
            writer.writerow(
                [
                    _sanitize_csv_cell(r.hostname),
                    _sanitize_csv_cell(r.current_group_name),
                    r.classification,
                    _sanitize_csv_cell(r.suggested_group_name or ""),
                    f"{top_score:.4f}",
                    r.computed_at.isoformat(),
                    str(r.acknowledged).lower(),
                ]
            )
        return output.getvalue().encode("utf-8")

    csv_bytes = _generate_csv()

    headers = {
        "Content-Disposition": 'attachment; filename="classification_results.csv"',
    }
    if truncated:
        headers["X-Truncated"] = "true"
        headers["X-Total-Count"] = str(response_dto.total)

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers=headers,
    )
