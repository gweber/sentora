"""Command handlers for audit hash-chain write operations.

Follows CQRS: commands mutate state, queries read state.  Each command
is a single async function that orchestrates domain logic and repository
calls.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.chain.hasher import CHAIN_ALGORITHM, compute_entry_hash
from audit.chain.repository import (
    DEFAULT_EPOCH_SIZE,
    get_epoch_boundary_entry,
    get_epoch_size,
    get_next_sequence,
    get_previous_hash,
    mark_epoch_end,
    reset_sequence_to,
    save_epoch_size,
)
from utils.dt import utc_now


async def initialize_chain(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    tenant_id: str | None = None,
    initialized_by: str = "system",
    epoch_size: int = DEFAULT_EPOCH_SIZE,
    sentora_version: str = "1.1.0",
) -> dict[str, Any]:
    """Create the genesis entry that anchors the hash-chain.

    The genesis entry has ``sequence=0``, ``epoch=0``, and
    ``previous_hash=None``.  It is the trust anchor for the entire
    chain — all subsequent hashes derive from it transitively.

    This function is idempotent: if a genesis entry already exists,
    it returns the existing one without modification.

    Args:
        db: Tenant database handle.
        tenant_id: Tenant identifier (``None`` for on-prem).
        initialized_by: Username or identifier of the actor.
        epoch_size: Number of entries per epoch.
        sentora_version: Application version string.

    Returns:
        The genesis entry dict (newly created or existing).
    """
    existing = await db["audit_log"].find_one({"sequence": 0})
    if existing is not None:
        logger.debug("Chain already initialized — genesis entry exists")
        return existing

    await save_epoch_size(db, epoch_size)

    sequence = await get_next_sequence(db)
    # Sequence counter should give us 0 on first call
    if sequence != 0:
        # Counter was already incremented (e.g. partial init) — reset
        await reset_sequence_to(db, 0)
        sequence = 0

    now = utc_now()
    entry: dict[str, Any] = {
        "sequence": 0,
        "epoch": 0,
        "timestamp": now,
        "domain": "system",
        "action": "system.genesis",
        "actor": initialized_by,
        "status": "info",
        "summary": "Audit hash-chain initialized",
        "details": {
            "sentora_version": sentora_version,
            "tenant_id": tenant_id,
            "initialized_by": initialized_by,
            "chain_algorithm": CHAIN_ALGORITHM,
            "epoch_size": epoch_size,
        },
        "tenant_id": tenant_id,
        "previous_hash": None,
        "is_epoch_start": True,
        "is_epoch_end": False,
        "previous_epoch_hash": None,
    }

    entry["hash"] = compute_entry_hash(entry, None)
    await db["audit_log"].insert_one(entry)
    entry.pop("_id", None)

    logger.info("Audit hash-chain initialized (genesis hash={})", entry["hash"][:16])
    return entry


async def append_chained_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    domain: str,
    action: str,
    actor: str = "system",
    status: str = "success",
    summary: str,
    details: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Append a new entry to the hash-chain.

    Atomically allocates a sequence number, computes the chain hash,
    checks for epoch boundaries, and inserts the entry.  On write
    failure, retries once with the same sequence to prevent gaps.

    Args:
        db: Tenant database handle.
        domain: Functional area.
        action: Specific event identifier.
        actor: Who initiated the action.
        status: Outcome (``"success"``, ``"failure"``, ``"info"``).
        summary: Human-readable description.
        details: Optional structured metadata.
        tenant_id: Tenant identifier.

    Returns:
        The inserted entry dict (without MongoDB ``_id``).

    Raises:
        errors.ChainIntegrityError: If the write fails after retry.
    """
    epoch_size = await get_epoch_size(db)
    sequence = await get_next_sequence(db)

    # Determine epoch and check for epoch boundary
    epoch = sequence // epoch_size
    prev_epoch_hash: str | None = None
    is_epoch_start = False

    if sequence > 0 and sequence % epoch_size == 0:
        # New epoch — close the previous one
        is_epoch_start = True
        prev_epoch = epoch - 1
        last_entry = await get_epoch_boundary_entry(db, prev_epoch, last=True)
        if last_entry:
            await mark_epoch_end(db, last_entry["_id"])
            prev_epoch_hash = last_entry.get("hash")

    previous_hash = await get_previous_hash(db, sequence)

    now = utc_now()
    entry: dict[str, Any] = {
        "sequence": sequence,
        "epoch": epoch,
        "timestamp": now,
        "domain": domain,
        "action": action,
        "actor": actor,
        "status": status,
        "summary": summary,
        "details": details or {},
        "tenant_id": tenant_id,
        "previous_hash": previous_hash,
        "is_epoch_start": is_epoch_start,
        "is_epoch_end": False,
        "previous_epoch_hash": prev_epoch_hash,
    }

    entry["hash"] = compute_entry_hash(entry, previous_hash)

    # Attempt insert with one retry on failure to prevent sequence gaps
    for attempt in range(2):
        try:
            await db["audit_log"].insert_one(entry)
            entry.pop("_id", None)
            return entry
        except Exception as exc:
            if attempt == 0:
                logger.warning(
                    "Chain entry write failed (seq={}), retrying: {}",
                    sequence,
                    exc,
                )
                entry.pop("_id", None)
                continue
            # Second attempt failed — log gap event
            from errors import ChainIntegrityError

            logger.error(
                "Chain entry write permanently failed (seq={}): {}",
                sequence,
                exc,
            )
            raise ChainIntegrityError(
                f"Failed to write chain entry at sequence {sequence}",
                detail={"sequence": sequence, "error": str(exc)},
            ) from exc

    # Unreachable, but keeps mypy happy
    return entry  # pragma: no cover
