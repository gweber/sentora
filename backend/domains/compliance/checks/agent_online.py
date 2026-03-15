"""Check: agent online status and staleness.

Identifies agents that have not checked in within a configurable
number of days, indicating potential availability or protection gaps.
"""

from __future__ import annotations

from datetime import timedelta
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
    """Find agents that have been offline beyond the allowed threshold.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: ``max_offline_days`` (default 7).
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for stale agents.
    """
    now = utc_now()
    max_offline_days: int = parameters.get("max_offline_days", 7)
    cutoff = now - timedelta(days=max_offline_days)

    total_agents = await db["s1_agents"].count_documents(scope_filter or {})
    if total_agents == 0:
        return not_applicable_result(
            control_id=control_id, framework_id=framework_id,
            control_name=control_name, category=category,
            severity=severity, checked_at=now,
        )

    # Build the stale-agent filter
    stale_filter: dict[str, Any] = {
        "last_active": {"$lt": cutoff},
    }
    if scope_filter:
        stale_filter = {"$and": [scope_filter, stale_filter]}

    violations: list[ComplianceViolation] = []
    projection = {"s1_agent_id": 1, "hostname": 1, "last_active": 1}

    async for agent in db["s1_agents"].find(stale_filter, projection):
        last_active = agent.get("last_active")
        last_active_str = last_active.isoformat() if last_active else "never"
        violations.append(
            ComplianceViolation(
                agent_id=agent["s1_agent_id"],
                agent_hostname=agent.get("hostname", "unknown"),
                violation_detail=(
                    f"Agent offline since {last_active_str} "
                    f"(>{max_offline_days} days)"
                ),
                remediation=(
                    f"Investigate endpoint {agent.get('hostname', 'unknown')} — "
                    f"last check-in {last_active_str}"
                ),
            )
        )

    non_compliant = len(violations)
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
            f"{compliant}/{total_agents} agents active within {max_offline_days} days. "
            f"{non_compliant} agent(s) stale."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
