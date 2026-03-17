"""Tags domain service — business logic for tag rules."""

from __future__ import annotations

import asyncio

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from domains.sources.collections import AGENTS, SOURCE_TAGS
from domains.tags import matcher, repository
from domains.tags.dto import (
    TagApplyResponse,
    TagPatternCreateRequest,
    TagPreviewResponse,
    TagRuleCreateRequest,
    TagRulePatternResponse,
    TagRuleResponse,
    TagRuleUpdateRequest,
)
from domains.tags.entities import TagRule, TagRulePattern
from errors import TagPatternNotFoundError, TagRuleAlreadyExistsError, TagRuleNotFoundError
from utils.dt import utc_now

# ── Converters ────────────────────────────────────────────────────────────────


def _pattern_to_response(p: TagRulePattern) -> TagRulePatternResponse:
    return TagRulePatternResponse(
        id=p.id,
        pattern=p.pattern,
        display_name=p.display_name,
        category=p.category,
        source=p.source,
        added_at=p.added_at.isoformat(),
        added_by=p.added_by,
    )


def _rule_to_response(rule: TagRule) -> TagRuleResponse:
    return TagRuleResponse(
        id=rule.id,
        tag_name=rule.tag_name,
        description=rule.description,
        patterns=[_pattern_to_response(p) for p in rule.patterns],
        apply_status=rule.apply_status,
        last_applied_at=rule.last_applied_at.isoformat() if rule.last_applied_at else None,
        last_applied_count=rule.last_applied_count,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
        created_by=rule.created_by,
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────


async def list_rules(db: AsyncIOMotorDatabase) -> list[TagRuleResponse]:  # type: ignore[type-arg]
    rules = await repository.list_all(db)
    return [_rule_to_response(r) for r in rules]


async def get_rule(db: AsyncIOMotorDatabase, rule_id: str) -> TagRuleResponse:  # type: ignore[type-arg]
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")
    return _rule_to_response(rule)


async def create_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    req: TagRuleCreateRequest,
) -> TagRuleResponse:
    existing = await repository.get_by_tag_name(db, req.tag_name)
    if existing is not None:
        raise TagRuleAlreadyExistsError(f"A tag rule for tag '{req.tag_name}' already exists")
    rule = TagRule(tag_name=req.tag_name, description=req.description)
    await repository.create(db, rule)
    await audit(
        db,
        domain="tags",
        action="tags.rule.created",
        summary=f"Tag rule '{req.tag_name}' created",
        details={"rule_id": rule.id, "tag_name": req.tag_name},
    )
    return _rule_to_response(rule)


async def update_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    req: TagRuleUpdateRequest,
) -> TagRuleResponse:
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")

    updates: dict = {}
    if req.tag_name is not None and req.tag_name != rule.tag_name:
        existing = await repository.get_by_tag_name(db, req.tag_name)
        if existing is not None and existing.id != rule_id:
            raise TagRuleAlreadyExistsError(f"A tag rule for tag '{req.tag_name}' already exists")
        updates["tag_name"] = req.tag_name
    if req.description is not None:
        updates["description"] = req.description

    if updates:
        await repository.update(db, rule_id, updates)
        await audit(
            db,
            domain="tags",
            action="tags.rule.updated",
            summary=f"Tag rule '{rule.tag_name}' updated",
            details={"rule_id": rule_id, "fields": list(updates.keys())},
        )

    updated = await repository.get_by_id(db, rule_id)
    return _rule_to_response(updated)  # type: ignore[arg-type]


async def delete_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> None:
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")
    await repository.delete(db, rule_id)
    await audit(
        db,
        domain="tags",
        action="tags.rule.deleted",
        summary=f"Tag rule '{rule.tag_name}' deleted",
        details={"rule_id": rule_id, "tag_name": rule.tag_name},
    )


async def add_pattern(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    req: TagPatternCreateRequest,
) -> TagRulePatternResponse:
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")
    pattern = TagRulePattern(
        pattern=req.pattern,
        display_name=req.display_name,
        category=req.category,
        source=req.source,
    )
    await repository.add_pattern(db, rule_id, pattern)
    await audit(
        db,
        domain="tags",
        action="tags.pattern.added",
        summary=f"Pattern '{req.pattern}' added to tag rule '{rule.tag_name}'",
        details={"rule_id": rule_id, "pattern": req.pattern},
    )
    return _pattern_to_response(pattern)


