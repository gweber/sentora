"""Fingerprint FastAPI routers.

Two routers are exported:

- ``fingerprint_router`` — mounted at ``/api/v1/fingerprints``.
  Handles CRUD for fingerprints and their markers.

- ``suggestions_router`` — mounted at ``/api/v1/suggestions``.
  Handles TF-IDF suggestion retrieval, computation, acceptance, and rejection.

All routes are async and use FastAPI dependency injection for the Motor
database handle. DTOs are used at every boundary — entities never leave
the service layer.
"""

from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.entities import UserRole
from domains.fingerprint import auto_proposer, repository, service
from domains.fingerprint.dto import (
    ApplyProposalResponse,
    AutoFingerprintProposalResponse,
    FingerprintImportRequest,
    FingerprintImportResponse,
    FingerprintMarkerResponse,
    FingerprintResponse,
    FingerprintSuggestionResponse,
    MarkerCreateRequest,
    MarkerReorderRequest,
    MarkerUpdateRequest,
    ProposedMarkerResponse,
)
from domains.fingerprint.entities import AutoFingerprintProposal, FingerprintMarker
from middleware.auth import get_current_user, require_role
from utils.distributed_lock import DistributedLock

fingerprint_router = APIRouter()
suggestions_router = APIRouter()


# ── Fingerprint routes ────────────────────────────────────────────────────────


