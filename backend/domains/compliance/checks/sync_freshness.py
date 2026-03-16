"""Check: sync data freshness.

Verifies that the last successful data sync completed within a
configurable time window, ensuring compliance checks operate on
current data.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

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
    """Verify that data synchronisation is recent enough.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: ``max_hours_since_sync`` (default 24).
        scope_filter: Not used — this is a global check.

    Returns:
        CheckResult indicating sync freshness status.
    """
    now = utc_now()
    max_hours: int = parameters.get("max_hours_since_sync", 24)
    cutoff = now - timedelta(hours=max_hours)

    # Check the latest completed sync run
    latest_sync = await db["s1_sync_runs"].find_one(
        {"status": "completed"},
        sort=[("completed_at", -1)],
        projection={"completed_at": 1, "run_id": 1},
    )

    violations: list[ComplianceViolation] = []
    total_agents = await db["s1_agents"].count_documents(scope_filter or {})

    if latest_sync is None:
        status = CheckStatus.failed
        summary = "No completed sync runs found — data inventory not populated"
        violations.append(
            ComplianceViolation(
                agent_id="system",
                agent_hostname="sentora",
                violation_detail="No successful data sync has ever completed",
                remediation="Trigger a full data sync from the Sync page",
            )
        )
        non_compliant = 1
        compliant = 0
        total = 1
    else:
        completed_at = latest_sync["completed_at"]
        if completed_at >= cutoff:
            status = CheckStatus.passed
            summary = (
                f"Last sync completed at {completed_at.isoformat()} "
                f"(within {max_hours}h window). {total_agents} agents in inventory."
            )
            non_compliant = 0
            compliant = 1
            total = 1
        else:
            age_hours = (now - completed_at).total_seconds() / 3600
            status = CheckStatus.failed
            summary = (
                f"Last sync completed {age_hours:.1f}h ago at "
                f"{completed_at.isoformat()} — exceeds {max_hours}h threshold"
            )
            violations.append(
                ComplianceViolation(
                    agent_id="system",
                    agent_hostname="sentora",
                    violation_detail=(f"Data is {age_hours:.1f}h old (threshold: {max_hours}h)"),
                    remediation="Trigger a data sync to refresh the inventory",
                )
            )
            non_compliant = 1
            compliant = 0
            total = 1

    return CheckResult(
        control_id=control_id,
        framework_id=framework_id,
        status=status,
        checked_at=now,
        total_endpoints=total,
        compliant_endpoints=compliant,
        non_compliant_endpoints=non_compliant,
        violations=violations,
        evidence_summary=summary,
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
