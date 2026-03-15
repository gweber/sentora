"""Check: unclassified application threshold.

Verifies that the percentage of unclassified applications on each
endpoint stays below a configurable threshold.
"""

from __future__ import annotations

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
    """Find endpoints with too many unclassified applications.

    Uses the app_summaries collection to determine classification
    status of each app, then counts per-agent unclassified totals.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: ``max_unclassified_percent`` (default 10).
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for endpoints above threshold.
    """
    now = utc_now()
    max_unclassified_pct: float = parameters.get("max_unclassified_percent", 10)

    total_agents = await db["s1_agents"].count_documents(scope_filter or {})
    if total_agents == 0:
        return not_applicable_result(
            control_id=control_id, framework_id=framework_id,
            control_name=control_name, category=category,
            severity=severity, checked_at=now,
        )

    # Get classified app names from app_summaries
    classified_apps: set[str] = set()
    async for doc in db["app_summaries"].find(
        {"category": {"$ne": None, "$ne": ""}},
        {"normalized_name": 1},
    ):
        classified_apps.add(doc["normalized_name"])

    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    projection = {"s1_agent_id": 1, "hostname": 1, "installed_app_names": 1}
    async for agent in db["s1_agents"].find(scope_filter or {}, projection):
        installed = agent.get("installed_app_names", [])
        if not installed:
            continue

        total_apps = len(installed)
        unclassified = sum(1 for app in installed if app not in classified_apps)
        unclassified_pct = (unclassified / total_apps * 100) if total_apps > 0 else 0

        if unclassified_pct > max_unclassified_pct:
            agent_id = agent["s1_agent_id"]
            non_compliant_agents.add(agent_id)
            violations.append(
                ComplianceViolation(
                    agent_id=agent_id,
                    agent_hostname=agent.get("hostname", "unknown"),
                    violation_detail=(
                        f"{unclassified}/{total_apps} apps unclassified "
                        f"({unclassified_pct:.1f}%, threshold {max_unclassified_pct}%)"
                    ),
                    remediation=(
                        "Review and classify unrecognised applications on this endpoint"
                    ),
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
            f"{compliant}/{total_agents} endpoints below {max_unclassified_pct}% "
            f"unclassified app threshold. "
            f"{non_compliant} endpoint(s) exceed threshold."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
