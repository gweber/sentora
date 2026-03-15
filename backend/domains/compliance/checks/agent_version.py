"""Check: SentinelOne agent version currency.

Compares each scoped agent's ``agent_version`` against either a
configured ``min_version`` parameter or the most common version
across the fleet (if no minimum is specified).
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import not_applicable_result
from domains.compliance.entities import CheckResult, CheckStatus, ComplianceViolation, ControlSeverity
from utils.dt import utc_now


def _version_tuple(version: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable tuple.

    Non-numeric segments are treated as 0.

    Args:
        version: Dotted version string (e.g. ``23.1.4.12345``).

    Returns:
        Tuple of integers for comparison.
    """
    parts: list[int] = []
    for segment in version.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


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
    """Identify agents running outdated SentinelOne agent versions.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: Optional ``min_version`` string.  If absent, the
            most common version in the fleet is used as the baseline.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for each outdated agent.
    """
    now = utc_now()
    total_agents = await db["s1_agents"].count_documents(scope_filter or {})

    if total_agents == 0:
        return not_applicable_result(
            control_id=control_id, framework_id=framework_id,
            control_name=control_name, category=category,
            severity=severity, checked_at=now,
        )

    min_version_str: str | None = parameters.get("min_version")

    if not min_version_str:
        # Determine the most common agent version as the baseline
        pipeline: list[dict[str, Any]] = []
        if scope_filter:
            pipeline.append({"$match": scope_filter})
        pipeline.extend([
            {"$group": {"_id": "$agent_version", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 1},
        ])
        cursor = db["s1_agents"].aggregate(pipeline)
        top = await cursor.to_list(length=1)
        if top and top[0]["_id"]:
            min_version_str = top[0]["_id"]
        else:
            return CheckResult(
                control_id=control_id,
                framework_id=framework_id,
                status=CheckStatus.warning,
                checked_at=now,
                total_endpoints=total_agents,
                compliant_endpoints=0,
                non_compliant_endpoints=0,
                violations=[],
                evidence_summary="Could not determine baseline agent version",
                severity=ControlSeverity(severity),
                category=category,
                control_name=control_name,
            )

    min_version = _version_tuple(min_version_str)
    violations: list[ComplianceViolation] = []

    projection = {"s1_agent_id": 1, "hostname": 1, "agent_version": 1}
    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        agent_version_str = agent.get("agent_version", "")
        if not agent_version_str:
            continue
        if _version_tuple(agent_version_str) < min_version:
            violations.append(
                ComplianceViolation(
                    agent_id=agent["s1_agent_id"],
                    agent_hostname=agent.get("hostname", "unknown"),
                    violation_detail=(
                        f"Agent version {agent_version_str} is below "
                        f"minimum {min_version_str}"
                    ),
                    remediation=(
                        f"Update SentinelOne agent on {agent.get('hostname', 'unknown')} "
                        f"from {agent_version_str} to {min_version_str} or later"
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
            f"{compliant}/{total_agents} agents at version {min_version_str} or later. "
            f"{non_compliant} agent(s) outdated."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
