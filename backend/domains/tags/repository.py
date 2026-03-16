"""Tags domain repository — all MongoDB access for tag rules."""

from __future__ import annotations

from typing import Any, Literal

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.tags.entities import TagRule, TagRulePattern
from utils.dt import utc_now

# ── Document converters ───────────────────────────────────────────────────────


def _doc_to_rule(doc: dict[str, Any]) -> TagRule:
    if "_id" in doc and not isinstance(doc["_id"], str):
        doc = {**doc, "_id": str(doc["_id"])}
    # Coerce nested pattern _id fields
    if "patterns" in doc:
        coerced: list[dict[str, Any]] = []
        for p in doc["patterns"]:
            if "_id" in p and not isinstance(p["_id"], str):
                p = {**p, "_id": str(p["_id"])}
            coerced.append(p)
        doc = {**doc, "patterns": coerced}
    return TagRule.model_validate(doc)


def _rule_to_doc(rule: TagRule) -> dict[str, Any]:
    d = rule.model_dump(by_alias=True)
    # Patterns are embedded — already serialised correctly
    return d


def _pattern_to_doc(pattern: TagRulePattern) -> dict[str, Any]:
    return pattern.model_dump(by_alias=True)


# ── CRUD ──────────────────────────────────────────────────────────────────────


async def get_by_id(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> TagRule | None:
    doc = await db["tag_rules"].find_one({"_id": rule_id})
    return _doc_to_rule(doc) if doc else None


async def get_by_tag_name(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tag_name: str,
) -> TagRule | None:
    doc = await db["tag_rules"].find_one({"tag_name": tag_name})
    return _doc_to_rule(doc) if doc else None


async def list_all(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[TagRule]:
    cursor = db["tag_rules"].find({}).sort("tag_name", 1).limit(500)
    return [_doc_to_rule(doc) async for doc in cursor]


async def create(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: TagRule,
) -> None:
    await db["tag_rules"].insert_one(_rule_to_doc(rule))


async def update(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    updates: dict[str, Any],
) -> None:
    await db["tag_rules"].update_one(
        {"_id": rule_id},
        {"$set": {**updates, "updated_at": utc_now()}},
    )


async def delete(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> None:
    await db["tag_rules"].delete_one({"_id": rule_id})


async def add_pattern(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    pattern: TagRulePattern,
) -> None:
    await db["tag_rules"].update_one(
        {"_id": rule_id},
        {
            "$push": {"patterns": _pattern_to_doc(pattern)},
            "$set": {"updated_at": utc_now()},
        },
    )


async def remove_pattern(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    pattern_id: str,
) -> None:
    await db["tag_rules"].update_one(
        {"_id": rule_id},
        {
            "$pull": {"patterns": {"_id": pattern_id}},
            "$set": {"updated_at": utc_now()},
        },
    )


async def set_apply_status(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    status: Literal["idle", "running", "done", "failed"],
    applied_count: int | None = None,
    applied_at: Any | None = None,  # noqa: ANN401
) -> None:
    fields: dict[str, Any] = {"apply_status": status}
    if applied_count is not None:
        fields["last_applied_count"] = applied_count
    if applied_at is not None:
        fields["last_applied_at"] = applied_at
    await db["tag_rules"].update_one({"_id": rule_id}, {"$set": fields})
