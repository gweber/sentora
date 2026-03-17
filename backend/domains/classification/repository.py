"""Classification domain repository — MongoDB operations.

All database access for classification results and runs lives here. No business
logic — only data access. Returns and accepts domain entities, not raw dicts.

Collections
-----------
``classification_results``  — One document per agent (upserted by agent_id).
``classification_runs``     — One document per pipeline execution.
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.classification.dto import ClassificationResultFilter
from domains.classification.entities import ClassificationResult, ClassificationRun
from domains.sources.collections import GROUPS

COLLECTION = "classification_results"
RUNS_COLLECTION = "classification_runs"


# ── Result operations ─────────────────────────────────────────────────────────


async def bulk_upsert_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    results: list[ClassificationResult],
) -> int:
    """Upsert multiple classification results in a single bulk_write call.

    Uses ``ReplaceOne(upsert=True, ordered=False)`` so individual document
    failures do not abort the batch — remaining operations continue and the
    caller receives an accurate success count.

    ``_id`` is intentionally excluded from replacement documents.  MongoDB
    rejects an attempt to alter ``_id`` on an existing document, so we let
    the database keep whatever ``_id`` it already assigned on the first insert.

    Args:
        db: Motor database handle.
        results: List of ClassificationResult entities to persist.

    Returns:
        Number of documents successfully written (inserted + replaced).
    """
    if not results:
        return 0

    from pymongo import ReplaceOne
    from pymongo.errors import BulkWriteError

    ops = [
        ReplaceOne(
            {"agent_id": r.agent_id},
            _result_to_doc(r),
            upsert=True,
        )
        for r in results
    ]

    try:
        res = await db[COLLECTION].bulk_write(ops, ordered=False)
        return res.modified_count + res.upserted_count
    except BulkWriteError as bwe:
        # ordered=False: some ops succeeded before the error was raised.
        # Log each failed op and return the success count so the caller
        # can accurately track progress.
        details = bwe.details
        ok = details.get("nModified", 0) + details.get("nUpserted", 0)
        for err in details.get("writeErrors", []):
            logger.warning(
                "bulk_upsert_results: doc index {} failed (code {}): {}",
                err.get("index"),
                err.get("code"),
                err.get("errmsg", ""),
            )
        return ok


async def get_by_agent_id(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    agent_id: str,
) -> ClassificationResult | None:
    """Fetch the classification result for a specific agent.

    Args:
        db: Motor database handle.
        agent_id: Agent source ID (``source_id``).

    Returns:
        The ClassificationResult entity if found, otherwise None.
    """
    doc = await db[COLLECTION].find_one({"agent_id": agent_id})
    if doc is None:
        return None
    return _doc_to_result(doc)


async def list_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    f: ClassificationResultFilter,
) -> tuple[list[ClassificationResult], int]:
    """Return a paginated, filtered list of classification results.

    Filtering supports verdict, group, hostname substring, and acknowledged
    state. Results are sorted by ``computed_at`` descending (most recent first).

    Args:
        db: Motor database handle.
        f: Filter and pagination parameters.

    Returns:
        A ``(results, total)`` tuple where ``total`` is the unfiltered count
        matching the query (for pagination).
    """
    query: dict[str, Any] = {}

    if f.classification is not None:
        query["classification"] = f.classification

    if f.group_id is not None:
        query["current_group_id"] = f.group_id

    if f.search is not None:
        query["hostname"] = {"$regex": re.escape(f.search), "$options": "i"}

    if f.acknowledged is not None:
        query["acknowledged"] = f.acknowledged

    skip = (f.page - 1) * f.limit

    total = await db[COLLECTION].count_documents(query)
    cursor = db[COLLECTION].find(query).sort("computed_at", -1).skip(skip).limit(f.limit)
    docs = await cursor.to_list(length=f.limit)
    results = [_doc_to_result(doc) for doc in docs]
    return results, total


async def acknowledge(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    agent_id: str,
) -> bool:
    """Set ``acknowledged=True`` on the result for the given agent.

    Args:
        db: Motor database handle.
        agent_id: Agent source ID.

    Returns:
        True if the document was found and updated, False otherwise.
    """
    result = await db[COLLECTION].update_one(
        {"agent_id": agent_id},
        {"$set": {"acknowledged": True}},
    )
    return result.matched_count > 0


async def get_overview(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Compute aggregate counts for the classification overview panel.

    Uses a ``$facet`` aggregation on ``classification_results`` to obtain
    verdict counts and the most recent ``computed_at`` timestamp in a single
    round-trip. A separate query to ``agents`` provides the distinct group
    count.

    Returns a dict with keys: ``total``, ``correct``, ``misclassified``,
    ``ambiguous``, ``unclassifiable``, ``groups_count``, ``last_computed_at``.

    Args:
        db: Motor database handle.

    Returns:
        Dict with overview statistics. All counts default to 0 if there are
        no documents.
    """
    pipeline: list[dict[str, Any]] = [
        {
            "$facet": {
                "by_verdict": [{"$group": {"_id": "$classification", "count": {"$sum": 1}}}],
                "latest": [
                    {"$sort": {"computed_at": -1}},
                    {"$limit": 1},
                    {"$project": {"computed_at": 1, "_id": 0}},
                ],
            }
        }
    ]

    facet_results = await db[COLLECTION].aggregate(pipeline).to_list(length=1)

    verdict_counts: dict[str, int] = {
        "correct": 0,
        "misclassified": 0,
        "ambiguous": 0,
        "unclassifiable": 0,
    }
    last_computed_at = None

    if facet_results:
        facet = facet_results[0]

        for bucket in facet.get("by_verdict", []):
            verdict = bucket.get("_id")
            if verdict in verdict_counts:
                verdict_counts[verdict] = bucket.get("count", 0)

        latest = facet.get("latest", [])
        if latest:
            last_computed_at = latest[0].get("computed_at")

    total = sum(verdict_counts.values())

    # Group count from groups collection
    try:
        groups_count = await db[GROUPS].count_documents({})
    except Exception:
        groups_count = 0

    return {
        "total": total,
        "correct": verdict_counts["correct"],
        "misclassified": verdict_counts["misclassified"],
        "ambiguous": verdict_counts["ambiguous"],
        "unclassifiable": verdict_counts["unclassifiable"],
        "groups_count": groups_count,
        "last_computed_at": last_computed_at,
    }