@fingerprint_router.get(
    "/",
    summary="List fingerprints with pagination",
    dependencies=[Depends(get_current_user)],
)
async def list_fingerprints(
    page: int = Query(1, ge=1),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Return fingerprints with pagination, sorted by group_id.

    Args:
        page: Page number (1-indexed).
        limit: Maximum number of fingerprints per page (default 200, max 1000).
        db: Motor database (injected).

    Returns:
        Dict with fingerprints list, total count, page, and limit.
    """
    skip = (page - 1) * limit
    total = await repository.count_all(db)
    items = await service.list_fingerprints(db, skip=skip, limit=limit)
    return {"fingerprints": items, "total": total, "page": page, "limit": limit}


# ── Export / Import routes (must precede /{group_id} to avoid shadowing) ──────


@fingerprint_router.get(
    "/export",
    summary="Export all fingerprints as JSON",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def export_fingerprints(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Export all fingerprints as a downloadable JSON file.

    Each fingerprint includes its group_id and all markers with pattern,
    display_name, category, weight, source, and confidence fields.

    Args:
        db: Motor database (injected).

    Returns:
        JSON file response with Content-Disposition header.
    """
    items = await service.export_all_fingerprints(db)
    payload = [item.model_dump() for item in items]
    content = json.dumps(payload, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="fingerprints_export.json"'},
    )


@fingerprint_router.post(
    "/import",
    response_model=FingerprintImportResponse,
    summary="Import fingerprints from JSON",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def import_fingerprints(
    body: FingerprintImportRequest,
    strategy: str = Query("merge", pattern="^(merge|replace)$"),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FingerprintImportResponse:
    """Import fingerprints from a JSON payload.

    Supports two strategies via the ``strategy`` query parameter:

    - ``merge`` (default): Add markers from the import that don't already exist
      (matched by pattern). Update weights for markers whose pattern already
      exists.
    - ``replace``: Replace all markers for the fingerprint with the imported
      ones.

    Fingerprints targeting group_ids that don't exist in the database are
    skipped with a warning.

    Args:
        body: Import request containing the list of fingerprint items.
        strategy: Import strategy — ``"merge"`` or ``"replace"``.
        db: Motor database (injected).

    Returns:
        FingerprintImportResponse with imported/skipped counts and errors.
    """
    return await service.import_fingerprints(db, body.items, strategy)


# ── Proposal routes (must precede /{group_id} to avoid shadowing) ─────────────


@fingerprint_router.post(
    "/proposals/generate",
    summary="Trigger auto-fingerprint proposal generation",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def generate_proposals(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Launch a background job that computes Lift-based marker proposals for
    every group simultaneously.

    Returns HTTP 409 if a generation run is already in progress.

    Args:
        db: Motor database (injected).

    Returns:
        ``{"status": "started"}`` when the background task is queued.
    """
    dist_lock = DistributedLock(db, "proposal_generation", ttl_seconds=600)
    acquired = await dist_lock.acquire()
    if not acquired:
        raise HTTPException(status_code=409, detail="Proposal generation already running")
    # Start heartbeat to keep the lock alive during long proposal generation
    dist_lock._heartbeat_task = asyncio.create_task(dist_lock._heartbeat())
    asyncio.create_task(_run_proposal_generation(db, dist_lock))
    return {"status": "started"}


@fingerprint_router.get(
    "/proposals/",
    response_model=list[AutoFingerprintProposalResponse],
    summary="List all auto-fingerprint proposals",
    dependencies=[Depends(get_current_user)],
)
async def list_proposals(
    show_dismissed: bool = Query(False),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[AutoFingerprintProposalResponse]:
    """Return all proposals, sorted by quality score (mean lift) descending.

    Args:
        show_dismissed: When True, include dismissed proposals in the response.
        db: Motor database (injected).

    Returns:
        List of AutoFingerprintProposalResponse DTOs.
    """
    proposals = await repository.list_proposals(db, show_dismissed=show_dismissed)
    return [_proposal_to_response(p) for p in proposals]


@fingerprint_router.post(
    "/proposals/{group_id}/apply",
    response_model=ApplyProposalResponse,
    summary="Apply a proposal's markers to the group fingerprint",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def apply_proposal(
    group_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ApplyProposalResponse:
    """Apply all proposed markers to the group's fingerprint (add-only).

    Skips markers whose ``normalized_name`` already exists as a marker pattern.
    Updates the proposal status to ``"applied"``.

    Args:
        group_id: SentinelOne group ID.
        db: Motor database (injected).

    Returns:
        ApplyProposalResponse with ``added`` and ``skipped`` counts.
    """
    proposal = await repository.get_proposal(db, group_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    fp = await repository.get_by_group_id(db, group_id)
    if fp is None:
        raise HTTPException(
            status_code=404,
            detail="Fingerprint not found — create one for this group first",
        )

    existing_patterns = {m.pattern for m in fp.markers}
    markers_to_add: list[FingerprintMarker] = []
    skipped = 0

    for pm in proposal.proposed_markers:
        if pm.normalized_name in existing_patterns:
            skipped += 1
            continue
        markers_to_add.append(
            FingerprintMarker(
                pattern=pm.normalized_name,
                display_name=pm.display_name,
                source="statistical",
                confidence=min(1.0, pm.lift / 20.0),
                weight=1.0,
            )
        )
        existing_patterns.add(pm.normalized_name)

    if markers_to_add:
        from domains.fingerprint.repository import _marker_to_doc

        marker_docs = [_marker_to_doc(marker) for marker in markers_to_add]
        await db["fingerprints"].update_one(
            {"group_id": group_id},
            {"$push": {"markers": {"$each": marker_docs}}},
        )

    await repository.update_proposal_status(db, group_id, "applied")
    return ApplyProposalResponse(added=len(markers_to_add), skipped=skipped, status="applied")


@fingerprint_router.post(
    "/proposals/{group_id}/dismiss",
    summary="Dismiss a proposal",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def dismiss_proposal(
    group_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Mark a proposal as dismissed so it is hidden from the default list view.

    Args:
        group_id: SentinelOne group ID.
        db: Motor database (injected).

    Returns:
        ``{"status": "dismissed"}``
    """
    proposal = await repository.get_proposal(db, group_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await repository.update_proposal_status(db, group_id, "dismissed")
    return {"status": "dismissed"}


# ── Proposal background task ──────────────────────────────────────────────────


async def _run_proposal_generation(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    dist_lock: DistributedLock,
) -> None:
    """Background coroutine that runs proposal generation and persists results."""
    try:
        from domains.config.repository import get as get_config

        cfg = await get_config(db)
        proposals = await auto_proposer.generate_proposals(
            db,
            coverage_min=cfg.proposal_coverage_min,
            outside_max=cfg.proposal_outside_max,
            lift_min=cfg.proposal_lift_min,
            top_k=cfg.proposal_top_k,
        )
        await repository.save_proposals(db, proposals)
    except Exception:
        logger.exception("Proposal generation failed")
    finally:
        ht = getattr(dist_lock, "_heartbeat_task", None)
        if ht and not ht.done():
            ht.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await ht
        await dist_lock.release()


# ── Proposal DTO conversion ───────────────────────────────────────────────────


def _proposal_to_response(proposal: AutoFingerprintProposal) -> AutoFingerprintProposalResponse:  # type: ignore[return]
    p: AutoFingerprintProposal = proposal
    return AutoFingerprintProposalResponse(
        id=p.id,
        group_id=p.group_id,
        group_name=p.group_name,
        group_size=p.group_size,
        proposed_markers=[
            ProposedMarkerResponse(
                normalized_name=m.normalized_name,
                display_name=m.display_name,
                lift=m.lift,
                group_coverage=m.group_coverage,
                outside_coverage=m.outside_coverage,
                agent_count_in_group=m.agent_count_in_group,
                agent_count_outside=m.agent_count_outside,
                shared_with_groups=m.shared_with_groups,
            )
            for m in p.proposed_markers
        ],
        quality_score=p.quality_score,
        total_groups=p.total_groups,
        coverage_min=p.coverage_min,
        outside_max=p.outside_max,
        lift_min=p.lift_min,
        top_k=p.top_k,
        status=p.status,
        computed_at=p.computed_at.isoformat(),
    )


# ── Fingerprint routes ────────────────────────────────────────────────────────


@fingerprint_router.get(
    "/{group_id}",
    response_model=FingerprintResponse,
    summary="Get fingerprint for a group",
    dependencies=[Depends(get_current_user)],
)
async def get_fingerprint(
    group_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FingerprintResponse:
    """Fetch the fingerprint associated with a SentinelOne group.

    Args:
        group_id: SentinelOne group ID.
        db: Motor database (injected).

    Returns:
        FingerprintResponse for the group.
    """
    return await service.get_fingerprint(db, group_id)


@fingerprint_router.post(
    "/{group_id}",
    response_model=FingerprintResponse,
    status_code=201,
    summary="Create fingerprint for a group",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def create_fingerprint(
    group_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FingerprintResponse:
    """Create a new empty fingerprint for a SentinelOne group.

    Returns HTTP 409 if a fingerprint already exists for this group.

    Args:
        group_id: SentinelOne group ID.
        db: Motor database (injected).

    Returns:
        The newly created FingerprintResponse with HTTP 201.
    """
    return await service.create_fingerprint(db, group_id)


@fingerprint_router.post(
    "/{group_id}/markers",
    response_model=FingerprintMarkerResponse,
    status_code=201,
    summary="Add a marker to a fingerprint",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def add_marker(
    group_id: str,
    body: MarkerCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FingerprintMarkerResponse:
    """Add a new glob-pattern marker to an existing fingerprint.

    Args:
        group_id: SentinelOne group ID.
        body: Validated marker creation payload.
        db: Motor database (injected).

    Returns:
        The newly created FingerprintMarkerResponse with HTTP 201.
    """
    return await service.add_marker(db, group_id, body)


@fingerprint_router.patch(
    "/{group_id}/markers/{marker_id}",
    response_model=FingerprintMarkerResponse,
    summary="Update a marker",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def update_marker(
    group_id: str,
    marker_id: str,
    body: MarkerUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FingerprintMarkerResponse:
    """Partially update an existing marker (weight, pattern, and/or display_name).

    Args:
        group_id: SentinelOne group ID.
        marker_id: ID of the marker to update.
        body: Partial update payload.
        db: Motor database (injected).

    Returns:
        The updated FingerprintMarkerResponse.
    """
    return await service.update_marker(db, group_id, marker_id, body)


@fingerprint_router.delete(
    "/{group_id}/markers/{marker_id}",
    status_code=204,
    summary="Delete a marker",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def delete_marker(
    group_id: str,
    marker_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Remove a marker from a fingerprint.

    Args:
        group_id: SentinelOne group ID.
        marker_id: ID of the marker to delete.
        db: Motor database (injected).

    Returns:
        HTTP 204 No Content.
    """
    await service.delete_marker(db, group_id, marker_id)
    return Response(status_code=204)


@fingerprint_router.put(
    "/{group_id}/markers/order",
    status_code=204,
    summary="Reorder markers",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def reorder_markers(
    group_id: str,
    body: MarkerReorderRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Reorder the markers within a fingerprint.

    The request body must contain the complete ordered list of all marker IDs.

    Args:
        group_id: SentinelOne group ID.
        body: Reorder request with the desired ordered list of marker IDs.
        db: Motor database (injected).

    Returns:
        HTTP 204 No Content.
    """
    await service.reorder_markers(db, group_id, body)
    return Response(status_code=204)


# ── Suggestion routes ─────────────────────────────────────────────────────────


@suggestions_router.get(
    "/{group_id}",
    response_model=list[FingerprintSuggestionResponse],
    summary="Get computed suggestions for a group",
    dependencies=[Depends(get_current_user)],
)
async def get_suggestions(
    group_id: str,
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[FingerprintSuggestionResponse]:
    """Return existing (non-rejected) suggestions for a group.

    Returns an empty list if no suggestions have been computed yet.

    Args:
        group_id: SentinelOne group ID.
        limit: Maximum number of suggestions to return (default 200, max 1000).
        db: Motor database (injected).

    Returns:
        List of FingerprintSuggestionResponse DTOs sorted by score descending.
    """
    results = await service.get_suggestions(db, group_id)
    return results[:limit]


@suggestions_router.post(
    "/{group_id}/compute",
    response_model=list[FingerprintSuggestionResponse],
    summary="Compute TF-IDF suggestions for a group",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def compute_suggestions(
    group_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[FingerprintSuggestionResponse]:
    """Recompute TF-IDF suggestions for a group from current installed-app data.

    Replaces all pending suggestions with freshly computed results.

    Args:
        group_id: SentinelOne group ID.
        db: Motor database (injected).

    Returns:
        List of newly computed FingerprintSuggestionResponse DTOs.
    """
    return await service.compute_suggestions(db, group_id)


@suggestions_router.post(
    "/{group_id}/accept/{suggestion_id}",
    status_code=204,
    summary="Accept a suggestion",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def accept_suggestion(
    group_id: str,
    suggestion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Accept a suggestion — marks it accepted and adds it as a statistical marker.

    Args:
        group_id: SentinelOne group ID.
        suggestion_id: ID of the suggestion to accept.
        db: Motor database (injected).

    Returns:
        HTTP 204 No Content.
    """
    await service.accept_suggestion(db, group_id, suggestion_id)
    return Response(status_code=204)


@suggestions_router.post(
    "/{group_id}/reject/{suggestion_id}",
    status_code=204,
    summary="Reject a suggestion",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def reject_suggestion(
    group_id: str,
    suggestion_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Soft-delete a suggestion by marking it as rejected.

    Rejected suggestions are excluded from future ``GET /suggestions/{group_id}``
    responses.

    Args:
        group_id: SentinelOne group ID.
        suggestion_id: ID of the suggestion to reject.
        db: Motor database (injected).

    Returns:
        HTTP 204 No Content.
    """
    await service.reject_suggestion(db, group_id, suggestion_id)
    return Response(status_code=204)
