"""Enforcement check engine.

Evaluates enforcement rules against the agent fleet using taxonomy
pattern matching.  Uses MongoDB aggregation pipelines for performance
at 150k+ agents.
"""

from __future__ import annotations

import asyncio
import re
import time
from fnmatch import translate as fnmatch_translate
from typing import Any

from bson import ObjectId
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import MAX_VIOLATIONS
from domains.enforcement.entities import (
    CheckStatus,
    EnforcementResult,
    EnforcementRule,
    EnforcementViolation,
)
from domains.enforcement.repository import (
    list_rules,
    store_results,
)
from utils.dt import utc_now


async def _get_taxonomy_patterns(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    category_id: str,
) -> list[str]:
    """Get all glob patterns from taxonomy entries in a category.

    Includes entries from the specified category and any sub-categories
    (matched by category prefix).

    Args:
        db: Motor database handle.
        category_id: The taxonomy category key.

    Returns:
        List of glob patterns from matching taxonomy entries.
    """
    patterns: list[str] = []
    async for entry in db["taxonomy_entries"].find(
        {"category": category_id},
        {"patterns": 1},
    ):
        patterns.extend(entry.get("patterns", []))
    return patterns


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    """Compile glob patterns to case-insensitive regex objects.

    Args:
        patterns: List of glob patterns.

    Returns:
        List of compiled regex objects.
    """
    compiled: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            regex = fnmatch_translate(p)
            compiled.append(re.compile(regex, re.IGNORECASE))
        except re.error:
            logger.warning("Invalid pattern skipped: {}", p)
    return compiled


def _matches_any(app_name: str, compiled_patterns: list[re.Pattern[str]]) -> bool:
    """Check if an app name matches any compiled pattern.

    Args:
        app_name: The normalised application name.
        compiled_patterns: Pre-compiled regex patterns.

    Returns:
        True if any pattern matches.
    """
    return any(p.match(app_name) for p in compiled_patterns)


def _build_scope_filter(
    scope_groups: list[str],
    scope_tags: list[str],
) -> dict[str, Any]:
    """Build a MongoDB agent query filter from scope parameters.

    Delegates to the shared ``utils.scope.build_agent_scope_filter``.

    Args:
        scope_groups: S1 group names.
        scope_tags: Agent tags.

    Returns:
        MongoDB filter dict (empty if no scope constraints).
    """
    from utils.scope import build_agent_scope_filter

    return build_agent_scope_filter(scope_tags=scope_tags, scope_groups=scope_groups)


async def _check_required(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: EnforcementRule,
    compiled_patterns: list[re.Pattern[str]],
    scope_filter: dict[str, Any],
) -> EnforcementResult:
    """Check that every scoped agent has at least one matching app.

    Args:
        db: Motor database handle.
        rule: The enforcement rule.
        compiled_patterns: Compiled taxonomy patterns.
        scope_filter: Agent scope filter.

    Returns:
        EnforcementResult with violations for agents missing the category.
    """
    now = utc_now()
    total = await db["s1_agents"].count_documents(scope_filter or {})
    if total == 0:
        return EnforcementResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.type.value,
            severity=rule.severity.value,
            checked_at=now,
            status=CheckStatus.passed,
            total_agents=0,
            compliant_agents=0,
            non_compliant_agents=0,
            violations=[],
        )

    violations: list[EnforcementViolation] = []
    projection = {"s1_agent_id": 1, "hostname": 1, "installed_app_names": 1}

    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        installed = agent.get("installed_app_names", [])
        has_match = any(_matches_any(app, compiled_patterns) for app in installed)
        if not has_match:
            violations.append(
                EnforcementViolation(
                    agent_id=agent["s1_agent_id"],
                    agent_hostname=agent.get("hostname", "unknown"),
                    violation_detail=(
                        f"Missing: no application in category '{rule.taxonomy_category_id}'"
                    ),
                )
            )

    non_compliant = len(violations)
    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]
    return EnforcementResult(
        rule_id=rule.id,
        rule_name=rule.name,
        rule_type=rule.type.value,
        severity=rule.severity.value,
        checked_at=now,
        status=CheckStatus.passed if non_compliant == 0 else CheckStatus.failed,
        total_agents=total,
        compliant_agents=total - non_compliant,
        non_compliant_agents=non_compliant,
        violations=violations,
    )


async def _check_forbidden(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: EnforcementRule,
    compiled_patterns: list[re.Pattern[str]],
    scope_filter: dict[str, Any],
) -> EnforcementResult:
    """Check that no scoped agent has any matching app.

    Args:
        db: Motor database handle.
        rule: The enforcement rule.
        compiled_patterns: Compiled taxonomy patterns.
        scope_filter: Agent scope filter.

    Returns:
        EnforcementResult with violations for agents with forbidden apps.
    """
    now = utc_now()
    total = await db["s1_agents"].count_documents(scope_filter or {})
    if total == 0:
        return EnforcementResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.type.value,
            severity=rule.severity.value,
            checked_at=now,
            status=CheckStatus.passed,
            total_agents=0,
            compliant_agents=0,
            non_compliant_agents=0,
            violations=[],
        )

    violations: list[EnforcementViolation] = []
    projection = {"s1_agent_id": 1, "hostname": 1, "installed_app_names": 1}

    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        installed = agent.get("installed_app_names", [])
        for app in installed:
            if _matches_any(app, compiled_patterns):
                violations.append(
                    EnforcementViolation(
                        agent_id=agent["s1_agent_id"],
                        agent_hostname=agent.get("hostname", "unknown"),
                        violation_detail=(
                            f"Forbidden application '{app}' found"
                            f" (category '{rule.taxonomy_category_id}')"
                        ),
                        app_name=app,
                    )
                )

    non_compliant_agents = len({v.agent_id for v in violations})
    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]
    return EnforcementResult(
        rule_id=rule.id,
        rule_name=rule.name,
        rule_type=rule.type.value,
        severity=rule.severity.value,
        checked_at=now,
        status=CheckStatus.passed if non_compliant_agents == 0 else CheckStatus.failed,
        total_agents=total,
        compliant_agents=total - non_compliant_agents,
        non_compliant_agents=non_compliant_agents,
        violations=violations,
    )


