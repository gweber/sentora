"""Check: classification coverage threshold.

Verifies that a sufficient percentage of installed applications have
been classified (not left as ``unclassified``).
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
from domains.sources.collections import AGENTS
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
    """Evaluate application classification coverage.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: ``min_classified_percent`` (default 90).
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult indicating coverage level.
    """
    now = utc_now()
    min_classified_pct: float = parameters.get("min_classified_percent", 90)

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

    # Resolve scoped agent IDs, then count classification results by agent_id.
    # classification_results uses agent_id (not tags/group_name), so we cannot
    # apply scope_filter directly — we must join via agents first.
    scoped_agent_ids: list[str] = []
    async for doc in db[AGENTS].find(scope_filter or {}, {"source_id": 1}):
        scoped_agent_ids.append(doc["source_id"])

    classified_count = await db["classification_results"].count_documents(
        {"agent_id": {"$in": scoped_agent_ids}} if scoped_agent_ids else {}
    )

    coverage_pct = (classified_count / total_agents * 100) if total_agents > 0 else 0
    violations: list[ComplianceViolation] = []

    if coverage_pct >= min_classified_pct:
        status = CheckStatus.passed
    elif coverage_pct >= min_classified_pct * 0.8:
        status = CheckStatus.warning
    else:
        status = CheckStatus.failed

    unclassified = total_agents - classified_count
    if unclassified > 0:
        violations.append(
            ComplianceViolation(
                agent_id="aggregate",
                agent_hostname="fleet-wide",
                violation_detail=(
                    f"{unclassified} agent(s) lack classification results "
                    f"({coverage_pct:.1f}% coverage, minimum {min_classified_pct}%)"
                ),
                remediation=("Run a classification sweep to classify unprocessed agents"),
            )
        )

    return CheckResult(
        control_id=control_id,
        framework_id=framework_id,
        status=status,
        checked_at=now,
        total_endpoints=total_agents,
        compliant_endpoints=classified_count,
        non_compliant_endpoints=unclassified,
        violations=violations,
        evidence_summary=(
            f"{classified_count}/{total_agents} agents classified "
            f"({coverage_pct:.1f}% coverage, threshold {min_classified_pct}%)"
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
