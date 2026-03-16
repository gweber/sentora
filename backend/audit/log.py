"""Audit log writer.

Call ``audit()`` from any domain layer to record an event to the
``audit_log`` MongoDB collection. The function is fire-and-forget — it
never raises; errors are swallowed and logged at WARNING level so that
audit failures never break normal application flow.

On transient write failure, the entry is queued in memory and retried
by a background consumer (up to 3 attempts with exponential backoff).

When the hash-chain has been initialized (genesis entry exists), new
entries are automatically chained: each entry receives a monotonic
sequence number, an epoch assignment, and a SHA-256 hash linking it
to the previous entry.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now

#: Maximum number of entries buffered in-memory per tenant before the oldest
#: are dropped.
_MAX_QUEUE_SIZE = 500

#: Maximum retry attempts per entry.
_MAX_RETRIES = 3

# Per-tenant retry queues keyed by ``db.name``.  Each tenant gets its own
# bounded deque so that one tenant's load cannot evict another's retries
# (AUDIT-008).
_retry_queues: dict[str, deque[tuple[AsyncIOMotorDatabase, dict[str, Any], int]]] = {}

_retry_task: asyncio.Task[None] | None = None  # type: ignore[type-arg]


def _get_retry_queue(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> deque[tuple[AsyncIOMotorDatabase, dict[str, Any], int]]:
    """Return the per-tenant retry queue for *db*, creating it if needed.

    Args:
        db: Motor database handle whose ``name`` identifies the tenant.

    Returns:
        A bounded deque for this tenant.
    """
    key = db.name
    if key not in _retry_queues:
        _retry_queues[key] = deque(maxlen=_MAX_QUEUE_SIZE)
    return _retry_queues[key]


async def _drain_retry_queue() -> None:
    """Background coroutine that retries failed audit log writes.

    Iterates over all per-tenant retry queues in round-robin fashion,
    processing entries with exponential backoff.  Entries that exhaust
    all retries are dropped and logged at ERROR level.
    """
    while True:
        # Collect one entry across all tenant queues (round-robin)
        found = False
        for queue in list(_retry_queues.values()):
            if not queue:
                continue
            found = True
            db, doc, attempt = queue.popleft()
            backoff = 2**attempt
            await asyncio.sleep(backoff)

            try:
                await db["audit_log"].insert_one(doc)
                doc.pop("_id", None)
                from audit.ws import audit_ws

                await audit_ws.broadcast(doc)
                logger.debug("Audit retry succeeded on attempt {}", attempt + 1)
            except asyncio.CancelledError:
                # Re-queue so it isn't lost on shutdown, then propagate
                queue.appendleft((db, doc, attempt))
                raise
            except Exception as exc:
                if attempt + 1 < _MAX_RETRIES:
                    queue.append((db, doc, attempt + 1))
                    logger.warning(
                        "Audit retry {} failed (will retry): {}",
                        attempt + 1,
                        exc,
                    )
                else:
                    logger.error(
                        "Audit log entry permanently lost after {} attempts: action={} summary={}",
                        _MAX_RETRIES,
                        doc.get("action"),
                        doc.get("summary"),
                    )

        if not found:
            await asyncio.sleep(5)


def _ensure_retry_task() -> None:
    """Start the retry background task if it is not already running."""
    global _retry_task  # noqa: PLW0603
    if _retry_task is None or _retry_task.done():
        _retry_task = asyncio.create_task(_drain_retry_queue())


async def _is_chain_initialized(db: AsyncIOMotorDatabase) -> bool:  # type: ignore[type-arg]
    """Check if the hash-chain genesis entry exists.

    Uses a lightweight existence check on sequence 0.

    Args:
        db: Tenant database handle.

    Returns:
        True if the chain has been initialized.
    """
    genesis = await db["audit_log"].find_one(
        {"sequence": 0},
        {"_id": 1},
    )
    return genesis is not None


async def audit(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    domain: str,
    action: str,
    actor: str = "system",
    status: str = "success",
    summary: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Write a single audit log entry.

    When the hash-chain has been initialized, the entry is automatically
    chained with sequence, epoch, and hash fields.  When the chain has
    not been initialized, the entry is written as a plain audit log
    entry (backwards-compatible).

    On transient failure the entry is queued for automatic retry (up to
    3 attempts).  This function never raises — callers can treat it as
    fire-and-forget.

    Args:
        db: Motor database handle.
        domain: Functional area (e.g. "sync", "config", "fingerprint").
        action: Specific event (e.g. "sync.completed", "config.updated").
        actor: Who initiated the action — "user", "system", or "scheduler".
        status: Outcome — "success", "failure", or "info".
        summary: Human-readable one-line description.
        details: Optional structured metadata (counts, changed fields, etc.).
    """
    try:
        chain_active = await _is_chain_initialized(db)
    except Exception:
        chain_active = False

    if chain_active:
        await _write_chained(
            db,
            domain=domain,
            action=action,
            actor=actor,
            status=status,
            summary=summary,
            details=details,
        )
    else:
        await _write_plain(
            db,
            domain=domain,
            action=action,
            actor=actor,
            status=status,
            summary=summary,
            details=details,
        )


async def _write_chained(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    domain: str,
    action: str,
    actor: str,
    status: str,
    summary: str,
    details: dict[str, Any] | None,
) -> None:
    """Write a hash-chained audit entry.

    Delegates to the chain command layer for sequence allocation, epoch
    management, and hash computation.  Falls back to plain write on
    chain error to preserve fire-and-forget semantics.
    """
    try:
        from audit.chain.commands import append_chained_entry

        entry = await append_chained_entry(
            db,
            domain=domain,
            action=action,
            actor=actor,
            status=status,
            summary=summary,
            details=details,
        )
        from audit.ws import audit_ws

        await audit_ws.broadcast(entry)
    except Exception as exc:
        logger.warning("Chained audit write failed, falling back to plain write: {}", exc)
        await _write_plain(
            db,
            domain=domain,
            action=action,
            actor=actor,
            status=status,
            summary=summary,
            details=details,
        )


async def _write_plain(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    domain: str,
    action: str,
    actor: str,
    status: str,
    summary: str,
    details: dict[str, Any] | None,
) -> None:
    """Write a plain (unchained) audit entry — the original behaviour."""
    now = utc_now()
    doc: dict[str, Any] = {
        "timestamp": now,
        "actor": actor,
        "domain": domain,
        "action": action,
        "status": status,
        "summary": summary,
        "details": details or {},
    }
    try:
        await db["audit_log"].insert_one(doc)
        doc.pop("_id", None)
        from audit.ws import audit_ws

        await audit_ws.broadcast(doc)
    except Exception as exc:
        logger.warning("Audit log write failed (queuing for retry): {}", exc)
        doc.pop("_id", None)
        _get_retry_queue(db).append((db, doc, 0))
        _ensure_retry_task()
