"""Query handlers for audit hash-chain read operations.

Follows CQRS: queries read state without side effects (except for
persisting verification results as an operational concern).
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.chain.entities import (
    BrokenReason,
    ChainStatus,
    ChainStatusInfo,
    EpochExport,
    EpochSummary,
    VerificationResult,
)
from audit.chain.hasher import CHAIN_ALGORITHM, compute_entry_hash, compute_export_hash
from audit.chain.repository import (
    count_chained_entries,
    get_completed_epochs,
    get_epoch_boundary_entry,
    get_epoch_size,
    get_exported_epochs,
    get_genesis_entry,
    get_last_verification,
    get_latest_chained_entry,
    mark_epoch_exported,
    save_verification_result,
    stream_entries_for_epoch,
    stream_entries_in_range,
)
from errors import ChainNotInitializedError, EpochNotCompleteError, EpochNotFoundError
from utils.dt import utc_now


async def verify_chain(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    epoch: int | None = None,
) -> VerificationResult:
    """Verify the integrity of the audit hash-chain.

    Checks sequence continuity (no gaps) and hash-chain integrity
    (each entry's hash matches the recomputed value).

    When ``epoch`` is ``None``, the entire chain is verified in
    epoch-sized batches to bound memory usage.  When a specific epoch
    is given, only that epoch is verified.

    Args:
        db: Tenant database handle.
        epoch: Specific epoch to verify, or ``None`` for the full chain.

    Returns:
        VerificationResult with status, counts, and any failure details.

    Raises:
        ChainNotInitializedError: If no genesis entry exists.
    """
    start_time = time.monotonic()

    genesis = await get_genesis_entry(db)
    if genesis is None:
        raise ChainNotInitializedError("Chain has not been initialized — no genesis entry")

    if epoch is not None:
        result = await _verify_single_epoch(db, epoch)
    else:
        result = await _verify_full_chain(db)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    result = VerificationResult(
        status=result.status,
        verified_entries=result.verified_entries,
        first_sequence=result.first_sequence,
        last_sequence=result.last_sequence,
        epochs_verified=result.epochs_verified,
        broken_at_sequence=result.broken_at_sequence,
        broken_reason=result.broken_reason,
        verification_time_ms=elapsed_ms,
    )

    # Persist the result
    await save_verification_result(db, {
        "status": result.status.value,
        "verified_entries": result.verified_entries,
        "chain_valid": result.status == ChainStatus.VALID,
        "verified_at": utc_now(),
        "broken_at_sequence": result.broken_at_sequence,
        "broken_reason": result.broken_reason.value if result.broken_reason else None,
        "verification_time_ms": result.verification_time_ms,
    })

    logger.info(
        "Chain verification complete: status={}, entries={}, time={}ms",
        result.status.value,
        result.verified_entries,
        result.verification_time_ms,
    )

    # Fire webhook on integrity failure
    if result.status != ChainStatus.VALID:
        try:
            from domains.webhooks.service import dispatch_event

            await dispatch_event(db, "audit.chain.integrity_failure", {
                "broken_at_sequence": result.broken_at_sequence,
                "reason": result.broken_reason.value if result.broken_reason else None,
                "epoch": result.broken_at_sequence // 1000 if result.broken_at_sequence else None,
                "verified_entries": result.verified_entries,
                "source": "audit",
            })
        except Exception as exc:
            logger.warning("Failed to dispatch audit chain integrity webhook: {}", exc)

    return result


async def _verify_full_chain(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> VerificationResult:
    """Verify the entire chain from genesis to latest entry."""
    epoch_size = await get_epoch_size(db)
    latest = await get_latest_chained_entry(db)
    if latest is None:
        return VerificationResult(
            status=ChainStatus.VALID,
            verified_entries=0,
            first_sequence=0,
            last_sequence=0,
            epochs_verified=0,
        )

    max_sequence = latest["sequence"]
    total_verified = 0
    epochs_verified = 0
    previous_hash: str | None = None

    # Process in batches of epoch_size
    batch_start = 0
    while batch_start <= max_sequence:
        batch_end = min(batch_start + epoch_size - 1, max_sequence)
        entries = await stream_entries_in_range(db, batch_start, batch_end)

        result = _verify_batch(entries, batch_start, previous_hash)
        if result is not None:
            return VerificationResult(
                status=result[0],
                verified_entries=total_verified + result[2],
                first_sequence=0,
                last_sequence=result[1],
                epochs_verified=epochs_verified,
                broken_at_sequence=result[1],
                broken_reason=result[3],
            )

        total_verified += len(entries)
        if entries:
            previous_hash = entries[-1].get("hash")
            current_epoch = entries[-1].get("epoch", 0)
            if entries[-1].get("is_epoch_end") or batch_end == max_sequence:
                epochs_verified = current_epoch + 1

        batch_start = batch_end + 1

    return VerificationResult(
        status=ChainStatus.VALID,
        verified_entries=total_verified,
        first_sequence=0,
        last_sequence=max_sequence,
        epochs_verified=epochs_verified,
    )


async def _verify_single_epoch(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    epoch: int,
) -> VerificationResult:
    """Verify a single epoch's internal chain integrity."""
    entries = await stream_entries_for_epoch(db, epoch)
    if not entries:
        raise EpochNotFoundError(
            f"Epoch {epoch} not found",
            detail={"epoch": epoch},
        )

    first_seq = entries[0]["sequence"]
    last_seq = entries[-1]["sequence"]

    # For epoch 0, the first entry's previous_hash should be None
    # For later epochs, we trust the stored previous_hash of the first entry
    initial_prev_hash = entries[0].get("previous_hash")

    result = _verify_batch(entries, first_seq, initial_prev_hash, skip_first_prev_check=True)
    if result is not None:
        return VerificationResult(
            status=result[0],
            verified_entries=result[2],
            first_sequence=first_seq,
            last_sequence=result[1],
            epochs_verified=0,
            broken_at_sequence=result[1],
            broken_reason=result[3],
        )

    return VerificationResult(
        status=ChainStatus.VALID,
        verified_entries=len(entries),
        first_sequence=first_seq,
        last_sequence=last_seq,
        epochs_verified=1,
    )


def _verify_batch(
    entries: list[dict[str, Any]],
    expected_start: int,
    expected_prev_hash: str | None,
    *,
    skip_first_prev_check: bool = False,
) -> tuple[ChainStatus, int, int, BrokenReason] | None:
    """Verify a batch of entries for sequence continuity and hash integrity.

    Args:
        entries: Ordered list of entry dicts.
        expected_start: Expected sequence number of the first entry.
        expected_prev_hash: Expected previous hash of the first entry.
        skip_first_prev_check: If True, don't check the first entry's
            previous_hash against ``expected_prev_hash`` (used for
            single-epoch verification where we trust the stored value).

    Returns:
        ``None`` if the batch is valid, otherwise a tuple of
        ``(status, broken_sequence, entries_checked, reason)``.
    """
    prev_hash = expected_prev_hash

    for i, entry in enumerate(entries):
        seq = entry.get("sequence")

        # Check sequence continuity
        expected_seq = expected_start + i
        if seq != expected_seq:
            return (ChainStatus.GAP_DETECTED, expected_seq, i, BrokenReason.SEQUENCE_GAP)

        # Check hash integrity
        entry_prev_hash = entry.get("previous_hash")
        if not skip_first_prev_check or i > 0:
            if entry_prev_hash != prev_hash:
                return (ChainStatus.BROKEN, seq, i, BrokenReason.HASH_MISMATCH)

        recomputed = compute_entry_hash(entry, entry_prev_hash)
        stored_hash = entry.get("hash")
        if recomputed != stored_hash:
            return (ChainStatus.BROKEN, seq, i, BrokenReason.HASH_MISMATCH)

        prev_hash = stored_hash

    return None


async def get_chain_status(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> ChainStatusInfo:
    """Query the current chain status for display.

    Args:
        db: Tenant database handle.

    Returns:
        ChainStatusInfo with current chain statistics.

    Raises:
        ChainNotInitializedError: If no genesis entry exists.
    """
    genesis = await get_genesis_entry(db)
    if genesis is None:
        raise ChainNotInitializedError("Chain has not been initialized — no genesis entry")

    latest = await get_latest_chained_entry(db)
    total = await count_chained_entries(db)
    last_verification = await get_last_verification(db)

    return ChainStatusInfo(
        total_entries=total,
        current_epoch=latest["epoch"] if latest else 0,
        current_sequence=latest["sequence"] if latest else 0,
        genesis_hash=genesis.get("hash", ""),
        latest_hash=latest.get("hash", "") if latest else genesis.get("hash", ""),
        chain_valid=last_verification.get("chain_valid") if last_verification else None,
        last_verified_at=last_verification.get("verified_at") if last_verification else None,
    )


async def list_epochs(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[EpochSummary]:
    """List all completed epochs with summary information.

    Args:
        db: Tenant database handle.

    Returns:
        Ordered list of EpochSummary for each completed epoch.
    """
    completed = await get_completed_epochs(db)
    exported = await get_exported_epochs(db)
    epoch_size = await get_epoch_size(db)

    summaries: list[EpochSummary] = []
    for epoch_end in completed:
        epoch_num = epoch_end["epoch"]
        first_entry = await get_epoch_boundary_entry(db, epoch_num, last=False)
        if first_entry is None:
            continue

        summaries.append(
            EpochSummary(
                epoch=epoch_num,
                first_sequence=first_entry["sequence"],
                last_sequence=epoch_end["sequence"],
                entry_count=epoch_end["sequence"] - first_entry["sequence"] + 1,
                first_timestamp=first_entry["timestamp"],
                last_timestamp=epoch_end["timestamp"],
                epoch_final_hash=epoch_end.get("hash", ""),
                previous_epoch_hash=first_entry.get("previous_epoch_hash"),
                exported=epoch_num in exported,
            )
        )

    return summaries


async def export_epoch(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    epoch: int,
    *,
    exported_by: str = "system",
    tenant_id: str | None = None,
    tenant_name: str | None = None,
    sentora_version: str = "1.1.0",
) -> EpochExport:
    """Export a completed epoch as a self-contained, verifiable archive.

    The export includes all entries and metadata needed for air-gapped
    verification.  An ``export_hash`` binds the metadata to the entries.

    Args:
        db: Tenant database handle.
        epoch: Epoch number to export.
        exported_by: Username of the exporter.
        tenant_id: Tenant identifier.
        tenant_name: Human-readable tenant name.
        sentora_version: Application version string.

    Returns:
        EpochExport with metadata and entries.

    Raises:
        EpochNotFoundError: If the epoch does not exist.
        EpochNotCompleteError: If the epoch is not yet complete.
    """
    entries = await stream_entries_for_epoch(db, epoch)
    if not entries:
        raise EpochNotFoundError(
            f"Epoch {epoch} not found",
            detail={"epoch": epoch},
        )

    last_entry = entries[-1]
    if not last_entry.get("is_epoch_end"):
        # Check if this is the current (incomplete) epoch
        latest = await get_latest_chained_entry(db)
        if latest and latest["epoch"] == epoch:
            raise EpochNotCompleteError(
                f"Epoch {epoch} is still in progress",
                detail={"epoch": epoch, "entries_so_far": len(entries)},
            )

    first_entry = entries[0]
    epoch_size = await get_epoch_size(db)

    # Compute export integrity hash
    export_hash = compute_export_hash(entries)

    metadata = {
        "sentora_version": sentora_version,
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "epoch": epoch,
        "epoch_size": epoch_size,
        "first_sequence": first_entry["sequence"],
        "last_sequence": last_entry["sequence"],
        "first_timestamp": first_entry["timestamp"].isoformat()
        if hasattr(first_entry["timestamp"], "isoformat")
        else str(first_entry["timestamp"]),
        "last_timestamp": last_entry["timestamp"].isoformat()
        if hasattr(last_entry["timestamp"], "isoformat")
        else str(last_entry["timestamp"]),
        "entry_count": len(entries),
        "previous_epoch_hash": first_entry.get("previous_epoch_hash"),
        "epoch_final_hash": last_entry.get("hash", ""),
        "exported_at": utc_now().isoformat(),
        "exported_by": exported_by,
        "chain_algorithm": CHAIN_ALGORITHM,
        "export_hash": export_hash,
    }

    # Serialise timestamps in entries for JSON export
    serialised_entries = []
    for entry in entries:
        e = dict(entry)
        if hasattr(e.get("timestamp"), "isoformat"):
            e["timestamp"] = e["timestamp"].isoformat()
        serialised_entries.append(e)

    # Record the export
    await mark_epoch_exported(db, epoch)

    return EpochExport(metadata=metadata, entries=serialised_entries)
