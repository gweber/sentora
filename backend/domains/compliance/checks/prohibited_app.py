"""Check: prohibited applications installed on endpoints.

Uses the ``app_summaries`` cache to identify prohibited app names, then
checks each scoped agent's ``installed_app_names`` for matches.  Avoids
the expensive ``$lookup`` join into ``installed_apps``.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import not_applicable_result
from domains.compliance.entities import (
    CheckResult,
    CheckStatus,
    ComplianceViolation,
    ControlSeverity,
)
from domains.sources.collections import AGENTS, INSTALLED_APPS
from utils.dt import utc_now


async def execute(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    control_id: str,
    framework_id: str,
    control_name: str,
    category: str,
    severity: str,
    parameters: dict[str, Any],
    scope_filter: dict[str, Any],
) -> CheckResult:
    """Find agents with prohibited applications installed.

    Two-phase approach for performance:
    1. Query ``app_summaries`` for app names with ``risk_level: "prohibited"``
    2. Iterate scoped agents and check ``installed_app_names`` for matches

    This avoids the expensive ``$lookup`` join from ``agents`` into
    ``installed_apps`` that previously scanned millions of rows.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: Not used for this check.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for each agent/app combination.
    """
    now = utc_now()

    # Count total agents in scope
    total_agents = await db[AGENTS].count_documents(scope_filter or {})
    if total_agents == 0:
        return not_applicable_result(
            control_id=control_id,
            framework_id=framework_id,
            control_name=control_name,
            category=category,
            severity=severity,
            checked_at=now,
        )

    # Phase 1: get the set of prohibited app names from the pre-computed cache.
    # app_summaries.risk_level stores the most common risk_level per app.
    # Also check installed_apps directly for any app with risk_level=prohibited
    # to catch apps where prohibited isn't the majority but still present.
    prohibited_names: set[str] = set()
    async for doc in (
        db[INSTALLED_APPS]
        .find(
            {"risk_level": "prohibited"},
            {"normalized_name": 1, "_id": 0},
        )
        .limit(10_000)
    ):
        prohibited_names.add(doc["normalized_name"])

    if not prohibited_names:
        return CheckResult(
            control_id=control_id,
            framework_id=framework_id,
            status=CheckStatus.passed,
            checked_at=now,
            total_endpoints=total_agents,
            compliant_endpoints=total_agents,
            non_compliant_endpoints=0,
            violations=[],
            evidence_summary=(
                f"{total_agents}/{total_agents} endpoints free of prohibited software."
            ),
            severity=ControlSeverity(severity),
            category=category,
            control_name=control_name,
        )

    # Phase 2: check each scoped agent's installed_app_names for matches
    prohibited_lower = {n.lower() for n in prohibited_names}
    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    agent_filter = {**(scope_filter or {}), "installed_app_names": {"$exists": True}}
    async for agent in db[AGENTS].find(
        agent_filter,
        {"source_id": 1, "hostname": 1, "installed_app_names": 1, "_id": 0},
    ):
        agent_id = agent["source_id"]
        hostname = agent.get("hostname", "unknown")
        for app_name in agent.get("installed_app_names", []):
            if app_name.lower() in prohibited_lower:
                non_compliant_agents.add(agent_id)
                violations.append(
                    ComplianceViolation(
                        agent_id=agent_id,
                        agent_hostname=hostname,
                        violation_detail=f"Prohibited application '{app_name}' installed",
                        app_name=app_name,
                        remediation=f"Uninstall '{app_name}' from endpoint {hostname}",
                    )
                )

    from .base import MAX_VIOLATIONS

    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]

    non_compliant = len(non_compliant_agents)
    compliant = total_agents - non_compliant
    status = CheckStatus.passed if non_compliant == 0 else CheckStatus.failed

    return CheckResult(
        control_id=control_id,
        framework_id=framework_id,
        status=status,
        checked_at=now,
        total_endpoints=total_agents,
        compliant_endpoints=compliant,
        non_compliant_endpoints=non_compliant,
        violations=violations,
        evidence_summary=(
            f"{compliant}/{total_agents} endpoints free of prohibited software. "
            f"{len(violations)} violation(s) found on {non_compliant} endpoint(s)."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
