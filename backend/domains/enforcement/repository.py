"""Enforcement repository — MongoDB data access layer.

Collections used:
- ``enforcement_rules`` — rule definitions
- ``enforcement_results`` — check result history (TTL 90 days)
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.enforcement.entities import (
    CheckStatus,
    EnforcementResult,
    EnforcementRule,
    EnforcementViolation,
    RuleType,
    Severity,
)
from utils.dt import utc_now


# ---------------------------------------------------------------------------
# Rules CRUD
# ---------------------------------------------------------------------------


async def list_rules(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    enabled_only: bool = False,
) -> list[EnforcementRule]:
    """List all enforcement rules.

    Args:
        db: Motor database handle.
        enabled_only: If True, return only enabled rules.

    Returns:
        List of enforcement rules, newest first.

    Reads from the ``enforcement_rules`` collection.
    """
    query: dict[str, Any] = {}
    if enabled_only:
        query["enabled"] = True

    rules: list[EnforcementRule] = []
    async for doc in db["enforcement_rules"].find(query).sort("created_at", -1):
        rules.append(_doc_to_rule(doc))
    return rules


async def get_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> EnforcementRule | None:
    """Get a single rule by ID.

    Args:
        db: Motor database handle.
        rule_id: The rule identifier (ObjectId string).

    Returns:
        The rule, or None if not found.

    Reads from the ``enforcement_rules`` collection.
    """
    try:
        oid = ObjectId(rule_id)
    except (InvalidId, TypeError):
        return None
    doc = await db["enforcement_rules"].find_one({"_id": oid})
    if doc is None:
        return None
    return _doc_to_rule(doc)


async def insert_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: EnforcementRule,
) -> str:
    """Insert a new enforcement rule.

    Args:
        db: Motor database handle.
        rule: The rule to insert.

    Returns:
        The generated rule ID string.

    Writes to the ``enforcement_rules`` collection.
    """
    doc = _rule_to_doc(rule)
    result = await db["enforcement_rules"].insert_one(doc)
    return str(result.inserted_id)


async def update_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    updates: dict[str, Any],
) -> bool:
    """Update fields on an existing rule.

    Args:
        db: Motor database handle.
        rule_id: The rule to update.
        updates: Dict of field name → new value.

    Returns:
        True if the rule was found and updated.

    Writes to the ``enforcement_rules`` collection.
    """
    try:
        oid = ObjectId(rule_id)
    except (InvalidId, TypeError):
        return False
    updates["updated_at"] = utc_now()
    result = await db["enforcement_rules"].update_one(
        {"_id": oid}, {"$set": updates}
    )
    return result.matched_count > 0


async def delete_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> bool:
    """Delete a rule by ID.

    Args:
        db: Motor database handle.
        rule_id: The rule to delete.

    Returns:
        True if the rule was found and deleted.

    Writes to the ``enforcement_rules`` collection.
    """
    try:
        oid = ObjectId(rule_id)
    except (InvalidId, TypeError):
        return False
    result = await db["enforcement_rules"].delete_one({"_id": oid})
    return result.deleted_count > 0


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


async def store_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    run_id: str,
    results: list[EnforcementResult],
) -> None:
    """Persist enforcement check results.

    Args:
        db: Motor database handle.
        run_id: Unique run identifier.
        results: List of results to store.

    Writes to the ``enforcement_results`` collection.
    """
    if not results:
        return
    docs = []
    for r in results:
        docs.append({
            "run_id": run_id,
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "rule_type": r.rule_type,
            "severity": r.severity,
            "checked_at": r.checked_at,
            "status": r.status.value,
            "total_agents": r.total_agents,
            "compliant_agents": r.compliant_agents,
            "non_compliant_agents": r.non_compliant_agents,
            "violations": [asdict(v) for v in r.violations],
        })
    await db["enforcement_results"].insert_many(docs)


async def get_latest_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[dict[str, Any]]:
    """Get the most recent result for each rule.

    Args:
        db: Motor database handle.

    Returns:
        List of result documents, one per rule.

    Reads from the ``enforcement_results`` collection.
    """
    pipeline: list[dict[str, Any]] = [
        {"$sort": {"checked_at": -1}},
        {"$group": {"_id": "$rule_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"severity": 1, "rule_name": 1}},
    ]
    results: list[dict[str, Any]] = []
    async for doc in db["enforcement_results"].aggregate(pipeline):
        doc.pop("_id", None)
        results.append(doc)
    return results


async def get_rule_history(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    limit: int = 90,
) -> list[dict[str, Any]]:
    """Get historical results for a specific rule.

    Args:
        db: Motor database handle.
        rule_id: The rule to query.
        limit: Maximum entries.

    Returns:
        List of results, newest first.

    Reads from the ``enforcement_results`` collection.
    """
    cursor = (
        db["enforcement_results"]
        .find({"rule_id": rule_id}, {"violations": 0})
        .sort("checked_at", -1)
        .limit(limit)
    )
    results: list[dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        results.append(doc)
    return results


async def get_all_current_violations(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    severity: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Get all current violations with pagination.

    Args:
        db: Motor database handle.
        severity: Optional severity filter.
        page: Page number.
        page_size: Items per page.

    Returns:
        Tuple of (violations, total_count).

    Reads from the ``enforcement_results`` collection.
    """
    pipeline: list[dict[str, Any]] = [
        {"$sort": {"checked_at": -1}},
        {"$group": {"_id": "$rule_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$match": {"status": "fail"}},
    ]
    if severity:
        pipeline.append({"$match": {"severity": severity}})

    pipeline.extend([
        {"$unwind": "$violations"},
        {
            "$project": {
                "rule_id": 1,
                "rule_name": 1,
                "rule_type": 1,
                "severity": 1,
                "checked_at": 1,
                "violation": "$violations",
            }
        },
    ])

    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = await db["enforcement_results"].aggregate(count_pipeline).to_list(1)
    total = count_result[0]["total"] if count_result else 0

    skip = (page - 1) * page_size
    pipeline.extend([
        {"$sort": {"severity": 1, "checked_at": -1}},
        {"$skip": skip},
        {"$limit": page_size},
    ])

    violations: list[dict[str, Any]] = []
    async for doc in db["enforcement_results"].aggregate(pipeline):
        v = doc["violation"]
        violations.append({
            "rule_id": doc["rule_id"],
            "rule_name": doc["rule_name"],
            "rule_type": doc["rule_type"],
            "severity": doc["severity"],
            "checked_at": doc["checked_at"].isoformat() if doc.get("checked_at") else "",
            "agent_id": v.get("agent_id", ""),
            "agent_hostname": v.get("agent_hostname", ""),
            "violation_detail": v.get("violation_detail", ""),
            "app_name": v.get("app_name"),
            "app_version": v.get("app_version"),
        })

    return violations, total


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc_to_rule(doc: dict[str, Any]) -> EnforcementRule:
    """Convert a MongoDB document to an EnforcementRule entity."""
    return EnforcementRule(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description"),
        taxonomy_category_id=doc["taxonomy_category_id"],
        type=RuleType(doc["type"]),
        severity=Severity(doc["severity"]),
        enabled=doc.get("enabled", True),
        scope_groups=doc.get("scope_groups", []),
        scope_tags=doc.get("scope_tags", []),
        labels=doc.get("labels", []),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
        created_by=doc.get("created_by"),
        updated_by=doc.get("updated_by"),
    )


def _rule_to_doc(rule: EnforcementRule) -> dict[str, Any]:
    """Convert an EnforcementRule entity to a MongoDB document."""
    return {
        "name": rule.name,
        "description": rule.description,
        "taxonomy_category_id": rule.taxonomy_category_id,
        "type": rule.type.value,
        "severity": rule.severity.value,
        "enabled": rule.enabled,
        "scope_groups": rule.scope_groups,
        "scope_tags": rule.scope_tags,
        "labels": rule.labels,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "created_by": rule.created_by,
        "updated_by": rule.updated_by,
    }