async def _check_allowlist(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: EnforcementRule,
    compiled_patterns: list[re.Pattern[str]],
    scope_filter: dict[str, Any],
) -> EnforcementResult:
    """Check that every app on scoped agents matches the taxonomy category.

    Any installed app that does NOT match the category patterns is a violation.

    Args:
        db: Motor database handle.
        rule: The enforcement rule.
        compiled_patterns: Compiled taxonomy patterns.
        scope_filter: Agent scope filter.

    Returns:
        EnforcementResult with violations for unapproved apps.
    """
    now = utc_now()
    total = await db["s1_agents"].count_documents(scope_filter or {})
    if total == 0:
        return EnforcementResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.type.value,
            severity=rule.severity.value,
            checked_at=now,
            status=CheckStatus.passed,
            total_agents=0,
            compliant_agents=0,
            non_compliant_agents=0,
            violations=[],
        )

    violations: list[EnforcementViolation] = []
    projection = {"s1_agent_id": 1, "hostname": 1, "installed_app_names": 1}

    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        installed = agent.get("installed_app_names", [])
        for app in installed:
            if not _matches_any(app, compiled_patterns):
                violations.append(
                    EnforcementViolation(
                        agent_id=agent["s1_agent_id"],
                        agent_hostname=agent.get("hostname", "unknown"),
                        violation_detail=f"Unapproved application '{app}' not in allowlist",
                        app_name=app,
                    )
                )

    non_compliant_agents = len({v.agent_id for v in violations})
    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]
    return EnforcementResult(
        rule_id=rule.id,
        rule_name=rule.name,
        rule_type=rule.type.value,
        severity=rule.severity.value,
        checked_at=now,
        status=CheckStatus.passed if non_compliant_agents == 0 else CheckStatus.failed,
        total_agents=total,
        compliant_agents=total - non_compliant_agents,
        non_compliant_agents=non_compliant_agents,
        violations=violations,
    )


_CHECK_DISPATCH = {
    "required": _check_required,
    "forbidden": _check_forbidden,
    "allowlist": _check_allowlist,
}


async def evaluate_rule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: EnforcementRule,
) -> EnforcementResult:
    """Evaluate a single enforcement rule.

    Args:
        db: Motor database handle.
        rule: The rule to evaluate.

    Returns:
        The check result.
    """
    patterns = await _get_taxonomy_patterns(db, rule.taxonomy_category_id)
    compiled = _compile_patterns(patterns)
    scope_filter = _build_scope_filter(rule.scope_groups, rule.scope_tags)

    if not compiled:
        now = utc_now()
        return EnforcementResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.type.value,
            severity=rule.severity.value,
            checked_at=now,
            status=CheckStatus.passed,
            total_agents=0,
            compliant_agents=0,
            non_compliant_agents=0,
            violations=[
                EnforcementViolation(
                    agent_id="system",
                    agent_hostname="sentora",
                    violation_detail=(
                        f"No taxonomy patterns found for category '{rule.taxonomy_category_id}'"
                    ),
                )
            ],
        )

    check_fn = _CHECK_DISPATCH[rule.type.value]
    return await check_fn(db, rule, compiled, scope_filter)


async def run_enforcement_checks(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule_id: str | None = None,
) -> tuple[str, list[EnforcementResult], int]:
    """Run enforcement checks for all enabled rules (or a single rule).

    Args:
        db: Motor database handle.
        rule_id: Optional single rule to evaluate.

    Returns:
        Tuple of (run_id, results, duration_ms).
    """
    run_id = str(ObjectId())
    start = time.monotonic()

    if rule_id:
        from domains.enforcement.repository import get_rule

        rule = await get_rule(db, rule_id)
        rules = [rule] if rule else []
    else:
        rules = await list_rules(db, enabled_only=True)

    if not rules:
        return run_id, [], 0

    logger.info("Running enforcement checks: {} rule(s)", len(rules))

    # Evaluate all rules concurrently
    tasks = [evaluate_rule(db, rule) for rule in rules]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[EnforcementResult] = []
    for idx, result in enumerate(raw_results):
        if isinstance(result, BaseException):
            logger.error("Enforcement rule {} failed: {}", rules[idx].id, result)
            results.append(
                EnforcementResult(
                    rule_id=rules[idx].id,
                    rule_name=rules[idx].name,
                    rule_type=rules[idx].type.value,
                    severity=rules[idx].severity.value,
                    checked_at=utc_now(),
                    status=CheckStatus.failed,
                    total_agents=0,
                    compliant_agents=0,
                    non_compliant_agents=0,
                    violations=[
                        EnforcementViolation(
                            agent_id="system",
                            agent_hostname="sentora",
                            violation_detail=f"Check error: {result}",
                        )
                    ],
                )
            )
        else:
            results.append(result)

    await store_results(db, run_id, results)

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Enforcement run {} completed: {} rules in {}ms",
        run_id,
        len(results),
        duration_ms,
    )

    return run_id, results, duration_ms
