"""Check: custom application presence or absence.

Verifies that a specific application (by name pattern) is or is not
installed on scoped endpoints.  Configured via ``app_pattern`` and
``must_exist`` parameters.
"""

from __future__ import annotations

import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import not_applicable_result
from domains.compliance.entities import (
    CheckResult,
    CheckStatus,
    ComplianceViolation,
    ControlSeverity,
)
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
    """Check for presence or absence of a specific application.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: ``app_pattern`` (required) — glob-style pattern for
            the application name.  ``must_exist`` (default True) — if
            True, the app must be present; if False, it must be absent.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for non-compliant endpoints.
    """
    now = utc_now()
    app_pattern: str = parameters.get("app_pattern", "")
    must_exist: bool = parameters.get("must_exist", True)

    if not app_pattern:
        return CheckResult(
            control_id=control_id,
            framework_id=framework_id,
            status=CheckStatus.error,
            checked_at=now,
            total_endpoints=0,
            compliant_endpoints=0,
            non_compliant_endpoints=0,
            violations=[],
            evidence_summary="No app_pattern configured for this control",
            severity=ControlSeverity(severity),
            category=category,
            control_name=control_name,
        )

    total_agents = await db["s1_agents"].count_documents(scope_filter or {})
    if total_agents == 0:
        return not_applicable_result(
            control_id=control_id,
            framework_id=framework_id,
            control_name=control_name,
            category=category,
            severity=severity,
            checked_at=now,
        )

    # Convert glob-style pattern to regex (simple * → .*)
    regex_pattern = re.escape(app_pattern).replace(r"\*", ".*")
    compiled = re.compile(regex_pattern, re.IGNORECASE)

    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    projection = {"s1_agent_id": 1, "hostname": 1, "installed_app_names": 1}
    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        installed = agent.get("installed_app_names", [])
        found = any(compiled.search(name) for name in installed)
        agent_id = agent["s1_agent_id"]
        hostname = agent.get("hostname", "unknown")

        if must_exist and not found:
            non_compliant_agents.add(agent_id)
            violations.append(
                ComplianceViolation(
                    agent_id=agent_id,
                    agent_hostname=hostname,
                    violation_detail=(f"Required application matching '{app_pattern}' not found"),
                    app_name=app_pattern,
                    remediation=f"Install an application matching '{app_pattern}' on {hostname}",
                )
            )
        elif not must_exist and found:
            matching = [name for name in installed if compiled.search(name)]
            non_compliant_agents.add(agent_id)
            for match_name in matching:
                violations.append(
                    ComplianceViolation(
                        agent_id=agent_id,
                        agent_hostname=hostname,
                        violation_detail=(
                            f"Disallowed application '{match_name}' found "
                            f"(matches pattern '{app_pattern}')"
                        ),
                        app_name=match_name,
                        remediation=f"Remove '{match_name}' from {hostname}",
                    )
                )

    from .base import MAX_VIOLATIONS

    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]

    non_compliant = len(non_compliant_agents)
    compliant = total_agents - non_compliant
    status = CheckStatus.passed if non_compliant == 0 else CheckStatus.failed
    action = "present" if must_exist else "absent"

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
            f"{compliant}/{total_agents} endpoints: '{app_pattern}' is {action}. "
            f"{non_compliant} non-compliant endpoint(s)."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
