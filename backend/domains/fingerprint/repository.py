"""Fingerprint repository — MongoDB operations for the fingerprint domain.

All database access for fingerprints and suggestions lives here. No business
logic — only data access. Returns and accepts domain entities, not raw dicts.

Collections
-----------
``fingerprints``             — One document per group; embeds the markers array.
``fingerprint_suggestions``  — One document per suggestion; keyed by group_id.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.fingerprint.entities import (
    AutoFingerprintProposal,
    Fingerprint,
    FingerprintMarker,
    FingerprintSuggestion,
)
from utils.dt import utc_now

COLLECTION = "fingerprints"
SUGGESTIONS_COLLECTION = "fingerprint_suggestions"
PROPOSALS_COLLECTION = "auto_fingerprint_proposals"


# ── Fingerprint operations ────────────────────────────────────────────────────


async def get_by_group_id(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> Fingerprint | None:
    """Fetch the fingerprint document for a specific group.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.

    Returns:
        The Fingerprint entity if found, otherwise None.
    """
    doc = await db[COLLECTION].find_one({"group_id": group_id})
    if doc is None:
        return None
    return _doc_to_fingerprint(doc)


async def create(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    fp: Fingerprint,
) -> Fingerprint:
    """Insert a new fingerprint document.

    Args:
        db: Motor database handle.
        fp: The Fingerprint entity to insert.

    Returns:
        The inserted Fingerprint (unchanged — id was set before insert).
    """
    doc = _fingerprint_to_doc(fp)
    await db[COLLECTION].insert_one(doc)
    return fp


async def list_all(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    skip: int = 0,
    limit: int = 200,
) -> list[Fingerprint]:
    """Return fingerprint documents, sorted by group_id, with pagination.

    Args:
        db: Motor database handle.
        skip: Number of documents to skip (for pagination).
        limit: Maximum number of documents to return.

    Returns:
        List of Fingerprint entities.
    """
    cursor = db[COLLECTION].find({}).sort("group_id", 1).skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    return [_doc_to_fingerprint(doc) async for doc in cursor]


async def count_all(db: AsyncIOMotorDatabase) -> int:  # type: ignore[type-arg]
    """Return the total number of fingerprint documents.

    Args:
        db: Motor database handle.

    Returns:
        Total count of fingerprint documents.
    """
    return await db[COLLECTION].count_documents({})


async def add_marker(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    marker: FingerprintMarker,
) -> bool:
    """Append a marker to the fingerprint's markers array.

    Also touches the ``updated_at`` timestamp.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        marker: The FingerprintMarker entity to append.

    Returns:
        True if the document was modified, False if the fingerprint was not found.
    """
    marker_doc = _marker_to_doc(marker)
    result = await db[COLLECTION].update_one(
        {"group_id": group_id},
        {
            "$push": {"markers": marker_doc},
            "$set": {"updated_at": utc_now()},
        },
    )
    return result.modified_count > 0


async def update_marker(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    marker_id: str,
    updates: dict[str, object],
) -> bool:
    """Apply a partial update to a specific marker using ``arrayFilters``.

    Also touches the ``updated_at`` timestamp.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        marker_id: The ``_id`` of the marker to update.
        updates: Dict of marker fields to set (e.g. ``{"weight": 1.5}``).

    Returns:
        True if a document was modified, False if not found.
    """
    set_fields = {f"markers.$[m].{k}": v for k, v in updates.items()}
    set_fields["updated_at"] = utc_now()
    result = await db[COLLECTION].update_one(
        {"group_id": group_id},
        {"$set": set_fields},
        array_filters=[{"m._id": marker_id}],
    )
    return result.modified_count > 0


async def remove_marker(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    marker_id: str,
) -> bool:
    """Remove a marker from the fingerprint's markers array.

    Also touches the ``updated_at`` timestamp.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        marker_id: The ``_id`` of the marker to remove.

    Returns:
        True if the document was modified, False if not found.
    """
    result = await db[COLLECTION].update_one(
        {"group_id": group_id},
        {
            "$pull": {"markers": {"_id": marker_id}},
            "$set": {"updated_at": utc_now()},
        },
    )
    return result.modified_count > 0


async def reorder_markers(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    ordered_ids: list[str],
) -> bool:
    """Reorder the markers array to match the given ordered ID list.

    Fetches the current fingerprint, reorders its markers in Python to match
    ``ordered_ids``, then replaces the ``markers`` array in MongoDB with ``$set``.
    Markers whose IDs are not present in ``ordered_ids`` are appended at the end.

    Also touches the ``updated_at`` timestamp.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        ordered_ids: Complete ordered list of marker IDs.

    Returns:
        True if the document was modified, False if the fingerprint was not found.
    """
    doc = await db[COLLECTION].find_one({"group_id": group_id})
    if doc is None:
        return False

    fp = _doc_to_fingerprint(doc)
    current_marker_count = len(fp.markers)
    if current_marker_count == 0:
        return False

    # Build a lookup dict for current markers
    marker_map: dict[str, FingerprintMarker] = {m.id: m for m in fp.markers}

    # Reorder: IDs in ordered_ids first, then any extras not mentioned
    reordered: list[FingerprintMarker] = []
    for mid in ordered_ids:
        if mid in marker_map:
            reordered.append(marker_map.pop(mid))
    # Append remaining (not referenced in ordered_ids) to preserve them
    reordered.extend(marker_map.values())

    marker_docs = [_marker_to_doc(m) for m in reordered]

    # Atomic update with marker-count guard to prevent overwriting concurrent
    # marker additions.  If another request added a marker between our read
    # and this write, the marker count won't match and the update is a no-op.
    result = await db[COLLECTION].update_one(
        {
            "group_id": group_id,
            f"markers.{current_marker_count - 1}": {"$exists": True},
            f"markers.{current_marker_count}": {"$exists": False},
        },
        {"$set": {"markers": marker_docs, "updated_at": utc_now()}},
    )
    return result.modified_count > 0


async def update_updated_at(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> None:
    """Touch the fingerprint's ``updated_at`` timestamp.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
    """
    await db[COLLECTION].update_one(
        {"group_id": group_id},
        {"$set": {"updated_at": utc_now()}},
    )


# ── Suggestion operations ─────────────────────────────────────────────────────


async def save_suggestions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    suggestions: list[FingerprintSuggestion],
) -> int:
    """Replace all pending suggestions for a group with a new batch.

    Deletes existing suggestions for the group before inserting the new batch
    to avoid stale results accumulating.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        suggestions: New list of FingerprintSuggestion entities.

    Returns:
        Number of suggestions inserted.
    """
    if not suggestions:
        await db[SUGGESTIONS_COLLECTION].delete_many({"group_id": group_id, "status": "pending"})
        return 0

    # AUDIT-040: Use a generation marker to avoid a window where suggestions
    # are deleted but not yet re-inserted.  Insert new docs first with a
    # unique generation tag, then delete old pending docs that lack the tag.
    generation = str(uuid.uuid4())
    docs = [_suggestion_to_doc(s) for s in suggestions]
    for d in docs:
        d["_generation"] = generation
    await db[SUGGESTIONS_COLLECTION].insert_many(docs)
    # Delete old pending suggestions (those without this generation marker)
    await db[SUGGESTIONS_COLLECTION].delete_many(
        {"group_id": group_id, "status": "pending", "_generation": {"$ne": generation}}
    )
    return len(docs)


async def get_suggestions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> list[FingerprintSuggestion]:
    """Return all non-rejected suggestions for a group, sorted by score descending.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.

    Returns:
        List of FingerprintSuggestion entities.
    """
    cursor = (
        db[SUGGESTIONS_COLLECTION]
        .find({"group_id": group_id, "status": {"$ne": "rejected"}})
        .sort("score", -1)
        .limit(500)
    )
    return [_doc_to_suggestion(doc) async for doc in cursor]


async def get_suggestion_by_id(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    suggestion_id: str,
) -> FingerprintSuggestion | None:
    """Fetch a single suggestion by its ID within a group.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        suggestion_id: String ObjectId of the suggestion.

    Returns:
        The FingerprintSuggestion entity if found, otherwise None.
    """
    doc = await db[SUGGESTIONS_COLLECTION].find_one({"_id": suggestion_id, "group_id": group_id})
    if doc is None:
        return None
    return _doc_to_suggestion(doc)


async def update_suggestion_status(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    suggestion_id: str,
    status: Literal["pending", "accepted", "rejected"],
) -> bool:
    """Update the workflow status of a suggestion.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        suggestion_id: String ObjectId of the suggestion.
        status: New status value (``"pending"``, ``"accepted"``, or ``"rejected"``).

    Returns:
        True if the document was modified, False if not found.
    """
    result = await db[SUGGESTIONS_COLLECTION].update_one(
        {"_id": suggestion_id, "group_id": group_id},
        {"$set": {"status": status}},
    )
    return result.modified_count > 0


# ── Internal helpers ──────────────────────────────────────────────────────────


def _doc_to_fingerprint(doc: dict[str, Any]) -> Fingerprint:
    """Convert a raw MongoDB document to a Fingerprint entity.

    Args:
        doc: Raw document dict from Motor.

    Returns:
        A Fingerprint instance.
    """
    return Fingerprint.model_validate(doc)


def _fingerprint_to_doc(fp: Fingerprint) -> dict[str, Any]:
    """Serialise a Fingerprint entity to a MongoDB-ready dict.

    Args:
        fp: The Fingerprint to serialise.

    Returns:
        Dict suitable for insertion into MongoDB (uses ``_id`` alias).
    """
    return fp.model_dump(by_alias=True)


def _marker_to_doc(marker: FingerprintMarker) -> dict[str, Any]:
    """Serialise a FingerprintMarker to a MongoDB-ready dict.

    Args:
        marker: The FingerprintMarker to serialise.

    Returns:
        Dict suitable for embedding in a markers array.
    """
    return marker.model_dump(by_alias=True)


def _doc_to_suggestion(doc: dict[str, Any]) -> FingerprintSuggestion:
    """Convert a raw MongoDB document to a FingerprintSuggestion entity.

    Args:
        doc: Raw document dict from Motor.

    Returns:
        A FingerprintSuggestion instance.
    """
    return FingerprintSuggestion.model_validate(doc)


def _suggestion_to_doc(suggestion: FingerprintSuggestion) -> dict[str, Any]:
    """Serialise a FingerprintSuggestion entity to a MongoDB-ready dict.

    Args:
        suggestion: The FingerprintSuggestion to serialise.

    Returns:
        Dict suitable for insertion into MongoDB (uses ``_id`` alias).
    """
    return suggestion.model_dump(by_alias=True)


# ── Proposal operations ───────────────────────────────────────────────────────


async def save_proposals(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    proposals: list[AutoFingerprintProposal],
) -> int:
    """Upsert all proposals (replace existing on re-generate).

    Each proposal is upserted by ``group_id`` so re-generating replaces
    the previous run's results cleanly.

    Args:
        db: Motor database handle.
        proposals: List of AutoFingerprintProposal entities to persist.

    Returns:
        Number of proposals upserted.
    """
    if not proposals:
        return 0
    from pymongo import ReplaceOne

    ops = []
    for proposal in proposals:
        doc = _proposal_to_doc(proposal)
        doc.pop("_id", None)  # never include _id in replacement — MongoDB rejects it on updates
        ops.append(ReplaceOne({"group_id": proposal.group_id}, doc, upsert=True))
    await db[PROPOSALS_COLLECTION].bulk_write(ops, ordered=False)
    return len(proposals)


async def list_proposals(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    show_dismissed: bool = False,
) -> list[AutoFingerprintProposal]:
    """Return all proposals, sorted by quality_score descending.

    Args:
        db: Motor database handle.
        show_dismissed: When False (default), dismissed proposals are excluded.

    Returns:
        List of AutoFingerprintProposal entities.
    """
    query: dict[str, Any] = {} if show_dismissed else {"status": {"$ne": "dismissed"}}
    cursor = db[PROPOSALS_COLLECTION].find(query).sort("quality_score", -1).limit(1000)
    return [_doc_to_proposal(doc) async for doc in cursor]


async def get_proposal(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> AutoFingerprintProposal | None:
    """Fetch the proposal for a specific group.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.

    Returns:
        The AutoFingerprintProposal entity if found, otherwise None.
    """
    doc = await db[PROPOSALS_COLLECTION].find_one({"group_id": group_id})
    if doc is None:
        return None
    return _doc_to_proposal(doc)


async def update_proposal_status(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
    status: Literal["pending", "applied", "dismissed"],
) -> bool:
    """Update the status of a proposal.

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID.
        status: New status (``"pending"``, ``"applied"``, or ``"dismissed"``).

    Returns:
        True if the document was modified, False if not found.
    """
    result = await db[PROPOSALS_COLLECTION].update_one(
        {"group_id": group_id},
        {"$set": {"status": status}},
    )
    return result.modified_count > 0


def _doc_to_proposal(doc: dict[str, Any]) -> AutoFingerprintProposal:
    # MongoDB returns _id as a BSON ObjectId; coerce to str so Pydantic validates cleanly.
    if "_id" in doc and not isinstance(doc["_id"], str):
        doc = {**doc, "_id": str(doc["_id"])}
    return AutoFingerprintProposal.model_validate(doc)


def _proposal_to_doc(proposal: AutoFingerprintProposal) -> dict[str, Any]:
    return proposal.model_dump(by_alias=True)
