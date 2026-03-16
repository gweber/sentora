"""MongoDB repository for audit hash-chain operations.

Handles all database interactions for sequence management, chain reads,
epoch queries, and chain metadata.  Domain logic lives in commands/queries.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

#: Default number of entries per epoch.
DEFAULT_EPOCH_SIZE = 1000

#: Batch size for streaming verification reads.
VERIFICATION_BATCH_SIZE = 1000


async def get_next_sequence(db: AsyncIOMotorDatabase) -> int:  # type: ignore[type-arg]
    """Atomically allocate the next sequence number.

    Uses ``findOneAndUpdate`` with ``$inc`` on a dedicated counter
    document in ``audit_chain_meta`` to guarantee monotonicity even
    under concurrent writes.

    Args:
        db: Tenant database handle.

    Returns:
        The next sequence number (starting from 0).
    """
    result = await db["audit_chain_meta"].find_one_and_update(
        {"_id": "sequence_counter"},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    # First call: $inc on non-existent field starts from 0 + 1 = 1.
    # We want 0-based, so the counter stores next-to-allocate and we
    # return value - 1.  But since upsert + $inc starts at 1, the
    # very first allocated sequence is 0 (value=1 → return 0).
    return result["value"] - 1


async def reset_sequence_to(db: AsyncIOMotorDatabase, value: int) -> None:  # type: ignore[type-arg]
    """Reset the sequence counter to a specific value (for retry after failed write).

    Args:
        db: Tenant database handle.
        value: The sequence value that failed — counter is reset so the
            next call to ``get_next_sequence`` returns this value.
    """
    await db["audit_chain_meta"].update_one(
        {"_id": "sequence_counter"},
        {"$set": {"value": value}},
        upsert=True,
    )


async def get_previous_hash(db: AsyncIOMotorDatabase, sequence: int) -> str | None:  # type: ignore[type-arg]
    """Fetch the hash of the entry preceding the given sequence.

    Args:
        db: Tenant database handle.
        sequence: Current entry's sequence number.

    Returns:
        Hash string of the previous entry, or ``None`` if this is the
        genesis entry (sequence 0).
    """
    if sequence == 0:
        return None
    prev = await db["audit_log"].find_one(
        {"sequence": sequence - 1},
        {"hash": 1, "_id": 0},
    )
    if prev is None:
        return None
    return prev.get("hash")


async def get_latest_chained_entry(db: AsyncIOMotorDatabase) -> dict[str, Any] | None:  # type: ignore[type-arg]
    """Fetch the most recent chained audit entry.

    Args:
        db: Tenant database handle.

    Returns:
        The entry dict with the highest sequence, or ``None`` if no
        chained entries exist.
    """
    return await db["audit_log"].find_one(
        {"sequence": {"$exists": True}},
        sort=[("sequence", -1)],
    )


async def get_genesis_entry(db: AsyncIOMotorDatabase) -> dict[str, Any] | None:  # type: ignore[type-arg]
    """Fetch the genesis entry (sequence 0).

    Args:
        db: Tenant database handle.

    Returns:
        The genesis entry dict, or ``None`` if the chain has not been
        initialised.
    """
    return await db["audit_log"].find_one({"sequence": 0})


async def count_chained_entries(db: AsyncIOMotorDatabase) -> int:  # type: ignore[type-arg]
    """Count the total number of chained audit entries.

    Args:
        db: Tenant database handle.

    Returns:
        Number of entries with a ``sequence`` field.
    """
    return await db["audit_log"].count_documents({"sequence": {"$exists": True}})


async def stream_entries_for_epoch(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    epoch: int,
) -> list[dict[str, Any]]:
    """Load all entries for a single epoch, ordered by sequence.

    Args:
        db: Tenant database handle.
        epoch: Epoch number to load.

    Returns:
        Ordered list of entry dicts.
    """
    cursor = (
        db["audit_log"]
        .find(
            {"epoch": epoch, "sequence": {"$exists": True}},
            {"_id": 0},
        )
        .sort("sequence", 1)
    )
    return [doc async for doc in cursor]


async def stream_entries_in_range(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    start_sequence: int,
    end_sequence: int,
) -> list[dict[str, Any]]:
    """Load entries in a sequence range (inclusive), ordered by sequence.

    Args:
        db: Tenant database handle.
        start_sequence: First sequence to include.
        end_sequence: Last sequence to include.

    Returns:
        Ordered list of entry dicts.
    """
    cursor = (
        db["audit_log"]
        .find(
            {
                "sequence": {"$gte": start_sequence, "$lte": end_sequence},
            },
            {"_id": 0},
        )
        .sort("sequence", 1)
    )
    return [doc async for doc in cursor]


async def mark_epoch_end(db: AsyncIOMotorDatabase, entry_id: Any) -> None:  # type: ignore[type-arg]  # noqa: ANN401
    """Set ``is_epoch_end`` on the last entry of a completed epoch.

    Args:
        db: Tenant database handle.
        entry_id: MongoDB ``_id`` of the entry to mark.
    """
    await db["audit_log"].update_one(
        {"_id": entry_id},
        {"$set": {"is_epoch_end": True}},
    )


async def get_epoch_boundary_entry(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    epoch: int,
    last: bool = True,
) -> dict[str, Any] | None:
    """Fetch the first or last entry of an epoch.

    Args:
        db: Tenant database handle.
        epoch: Epoch number.
        last: If True, return the last entry; if False, the first.

    Returns:
        Entry dict, or ``None`` if the epoch has no entries.
    """
    sort_dir = -1 if last else 1
    return await db["audit_log"].find_one(
        {"epoch": epoch, "sequence": {"$exists": True}},
        sort=[("sequence", sort_dir)],
    )


async def get_completed_epochs(db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:  # type: ignore[type-arg]
    """List all completed epochs with summary information.

    An epoch is complete when an entry with ``is_epoch_end=True`` exists.

    Args:
        db: Tenant database handle.

    Returns:
        List of dicts with epoch summary data.
    """
    pipeline = [
        {"$match": {"is_epoch_end": True, "sequence": {"$exists": True}}},
        {"$sort": {"epoch": 1}},
        {
            "$project": {
                "_id": 0,
                "epoch": 1,
                "sequence": 1,
                "hash": 1,
                "timestamp": 1,
            }
        },
    ]
    return [doc async for doc in db["audit_log"].aggregate(pipeline)]


async def save_verification_result(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    result: dict[str, Any],
) -> None:
    """Persist the latest verification result in chain metadata.

    Args:
        db: Tenant database handle.
        result: Verification result dict.
    """
    await db["audit_chain_meta"].update_one(
        {"_id": "last_verification"},
        {"$set": result},
        upsert=True,
    )


async def get_last_verification(db: AsyncIOMotorDatabase) -> dict[str, Any] | None:  # type: ignore[type-arg]
    """Fetch the most recent verification result.

    Args:
        db: Tenant database handle.

    Returns:
        Verification result dict, or ``None`` if never verified.
    """
    return await db["audit_chain_meta"].find_one({"_id": "last_verification"})


async def get_epoch_size(db: AsyncIOMotorDatabase) -> int:  # type: ignore[type-arg]
    """Read the configured epoch size from chain metadata.

    Falls back to ``DEFAULT_EPOCH_SIZE`` if not configured.

    Args:
        db: Tenant database handle.

    Returns:
        Number of entries per epoch.
    """
    meta = await db["audit_chain_meta"].find_one({"_id": "chain_config"})
    if meta and meta.get("epoch_size"):
        return meta["epoch_size"]
    return DEFAULT_EPOCH_SIZE


async def save_epoch_size(db: AsyncIOMotorDatabase, epoch_size: int) -> None:  # type: ignore[type-arg]
    """Persist the epoch size in chain metadata.

    Args:
        db: Tenant database handle.
        epoch_size: Number of entries per epoch.
    """
    await db["audit_chain_meta"].update_one(
        {"_id": "chain_config"},
        {"$set": {"epoch_size": epoch_size}},
        upsert=True,
    )


async def mark_epoch_exported(db: AsyncIOMotorDatabase, epoch: int) -> None:  # type: ignore[type-arg]
    """Record that an epoch has been exported.

    Args:
        db: Tenant database handle.
        epoch: Epoch number that was exported.
    """
    await db["audit_chain_meta"].update_one(
        {"_id": "exported_epochs"},
        {"$addToSet": {"epochs": epoch}},
        upsert=True,
    )


async def get_exported_epochs(db: AsyncIOMotorDatabase) -> set[int]:  # type: ignore[type-arg]
    """Fetch the set of epoch numbers that have been exported.

    Args:
        db: Tenant database handle.

    Returns:
        Set of exported epoch numbers.
    """
    doc = await db["audit_chain_meta"].find_one({"_id": "exported_epochs"})
    if doc and doc.get("epochs"):
        return set(doc["epochs"])
    return set()
