"""Library repository — MongoDB operations for library_entries, library_subscriptions,
and library_ingestion_runs collections.

All database access for the library domain lives here. Returns and accepts
domain entities, not raw dicts.
"""

from __future__ import annotations

import re
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.library.entities import (
    IngestionRun,
    LibraryEntry,
    LibrarySubscription,
)
from utils.dt import utc_now

ENTRIES_COLLECTION = "library_entries"
SUBSCRIPTIONS_COLLECTION = "library_subscriptions"
INGESTION_RUNS_COLLECTION = "library_ingestion_runs"


# ── Library entries ──────────────────────────────────────────────────────────


async def get_entry(db: AsyncIOMotorDatabase, entry_id: str) -> LibraryEntry | None:  # type: ignore[type-arg]
    doc = await db[ENTRIES_COLLECTION].find_one({"_id": entry_id})
    if doc is None:
        return None
    return LibraryEntry.model_validate(doc)


async def get_entries_by_ids(
    db: AsyncIOMotorDatabase,
    entry_ids: list[str],  # type: ignore[type-arg]
) -> list[LibraryEntry]:
    """Batch-fetch multiple library entries by their IDs in a single query."""
    if not entry_ids:
        return []
    cursor = db[ENTRIES_COLLECTION].find({"_id": {"$in": entry_ids}})
    return [LibraryEntry.model_validate(doc) async for doc in cursor]


async def get_entry_by_upstream(
    db: AsyncIOMotorDatabase,
    source: str,
    upstream_id: str,  # type: ignore[type-arg]
) -> LibraryEntry | None:
    doc = await db[ENTRIES_COLLECTION].find_one({"source": source, "upstream_id": upstream_id})
    if doc is None:
        return None
    return LibraryEntry.model_validate(doc)


async def list_entries(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    status: str | None = "published",
    source: str | None = None,
    category: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[LibraryEntry], int]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source
    if category:
        query["category"] = category
    if search:
        query["name"] = re.compile(re.escape(search), re.IGNORECASE)

    total = await db[ENTRIES_COLLECTION].count_documents(query)
    cursor = (
        db[ENTRIES_COLLECTION]
        .find(query)
        .sort([("subscriber_count", -1), ("name", 1)])
        .skip(skip)
        .limit(limit)
    )
    entries = [LibraryEntry.model_validate(doc) async for doc in cursor]
    return entries, total


async def insert_entry(db: AsyncIOMotorDatabase, entry: LibraryEntry) -> LibraryEntry:  # type: ignore[type-arg]
    doc = entry.model_dump(by_alias=True)
    await db[ENTRIES_COLLECTION].insert_one(doc)
    return entry


async def update_entry(
    db: AsyncIOMotorDatabase,
    entry_id: str,
    updates: dict[str, Any],  # type: ignore[type-arg]
) -> bool:
    updates["updated_at"] = utc_now()
    result = await db[ENTRIES_COLLECTION].update_one({"_id": entry_id}, {"$set": updates})
    return result.modified_count > 0


async def upsert_entry_by_upstream(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    source: str,
    upstream_id: str,
    entry_data: dict[str, Any],
) -> tuple[str, bool]:
    """Upsert a library entry by (source, upstream_id). Returns (entry_id, was_created)."""
    now = utc_now()
    entry_data["updated_at"] = now

    result = await db[ENTRIES_COLLECTION].update_one(
        {"source": source, "upstream_id": upstream_id},
        {
            "$set": entry_data,
            "$setOnInsert": {
                "_id": str(ObjectId()),
                "created_at": now,
                "subscriber_count": 0,
            },
            "$inc": {"version": 1},
        },
        upsert=True,
    )
    was_created = result.upserted_id is not None
    if was_created:
        entry_id = result.upserted_id
    else:
        doc = await db[ENTRIES_COLLECTION].find_one(
            {"source": source, "upstream_id": upstream_id}, {"_id": 1}
        )
        entry_id = doc["_id"] if doc else ""
    return str(entry_id), was_created


async def delete_entry(db: AsyncIOMotorDatabase, entry_id: str) -> bool:  # type: ignore[type-arg]
    result = await db[ENTRIES_COLLECTION].delete_one({"_id": entry_id})
    return result.deleted_count > 0


async def increment_subscriber_count(
    db: AsyncIOMotorDatabase,
    entry_id: str,
    delta: int,  # type: ignore[type-arg]
) -> None:
    await db[ENTRIES_COLLECTION].update_one(
        {"_id": entry_id}, {"$inc": {"subscriber_count": delta}}
    )