async def remove_pattern(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    pattern_id: str,
) -> None:
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")
    pattern = next((p for p in rule.patterns if p.id == pattern_id), None)
    if pattern is None:
        raise TagPatternNotFoundError(f"Pattern '{pattern_id}' not found in tag rule '{rule_id}'")
    await repository.remove_pattern(db, rule_id, pattern_id)
    await audit(
        db,
        domain="tags",
        action="tags.pattern.removed",
        summary=f"Pattern '{pattern.pattern}' removed from tag rule '{rule.tag_name}'",
        details={"rule_id": rule_id, "pattern_id": pattern_id},
    )


# ── Actions ───────────────────────────────────────────────────────────────────


async def preview_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> TagPreviewResponse:
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")
    agents, total = await matcher.find_matching_agents(db, rule)
    return TagPreviewResponse(
        rule_id=rule_id,
        tag_name=rule.tag_name,
        matched_count=total,
        preview_capped=total > len(agents),
        agents=agents,
    )


async def apply_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> TagApplyResponse:
    rule = await repository.get_by_id(db, rule_id)
    if rule is None:
        raise TagRuleNotFoundError(f"Tag rule '{rule_id}' not found")
    # Atomic guard: only proceed if not already running
    result = await db["tag_rules"].find_one_and_update(
        {"_id": rule_id, "apply_status": {"$ne": "running"}},
        {"$set": {"apply_status": "running"}},
    )
    if not result:
        return TagApplyResponse(status="already_running", rule_id=rule_id)
    asyncio.create_task(_run_apply(db, rule))
    return TagApplyResponse(status="started", rule_id=rule_id)


async def _run_apply(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: TagRule,
) -> None:
    from config import get_settings
    from domains.sync.s1_client import S1Client

    settings = get_settings()
    try:
        agents, total = await matcher.find_matching_agents(db, rule, cap=None)
        s1_ids = [a.source_id for a in agents]

        if not s1_ids:
            await repository.set_apply_status(
                db, rule.id, "done", applied_count=0, applied_at=utc_now()
            )
            await audit(
                db,
                domain="tags",
                action="tags.apply.completed",
                summary=f"Tag '{rule.tag_name}': no agents matched, nothing applied",
                details={"rule_id": rule.id, "agent_count": 0},
            )
            return

        client = S1Client(
            settings.s1_base_url,
            settings.s1_api_token,
            settings.s1_rate_limit_per_minute,
        )
        try:
            # Ensure the tag exists in the source — create it if it's a new local rule
            tag_doc = await db[SOURCE_TAGS].find_one({"name": rule.tag_name})
            if not tag_doc:
                logger.info("Tag '{}' not found in source — creating it", rule.tag_name)
                created = await client.create_tag(rule.tag_name)
                # Persist to local source_tags collection so it's visible immediately
                from domains.sync.normalizer import normalize_tag

                tag_doc = normalize_tag(created, utc_now().isoformat())
                await db[SOURCE_TAGS].update_one(
                    {"source_id": tag_doc["source_id"]},
                    {"$set": tag_doc},
                    upsert=True,
                )
                logger.info("Tag '{}' created (id={})", rule.tag_name, tag_doc["source_id"])

            tag_id = tag_doc["source_id"]
            batch_size = 100
            for i in range(0, len(s1_ids), batch_size):
                await client.tag_agents(s1_ids[i : i + batch_size], tag_id)
        finally:
            await client.close()

        # Update local agent documents so tags are visible immediately
        # (without waiting for the next full sync)
        if s1_ids:
            result = await db[AGENTS].update_many(
                {"source_id": {"$in": s1_ids}},
                {"$addToSet": {"tags": rule.tag_name}},
            )
            logger.info(
                "Updated {} local agent docs with tag '{}'",
                result.modified_count,
                rule.tag_name,
            )

        await repository.set_apply_status(
            db,
            rule.id,
            "done",
            applied_count=len(s1_ids),
            applied_at=utc_now(),
        )
        await audit(
            db,
            domain="tags",
            action="tags.apply.completed",
            summary=f"Tag '{rule.tag_name}' applied to {len(s1_ids)} agents",
            details={"rule_id": rule.id, "agent_count": len(s1_ids)},
        )
    except Exception as exc:
        logger.error("Tag apply failed for rule {}: {}", rule.id, exc)
        await repository.set_apply_status(db, rule.id, "failed")
        await audit(
            db,
            domain="tags",
            action="tags.apply.failed",
            status="failure",
            summary=f"Tag apply failed for '{rule.tag_name}': {exc}",
            details={"rule_id": rule.id, "error": str(exc)},
        )
