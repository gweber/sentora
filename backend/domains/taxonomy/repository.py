"""Taxonomy repository — MongoDB operations for taxonomy_entries and taxonomy_categories.

All database access for the taxonomy domain lives here. No business logic —
only data access patterns. Returns and accepts domain entities, not raw dicts.
"""

from __future__ import annotations

import re
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.taxonomy.entities import SoftwareEntry
from utils.dt import utc_now

COLLECTION = "taxonomy_entries"
CATEGORIES_COLLECTION = "taxonomy_categories"

# MongoDB index specifications created on first startup
_INDEXES: list[dict[str, Any]] = [
    {"key": {"category": 1}},
    {"key": {"name": 1}},
    {"key": {"name": "text", "patterns": "text"}},  # text index for search
]


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Create MongoDB indexes for the software_taxonomy collection if they don't exist.

    Args:
        db: Motor database handle.
    """
    col = db[COLLECTION]
    for spec in _INDEXES:
        await col.create_index(list(spec["key"].items()), background=True)


async def count(db: AsyncIOMotorDatabase) -> int:  # type: ignore[type-arg]
    """Return the total number of entries in the taxonomy.

    Args:
        db: Motor database handle.

    Returns:
        Total document count in the software_taxonomy collection.
    """
    return await db[COLLECTION].count_documents({})


async def get_by_id(db: AsyncIOMotorDatabase, entry_id: str) -> SoftwareEntry | None:  # type: ignore[type-arg]
    """Fetch a single taxonomy entry by its string ObjectId.

    Args:
        db: Motor database handle.
        entry_id: String representation of the MongoDB ObjectId.

    Returns:
        The SoftwareEntry if found, otherwise None.
    """
    doc = await db[COLLECTION].find_one({"_id": entry_id})
    if doc is None:
        return None
    return _doc_to_entity(doc)


async def list_all(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    skip: int = 0,
    limit: int = 500,
) -> list[SoftwareEntry]:
    """Return all taxonomy entries with optional pagination.

    Args:
        db: Motor database handle.
        skip: Number of documents to skip (for pagination).
        limit: Maximum number of documents to return.

    Returns:
        List of SoftwareEntry objects sorted by category then name.
    """
    cursor = db[COLLECTION].find({}).sort([("category", 1), ("name", 1)]).skip(skip).limit(limit)
    return [_doc_to_entity(doc) async for doc in cursor]


async def list_by_category(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    category: str,
    limit: int = 500,
) -> list[SoftwareEntry]:
    """Return entries in a given category, sorted by name.

    Args:
        db: Motor database handle.
        category: Category key (e.g. "scada_hmi").
        limit: Maximum number of entries to return (default 500).

    Returns:
        List of SoftwareEntry objects in that category.
    """
    cursor = db[COLLECTION].find({"category": category}).sort("name", 1).limit(limit)
    return [_doc_to_entity(doc) async for doc in cursor]


async def list_categories(db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:  # type: ignore[type-arg]
    """Return all categories from taxonomy_categories, joined with entry counts.

    Categories are first-class entities stored in their own collection.
    Entry counts are computed via a lookup against software_taxonomy.

    Args:
        db: Motor database handle.

    Returns:
        List of dicts with keys ``key``, ``display``, and ``entry_count``,
        sorted alphabetically by display name.
    """
    pipeline: list[dict[str, Any]] = [
        {
            "$lookup": {
                "from": COLLECTION,
                "localField": "key",
                "foreignField": "category",
                "as": "_entries",
            }
        },
        {
            "$project": {
                "_id": 0,
                "key": 1,
                "display": 1,
                "entry_count": {"$size": "$_entries"},
            }
        },
        {"$sort": {"display": 1}},
    ]
    return [doc async for doc in db[CATEGORIES_COLLECTION].aggregate(pipeline)]


async def get_category(db: AsyncIOMotorDatabase, key: str) -> dict[str, Any] | None:  # type: ignore[type-arg]
    """Fetch a single category by key.

    Args:
        db: Motor database handle.
        key: Category key string.

    Returns:
        Category document or None.
    """
    return await db[CATEGORIES_COLLECTION].find_one({"key": key})


async def insert_category(db: AsyncIOMotorDatabase, key: str, display: str) -> dict[str, Any]:  # type: ignore[type-arg]
    """Insert a new category into taxonomy_categories.

    Args:
        db: Motor database handle.
        key: Unique category key.
        display: Human-readable display label.

    Returns:
        The inserted document.
    """
    now = utc_now()
    doc = {
        "_id": str(ObjectId()),
        "key": key,
        "display": display,
        "created_at": now,
        "updated_at": now,
    }
    await db[CATEGORIES_COLLECTION].insert_one(doc)
    return doc


async def update_category_doc(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    old_key: str,
    *,
    new_key: str | None = None,
    new_display: str | None = None,
) -> bool:
    """Update a category document in taxonomy_categories.

    Args:
        db: Motor database handle.
        old_key: Current category key.
        new_key: New key, or None to keep.
        new_display: New display label, or None to keep.

    Returns:
        True if the document was updated.
    """
    patch: dict[str, Any] = {"updated_at": utc_now()}
    if new_key is not None:
        patch["key"] = new_key
    if new_display is not None:
        patch["display"] = new_display
    result = await db[CATEGORIES_COLLECTION].update_one({"key": old_key}, {"$set": patch})
    return result.modified_count > 0


async def delete_category_doc(db: AsyncIOMotorDatabase, key: str) -> bool:  # type: ignore[type-arg]
    """Delete a category document from taxonomy_categories.

    Args:
        db: Motor database handle.
        key: Category key to delete.

    Returns:
        True if the document was deleted.
    """
    result = await db[CATEGORIES_COLLECTION].delete_one({"key": key})
    return result.deleted_count > 0


async def bulk_insert_categories(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    categories: list[dict[str, Any]],
) -> int:
    """Bulk-insert category documents (used by seed).

    Args:
        db: Motor database handle.
        categories: List of category dicts with key, display, etc.

    Returns:
        Number of documents inserted.
    """
    if not categories:
        return 0
    result = await db[CATEGORIES_COLLECTION].insert_many(categories, ordered=False)
    return len(result.inserted_ids)


async def search(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    query: str,
    *,
    limit: int = 50,
) -> list[SoftwareEntry]:
    """Search taxonomy entries by name using a case-insensitive regex.

    Falls back gracefully if the text index is not yet built.

    Args:
        db: Motor database handle.
        query: Search string. Matched against the ``name`` field.
        limit: Maximum results to return.

    Returns:
        List of matching SoftwareEntry objects.
    """
    # Case-insensitive regex search on name — works without text index
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    cursor = db[COLLECTION].find({"name": pattern}).limit(limit)
    return [_doc_to_entity(doc) async for doc in cursor]


async def insert(db: AsyncIOMotorDatabase, entry: SoftwareEntry) -> SoftwareEntry:  # type: ignore[type-arg]
    """Insert a new taxonomy entry.

    Args:
        db: Motor database handle.
        entry: The SoftwareEntry to insert.

    Returns:
        The inserted SoftwareEntry (unchanged — id was set before insert).
    """
    doc = _entity_to_doc(entry)
    await db[COLLECTION].insert_one(doc)
    return entry


async def bulk_insert(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entries: list[SoftwareEntry],
    *,
    ordered: bool = False,
) -> int:
    """Bulk-insert a list of taxonomy entries.

    Uses ``ordered=False`` by default to skip duplicate key errors when
    re-seeding and continue with remaining documents.

    Args:
        db: Motor database handle.
        entries: List of SoftwareEntry objects to insert.
        ordered: If False, continue on duplicate key errors.

    Returns:
        Number of documents inserted.
    """
    if not entries:
        return 0
    docs = [_entity_to_doc(e) for e in entries]
    result = await db[COLLECTION].insert_many(docs, ordered=ordered)
    return len(result.inserted_ids)


async def update(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entry_id: str,
    updates: dict[str, Any],
) -> bool:
    """Apply a partial update to a taxonomy entry.

    Args:
        db: Motor database handle.
        entry_id: String ObjectId of the entry to update.
        updates: Dict of field names to new values (applied as ``$set``).

    Returns:
        True if a document was modified, False if the entry was not found.
    """
    updates["updated_at"] = utc_now()
    result = await db[COLLECTION].update_one(
        {"_id": entry_id},
        {"$set": updates},
    )
    return result.modified_count > 0


async def delete(db: AsyncIOMotorDatabase, entry_id: str) -> bool:  # type: ignore[type-arg]
    """Delete a taxonomy entry by ID.

    Args:
        db: Motor database handle.
        entry_id: String ObjectId of the entry to delete.

    Returns:
        True if the document was deleted, False if not found.
    """
    result = await db[COLLECTION].delete_one({"_id": entry_id})
    return result.deleted_count > 0


async def update_category(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    old_key: str,
    *,
    new_key: str | None = None,
    new_display: str | None = None,
) -> int:
    """Bulk-update all entries in a category (rename key and/or display label).

    Args:
        db: Motor database handle.
        old_key: The existing category key.
        new_key: Replacement category key, or None to leave unchanged.
        new_display: Replacement display label, or None to leave unchanged.

    Returns:
        Number of entries modified.
    """
    patch: dict[str, Any] = {"updated_at": utc_now()}
    if new_key is not None:
        patch["category"] = new_key
    if new_display is not None:
        patch["category_display"] = new_display
    result = await db[COLLECTION].update_many({"category": old_key}, {"$set": patch})
    return result.modified_count


async def delete_category(db: AsyncIOMotorDatabase, category_key: str) -> int:  # type: ignore[type-arg]
    """Delete all entries belonging to a category.

    Args:
        db: Motor database handle.
        category_key: The category key whose entries should be removed.

    Returns:
        Number of entries deleted.
    """
    result = await db[COLLECTION].delete_many({"category": category_key})
    return result.deleted_count


# ── Internal helpers ──────────────────────────────────────────────────────────


def _doc_to_entity(doc: dict[str, Any]) -> SoftwareEntry:
    """Convert a raw MongoDB document to a SoftwareEntry entity.

    Args:
        doc: Raw document dict from Motor (``_id`` is a string).

    Returns:
        A SoftwareEntry instance.
    """
    return SoftwareEntry.model_validate(doc)


def _entity_to_doc(entry: SoftwareEntry) -> dict[str, Any]:
    """Serialise a SoftwareEntry to a MongoDB-ready dict.

    Uses the ``_id`` alias so Motor stores the correct key.

    Args:
        entry: The SoftwareEntry to serialise.

    Returns:
        Dict suitable for insertion into MongoDB.
    """
    return entry.model_dump(by_alias=True)
