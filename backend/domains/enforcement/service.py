"""Enforcement service — business logic for rule CRUD and check execution.

Orchestrates between the repository, engine, audit log, and webhooks.
Handles new/resolved violation detection for webhook dispatch.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from domains.enforcement.dto import (
    CheckRunResponse,
    EnforcementResultResponse,
    EnforcementRuleResponse,
    RuleListResponse,
    SummaryResponse,
    ViolationDetailResponse,
    ViolationListResponse,
    ViolationResponse,
)
from domains.enforcement.engine import run_enforcement_checks
from domains.enforcement.entities import (
    CheckStatus,
    EnforcementResult,
    EnforcementRule,
    RuleType,
    Severity,
)
from domains.enforcement.repository import (
    delete_rule,
    get_all_current_violations,
    get_latest_results,
    get_rule,
    get_rule_history,
    insert_rule,
    list_rules,
    update_rule,
)
from utils.dt import utc_now

# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------


async def create_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    actor: str,
    name: str,
    taxonomy_category_id: str,
    rule_type: str,
    severity: str,
    description: str | None = None,
    scope_groups: list[str] | None = None,
    scope_tags: list[str] | None = None,
    labels: list[str] | None = None,
) -> EnforcementRuleResponse:
    """Create a new enforcement rule.

    Args:
        db: Motor database handle.
        actor: Username creating the rule.
        name: Rule display name.
        taxonomy_category_id: Taxonomy category key.
        rule_type: required/forbidden/allowlist.
        severity: critical/high/medium/low.
        description: Optional description.
        scope_groups: Optional group scope.
        scope_tags: Optional tag scope.
        labels: Optional framework labels.

    Returns:
        The created rule as a response DTO.

    Raises:
        InvalidTaxonomyCategoryError: If taxonomy_category_id does not
            reference an existing taxonomy category.
    """
    from errors import InvalidTaxonomyCategoryError

    # Validate taxonomy category exists
    cat = await db["taxonomy_categories"].find_one({"key": taxonomy_category_id})
    if cat is None:
        raise InvalidTaxonomyCategoryError(
            f"Taxonomy category '{taxonomy_category_id}' does not exist"
        )

    now = utc_now()
    rule = EnforcementRule(
        id="",
        name=name,
        description=description,
        taxonomy_category_id=taxonomy_category_id,
        type=RuleType(rule_type),
        severity=Severity(severity),
        scope_groups=scope_groups or [],
        scope_tags=scope_tags or [],
        labels=labels or [],
        created_at=now,
        updated_at=now,
        created_by=actor,
        updated_by=actor,
    )
    rule_id = await insert_rule(db, rule)
    rule.id = rule_id

    await audit(
        db,
        domain="enforcement",
        action="enforcement.rule.created",
        actor=actor,
        summary=f"Created enforcement rule: {name}",
        details={"rule_id": rule_id, "type": rule_type, "severity": severity},
    )

    return _rule_to_response(rule)


async def get_rule_detail(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
) -> EnforcementRuleResponse | None:
    """Get a single rule by ID.

    Args:
        db: Motor database handle.
        rule_id: The rule identifier.

    Returns:
        The rule response, or None if not found.
    """
    rule = await get_rule(db, rule_id)
    if rule is None:
        return None
    return _rule_to_response(rule)


async def list_all_rules(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> RuleListResponse:
    """List all enforcement rules.

    Args:
        db: Motor database handle.

    Returns:
        RuleListResponse with all rules.
    """
    rules = await list_rules(db)
    return RuleListResponse(
        rules=[_rule_to_response(r) for r in rules],
        total=len(rules),
    )


async def update_rule_fields(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    *,
    actor: str,
    updates: dict[str, Any],
) -> EnforcementRuleResponse | None:
    """Update fields on an existing rule.

    Validates ``type`` and ``severity`` against their respective enums
    before passing to the repository to prevent invalid values being
    written via ``$set`` (AUDIT-049).

    Args:
        db: Motor database handle.
        rule_id: The rule to update.
        actor: Username performing the update.
        updates: Field -> value mapping.

    Returns:
        Updated rule response, or None if not found.

    Raises:
        ValueError: If ``type`` or ``severity`` are not valid enum values.
    """
    # Validate enum fields before passing raw dict to $set (AUDIT-049).
    if "type" in updates:
        RuleType(updates["type"])  # raises ValueError if invalid
    if "severity" in updates:
        Severity(updates["severity"])  # raises ValueError if invalid

    updates["updated_by"] = actor
    success = await update_rule(db, rule_id, updates)
    if not success:
        return None

    await audit(
        db,
        domain="enforcement",
        action="enforcement.rule.updated",
        actor=actor,
        summary=f"Updated enforcement rule {rule_id}",
        details={"rule_id": rule_id, "fields": list(updates.keys())},
    )

    return await get_rule_detail(db, rule_id)


async def toggle_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    *,
    actor: str,
) -> EnforcementRuleResponse | None:
    """Toggle a rule's enabled state.

    Args:
        db: Motor database handle.
        rule_id: The rule to toggle.
        actor: Username performing the action.

    Returns:
        Updated rule response, or None if not found.
    """
    rule = await get_rule(db, rule_id)
    if rule is None:
        return None

    new_state = not rule.enabled
    await update_rule(db, rule_id, {"enabled": new_state, "updated_by": actor})

    await audit(
        db,
        domain="enforcement",
        action="enforcement.rule.toggled",
        actor=actor,
        summary=f"{'Enabled' if new_state else 'Disabled'} enforcement rule: {rule.name}",
        details={"rule_id": rule_id, "enabled": new_state},
    )

    return await get_rule_detail(db, rule_id)


async def remove_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    *,
    actor: str,
) -> bool:
    """Delete a rule.

    Args:
        db: Motor database handle.
        rule_id: The rule to delete.
        actor: Username performing the deletion.

    Returns:
        True if the rule was deleted.
    """
    deleted = await delete_rule(db, rule_id)
    if deleted:
        await audit(
            db,
            domain="enforcement",
            action="enforcement.rule.deleted",
            actor=actor,
            summary=f"Deleted enforcement rule {rule_id}",
        )
    return deleted


# ---------------------------------------------------------------------------
# Check execution
# ---------------------------------------------------------------------------


async def trigger_check(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    actor: str,
    rule_id: str | None = None,
) -> CheckRunResponse:
    """Trigger enforcement checks and dispatch violation webhooks.

    Args:
        db: Motor database handle.
        actor: Username triggering the run.
        rule_id: Optional single rule to check.

    Returns:
        CheckRunResponse with run summary.
    """
    # Capture previous violations for delta detection
    prev_results = await get_latest_results(db)
    prev_violation_keys: set[str] = set()
    for r in prev_results:
        for v in r.get("violations", []):
            prev_violation_keys.add(f"{r['rule_id']}:{v.get('agent_id', '')}")

    run_id, results, duration_ms = await run_enforcement_checks(db, rule_id)

    passed = sum(1 for er in results if er.status == CheckStatus.passed)
    failed = sum(1 for er in results if er.status == CheckStatus.failed)
    total_violations = sum(len(er.violations) for er in results)

    # Detect new violations
    new_violation_keys: set[str] = set()
    for er in results:
        for v in er.violations:
            key = f"{er.rule_id}:{v.agent_id}"
            new_violation_keys.add(key)

    new_violations = new_violation_keys - prev_violation_keys
    resolved_violations = prev_violation_keys - new_violation_keys

    # Dispatch webhook events for new violations
    if new_violations:
        await _dispatch_violation_webhook(db, results, new_violations, "new")
    if resolved_violations:
        await _dispatch_violation_webhook(db, results, resolved_violations, "resolved")

    await audit(
        db,
        domain="enforcement",
        action="enforcement.check.completed",
        actor=actor,
        summary=(
            f"Enforcement check {run_id}: {len(results)} rules, "
            f"{passed} pass, {failed} fail, {total_violations} violations"
        ),
        details={
            "run_id": run_id,
            "rules_evaluated": len(results),
            "duration_ms": duration_ms,
            "new_violations": len(new_violations),
            "resolved_violations": len(resolved_violations),
        },
    )

    # Dispatch enforcement.check.completed webhook
    try:
        from domains.webhooks.service import dispatch_event

        await dispatch_event(
            db,
            "enforcement.check.completed",
            {
                "run_id": run_id,
                "rules_checked": len(results),
                "rules_passed": passed,
                "rules_failed": failed,
                "total_violations": total_violations,
                "new_violations": len(new_violations),
                "resolved_violations": len(resolved_violations),
                "source": "enforcement",
            },
        )
    except Exception:
        logger.opt(exception=True).warning("Failed to dispatch enforcement.check.completed webhook")

    return CheckRunResponse(
        run_id=run_id,
        rules_evaluated=len(results),
        passed=passed,
        failed=failed,
        total_violations=total_violations,
        duration_ms=duration_ms,
    )


async def _dispatch_violation_webhook(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    results: list[EnforcementResult],
    violation_keys: set[str],
    event_type: str,
) -> None:
    """Dispatch webhook events for new or resolved violations.

    Args:
        db: Motor database handle.
        results: Current check results.
        violation_keys: Set of "rule_id:agent_id" keys.
        event_type: "new" or "resolved".
    """
    try:
        from domains.webhooks.service import dispatch_event

        # Aggregate by rule for the payload
        by_rule: dict[str, list[str]] = {}
        for key in violation_keys:
            rule_id, agent_id = key.split(":", 1)
            by_rule.setdefault(rule_id, []).append(agent_id)

        for rule_id, agent_ids in by_rule.items():
            # Find the rule result
            rule_result = next((r for r in results if r.rule_id == rule_id), None)
            rule_name = rule_result.rule_name if rule_result else rule_id
            severity = rule_result.severity if rule_result else "medium"

            # Get top 5 hostnames
            hostnames = []
            if rule_result:
                for v in rule_result.violations:
                    if v.agent_id in agent_ids and v.agent_hostname not in hostnames:
                        hostnames.append(v.agent_hostname)
                    if len(hostnames) >= 5:
                        break

            await dispatch_event(
                db,
                f"enforcement.violation.{event_type}",
                {
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "severity": severity,
                    "affected_agents": len(agent_ids),
                    "top_hostnames": hostnames,
                    "source": "enforcement",
                },
            )
    except Exception:
        logger.opt(exception=True).warning("Failed to dispatch enforcement webhook")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def get_summary(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> SummaryResponse:
    """Get aggregated enforcement summary.

    Args:
        db: Motor database handle.

    Returns:
        SummaryResponse with counts and severity breakdown.
    """
    all_rules = await list_rules(db)
    latest = await get_latest_results(db)

    passing = sum(1 for r in latest if r.get("status") == "pass")
    failing = sum(1 for r in latest if r.get("status") == "fail")

    total_violations = 0
    by_severity: dict[str, int] = {}
    last_checked: str | None = None

    for r in latest:
        v_count = len(r.get("violations", []))
        total_violations += v_count
        sev = r.get("severity", "medium")
        if r.get("status") == "fail":
            by_severity[sev] = by_severity.get(sev, 0) + v_count

        checked = r.get("checked_at")
        if checked:
            checked_str = checked.isoformat() if hasattr(checked, "isoformat") else str(checked)
            if last_checked is None or checked_str > last_checked:
                last_checked = checked_str

    return SummaryResponse(
        total_rules=len(all_rules),
        enabled_rules=sum(1 for r in all_rules if r.enabled),
        passing=passing,
        failing=failing,
        total_violations=total_violations,
        by_severity=by_severity,
        last_checked_at=last_checked,
    )


async def get_latest_rule_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[EnforcementResultResponse]:
    """Get the latest result for each rule.

    Args:
        db: Motor database handle.

    Returns:
        List of result response DTOs.
    """
    latest = await get_latest_results(db)
    return [_result_doc_to_response(r) for r in latest]


async def get_rule_result_history(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str,
    limit: int = 90,
) -> list[EnforcementResultResponse]:
    """Get historical results for a rule.

    Args:
        db: Motor database handle.
        rule_id: The rule to query.
        limit: Maximum entries.

    Returns:
        List of result DTOs, newest first.
    """
    history = await get_rule_history(db, rule_id, limit)
    return [_result_doc_to_response(r) for r in history]


async def list_current_violations(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    severity: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> ViolationListResponse:
    """Get paginated current violations.

    Args:
        db: Motor database handle.
        severity: Optional filter.
        page: Page number.
        page_size: Items per page.

    Returns:
        ViolationListResponse with paginated data.
    """
    violations, total = await get_all_current_violations(db, severity, page, page_size)
    return ViolationListResponse(
        violations=[
            ViolationDetailResponse(
                rule_id=v["rule_id"],
                rule_name=v["rule_name"],
                rule_type=v["rule_type"],
                severity=v["severity"],
                agent_id=v["agent_id"],
                agent_hostname=v["agent_hostname"],
                violation_detail=v.get("violation_detail", ""),
                app_name=v.get("app_name"),
                app_version=v.get("app_version"),
                checked_at=v.get("checked_at", ""),
            )
            for v in violations
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rule_to_response(rule: EnforcementRule) -> EnforcementRuleResponse:
    """Convert an entity to a response DTO."""
    return EnforcementRuleResponse(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        taxonomy_category_id=rule.taxonomy_category_id,
        type=rule.type.value,
        severity=rule.severity.value,
        enabled=rule.enabled,
        scope_groups=rule.scope_groups,
        scope_tags=rule.scope_tags,
        labels=rule.labels,
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
        created_by=rule.created_by,
    )


def _result_doc_to_response(doc: dict[str, Any]) -> EnforcementResultResponse:
    """Convert a result document to a response DTO."""
    checked = doc.get("checked_at")
    checked_str = (
        checked.isoformat()
        if checked is not None and hasattr(checked, "isoformat")
        else str(checked or "")
    )
    return EnforcementResultResponse(
        rule_id=doc.get("rule_id", ""),
        rule_name=doc.get("rule_name", ""),
        rule_type=doc.get("rule_type", ""),
        severity=doc.get("severity", ""),
        checked_at=checked_str,
        status=doc.get("status", ""),
        total_agents=doc.get("total_agents", 0),
        compliant_agents=doc.get("compliant_agents", 0),
        non_compliant_agents=doc.get("non_compliant_agents", 0),
        violations=[
            ViolationResponse(
                agent_id=v.get("agent_id", ""),
                agent_hostname=v.get("agent_hostname", ""),
                violation_detail=v.get("violation_detail", ""),
                app_name=v.get("app_name"),
                app_version=v.get("app_version"),
            )
            for v in doc.get("violations", [])
        ],
    )
