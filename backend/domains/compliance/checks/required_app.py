"""Check: required applications missing from endpoints.

Verifies that every scoped agent has all applications listed in the
``required_apps`` parameter installed.  Each required entry is matched
against the agent's ``installed_app_names`` using case-insensitive
substring matching.
"""

from __future__ import annotations

import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import not_applicable_result
from domains.compliance.entities import CheckResult, CheckStatus, ComplianceViolation, ControlSeverity
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
    """Find agents missing required applications.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: Must contain ``required_apps`` — a list of app name
            patterns to check for.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for each missing app per agent.
    """
    now = utc_now()
    required_apps: list[str] = parameters.get("required_apps", [])

    if not required_apps:
        return not_applicable_result(
            control_id=control_id, framework_id=framework_id,
            control_name=control_name, category=category,
            severity=severity, checked_at=now,
            evidence_summary="No required applications configured",
        )

    total_agents = await db["s1_agents"].count_documents(scope_filter or {})
    if total_agents == 0:
        return not_applicable_result(
            control_id=control_id, framework_id=framework_id,
            control_name=control_name, category=category,
            severity=severity, checked_at=now,
        )

    # Build regex patterns for each required app (case-insensitive)
    patterns = [re.compile(re.escape(app), re.IGNORECASE) for app in required_apps]

    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    projection = {"s1_agent_id": 1, "hostname": 1, "installed_app_names": 1}
    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        agent_id = agent["s1_agent_id"]
        hostname = agent.get("hostname", "unknown")
        installed = agent.get("installed_app_names", [])
        installed_lower = [name.lower() for name in installed]

        for idx, required in enumerate(required_apps):
            pattern = patterns[idx]
            found = any(pattern.search(name) for name in installed)
            if not found:
                non_compliant_agents.add(agent_id)
                violations.append(
                    ComplianceViolation(
                        agent_id=agent_id,
                        agent_hostname=hostname,
                        violation_detail=f"Required application '{required}' not found",
                        app_name=required,
                        remediation=f"Install '{required}' on endpoint {hostname}",
                    )
                )

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
            f"{compliant}/{total_agents} endpoints have all {len(required_apps)} "
            f"required application(s). {len(violations)} missing installation(s) "
            f"across {non_compliant} endpoint(s)."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
