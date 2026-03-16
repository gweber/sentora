"""REST API router for audit hash-chain operations.

Endpoints for chain verification, status, epoch listing, and epoch
export.  All endpoints require at minimum analyst-level access.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.chain.commands import initialize_chain
from audit.chain.dtos import (
    ChainStatusResponse,
    EpochListResponse,
    VerifyChainRequest,
    VerifyChainResponse,
)
from audit.chain.queries import export_epoch, get_chain_status, list_epochs, verify_chain
from database import get_tenant_db
from domains.auth.entities import UserRole
from middleware.auth import require_role

router = APIRouter()


@router.post(
    "/verify",
    response_model=VerifyChainResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def verify_audit_chain(
    body: VerifyChainRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Verify the integrity of the audit hash-chain.

    Checks sequence continuity and hash integrity.  When ``epoch`` is
    ``null``, the entire chain is verified in batches.

    Returns verification result with status, counts, and failure details.
    """
    result = await verify_chain(db, epoch=body.epoch)
    return JSONResponse(
        {
            "status": result.status.value,
            "verified_entries": result.verified_entries,
            "first_sequence": result.first_sequence,
            "last_sequence": result.last_sequence,
            "epochs_verified": result.epochs_verified,
            "broken_at_sequence": result.broken_at_sequence,
            "broken_reason": result.broken_reason.value if result.broken_reason else None,
            "verification_time_ms": result.verification_time_ms,
        }
    )


@router.get(
    "/status",
    response_model=ChainStatusResponse,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def chain_status(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Return current audit chain statistics.

    Includes total entries, current epoch/sequence, genesis hash,
    latest hash, and last verification result.
    """
    status = await get_chain_status(db)
    return JSONResponse(
        {
            "total_entries": status.total_entries,
            "current_epoch": status.current_epoch,
            "current_sequence": status.current_sequence,
            "genesis_hash": status.genesis_hash,
            "latest_hash": status.latest_hash,
            "chain_valid": status.chain_valid,
            "last_verified_at": status.last_verified_at.isoformat()
            if status.last_verified_at
            else None,
        }
    )


@router.get(
    "/epochs",
    response_model=EpochListResponse,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def list_chain_epochs(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """List all completed epochs with summary information.

    Each epoch includes sequence range, timestamps, entry count, and
    whether it has been exported.
    """
    epochs = await list_epochs(db)
    return JSONResponse(
        {
            "epochs": [
                {
                    "epoch": e.epoch,
                    "first_sequence": e.first_sequence,
                    "last_sequence": e.last_sequence,
                    "entry_count": e.entry_count,
                    "first_timestamp": e.first_timestamp.isoformat()
                    if hasattr(e.first_timestamp, "isoformat")
                    else str(e.first_timestamp),
                    "last_timestamp": e.last_timestamp.isoformat()
                    if hasattr(e.last_timestamp, "isoformat")
                    else str(e.last_timestamp),
                    "epoch_final_hash": e.epoch_final_hash,
                    "previous_epoch_hash": e.previous_epoch_hash,
                    "exported": e.exported,
                }
                for e in epochs
            ],
            "total": len(epochs),
        }
    )


@router.post(
    "/export/{epoch_number}",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def export_chain_epoch(
    epoch_number: int,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    """Export a completed epoch as a downloadable JSON archive.

    The export is a self-contained file suitable for air-gapped
    verification.  Includes all entries and an integrity hash.
    """
    export = await export_epoch(db, epoch_number)
    payload = json.dumps(
        {"export_metadata": export.metadata, "entries": export.entries},
        indent=2,
        ensure_ascii=True,
        default=str,
    )
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="audit_epoch_{epoch_number}.json"',
        },
    )


@router.post(
    "/initialize",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def initialize_audit_chain(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Initialize the audit hash-chain by creating the genesis entry.

    Idempotent — returns the existing genesis entry if the chain has
    already been initialized.
    """
    entry = await initialize_chain(db)
    entry_copy = dict(entry)
    entry_copy.pop("_id", None)
    if hasattr(entry_copy.get("timestamp"), "isoformat"):
        entry_copy["timestamp"] = entry_copy["timestamp"].isoformat()
    return JSONResponse(entry_copy, status_code=201)