async def get_stats(
    library_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Get library stats. Entries from shared library_db, subscriptions from tenant_db."""
    total = await library_db[ENTRIES_COLLECTION].count_documents({})
    by_source: dict[str, int] = {}
    async for doc in library_db[ENTRIES_COLLECTION].aggregate(
        [{"$group": {"_id": "$source", "count": {"$sum": 1}}}]
    ):
        by_source[doc["_id"] or "unknown"] = doc["count"]

    by_status: dict[str, int] = {}
    async for doc in library_db[ENTRIES_COLLECTION].aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    ):
        by_status[doc["_id"] or "unknown"] = doc["count"]

    total_subs = await tenant_db[SUBSCRIPTIONS_COLLECTION].count_documents({})
    return {
        "total_entries": total,
        "by_source": by_source,
        "by_status": by_status,
        "total_subscriptions": total_subs,
    }


# ── Subscriptions ────────────────────────────────────────────────────────────


async def get_subscription(
    db: AsyncIOMotorDatabase,
    sub_id: str,  # type: ignore[type-arg]
) -> LibrarySubscription | None:
    doc = await db[SUBSCRIPTIONS_COLLECTION].find_one({"_id": sub_id})
    if doc is None:
        return None
    return LibrarySubscription.model_validate(doc)


async def get_subscription_by_group_entry(
    db: AsyncIOMotorDatabase,
    group_id: str,
    entry_id: str,  # type: ignore[type-arg]
) -> LibrarySubscription | None:
    doc = await db[SUBSCRIPTIONS_COLLECTION].find_one(
        {"group_id": group_id, "library_entry_id": entry_id}
    )
    if doc is None:
        return None
    return LibrarySubscription.model_validate(doc)


async def list_subscriptions_by_group(
    db: AsyncIOMotorDatabase,
    group_id: str,  # type: ignore[type-arg]
) -> list[LibrarySubscription]:
    cursor = db[SUBSCRIPTIONS_COLLECTION].find({"group_id": group_id})
    return [LibrarySubscription.model_validate(doc) async for doc in cursor]


async def list_subscriptions_by_entry(
    db: AsyncIOMotorDatabase,
    entry_id: str,  # type: ignore[type-arg]
) -> list[LibrarySubscription]:
    cursor = db[SUBSCRIPTIONS_COLLECTION].find({"library_entry_id": entry_id})
    return [LibrarySubscription.model_validate(doc) async for doc in cursor]


async def list_auto_update_subscriptions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[LibrarySubscription]:
    """List all subscriptions with auto_update=True.

    Staleness detection (comparing synced_version to entry version) is done
    in the service layer since entries may live in a different database.
    """
    cursor = db[SUBSCRIPTIONS_COLLECTION].find({"auto_update": True})
    return [LibrarySubscription.model_validate(doc) async for doc in cursor]


async def insert_subscription(
    db: AsyncIOMotorDatabase,
    sub: LibrarySubscription,  # type: ignore[type-arg]
) -> LibrarySubscription:
    doc = sub.model_dump(by_alias=True)
    await db[SUBSCRIPTIONS_COLLECTION].insert_one(doc)
    return sub


async def update_subscription(
    db: AsyncIOMotorDatabase,
    sub_id: str,
    updates: dict[str, Any],  # type: ignore[type-arg]
) -> bool:
    result = await db[SUBSCRIPTIONS_COLLECTION].update_one({"_id": sub_id}, {"$set": updates})
    return result.modified_count > 0


async def delete_subscription(db: AsyncIOMotorDatabase, sub_id: str) -> bool:  # type: ignore[type-arg]
    result = await db[SUBSCRIPTIONS_COLLECTION].delete_one({"_id": sub_id})
    return result.deleted_count > 0


async def delete_subscriptions_by_entry(db: AsyncIOMotorDatabase, entry_id: str) -> int:  # type: ignore[type-arg]
    result = await db[SUBSCRIPTIONS_COLLECTION].delete_many({"library_entry_id": entry_id})
    return result.deleted_count


# ── Ingestion runs ───────────────────────────────────────────────────────────


async def insert_ingestion_run(
    db: AsyncIOMotorDatabase,
    run: IngestionRun,  # type: ignore[type-arg]
) -> IngestionRun:
    doc = run.model_dump(by_alias=True)
    await db[INGESTION_RUNS_COLLECTION].insert_one(doc)
    return run


async def update_ingestion_run(
    db: AsyncIOMotorDatabase,
    run_id: str,
    updates: dict[str, Any],  # type: ignore[type-arg]
) -> bool:
    result = await db[INGESTION_RUNS_COLLECTION].update_one({"_id": run_id}, {"$set": updates})
    return result.modified_count > 0


async def list_ingestion_runs(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    source: str | None = None,
    limit: int = 20,
) -> list[IngestionRun]:
    query: dict[str, Any] = {}
    if source:
        query["source"] = source
    cursor = db[INGESTION_RUNS_COLLECTION].find(query).sort([("started_at", -1)]).limit(limit)
    return [IngestionRun.model_validate(doc) async for doc in cursor]


async def get_last_run_for_source(
    db: AsyncIOMotorDatabase,
    source: str,  # type: ignore[type-arg]
) -> IngestionRun | None:
    doc = await db[INGESTION_RUNS_COLLECTION].find_one(
        {"source": source}, sort=[("started_at", -1)]
    )
    if doc is None:
        return None
    return IngestionRun.model_validate(doc)