# ── Run operations ────────────────────────────────────────────────────────────


async def save_run(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    run: ClassificationRun,
) -> None:
    """Insert a new classification run document.

    Args:
        db: Motor database handle.
        run: The ClassificationRun entity to insert.
    """
    doc = _run_to_doc(run)
    await db[RUNS_COLLECTION].insert_one(doc)


async def update_run(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    run_id: str,
    updates: dict[str, Any],
) -> None:
    """Apply a partial update to a classification run document.

    Args:
        db: Motor database handle.
        run_id: The ``_id`` of the run to update.
        updates: Fields to set (e.g. ``{"status": "completed", "completed_at": ...}``).
    """
    await db[RUNS_COLLECTION].update_one(
        {"_id": run_id},
        {"$set": updates},
    )


async def get_latest_run(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> ClassificationRun | None:
    """Fetch the most recently started classification run.

    Args:
        db: Motor database handle.

    Returns:
        The most recent ClassificationRun entity, or None if none exist.
    """
    doc = await db[RUNS_COLLECTION].find_one({}, sort=[("started_at", -1)])
    if doc is None:
        return None
    return _doc_to_run(doc)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _doc_to_result(doc: dict[str, Any]) -> ClassificationResult:
    """Convert a raw MongoDB document to a ClassificationResult entity.

    Args:
        doc: Raw document dict from Motor.

    Returns:
        A ClassificationResult instance.
    """
    if "_id" in doc:
        doc = {**doc, "_id": str(doc["_id"])}
    return ClassificationResult.model_validate(doc)


def _result_to_doc(result: ClassificationResult) -> dict[str, Any]:
    """Serialise a ClassificationResult entity to a MongoDB-ready dict.

    ``_id`` is excluded so that ``replace_one`` / ``ReplaceOne`` never tries
    to alter the immutable ``_id`` field of an already-existing document.
    MongoDB preserves the existing ``_id`` on replace and assigns a new one
    on upsert-insert automatically.

    Args:
        result: The ClassificationResult to serialise.

    Returns:
        Dict suitable for replacement in MongoDB (no ``_id`` key).
    """
    doc = result.model_dump(by_alias=True)
    doc.pop("_id", None)
    return doc


def _doc_to_run(doc: dict[str, Any]) -> ClassificationRun:
    """Convert a raw MongoDB document to a ClassificationRun entity.

    Args:
        doc: Raw document dict from Motor.

    Returns:
        A ClassificationRun instance.
    """
    return ClassificationRun.model_validate(doc)


def _run_to_doc(run: ClassificationRun) -> dict[str, Any]:
    """Serialise a ClassificationRun entity to a MongoDB-ready dict.

    Args:
        run: The ClassificationRun to serialise.

    Returns:
        Dict suitable for insertion into MongoDB (uses ``_id`` alias).
    """
    return run.model_dump(by_alias=True)
