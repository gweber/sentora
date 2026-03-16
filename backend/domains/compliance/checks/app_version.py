"""Check: outdated application versions.

Compares installed application versions against known current versions
from the library or a manually configured version map.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import MAX_VIOLATIONS, not_applicable_result
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
    """Identify endpoints with outdated application versions.

    Uses an aggregation pipeline to compare installed app versions
    against the most common (latest) version per normalized app name.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: Optional ``version_map`` dict of app_name→min_version.
            If absent, uses the most common version as baseline.
            Optional ``max_outdated_percent`` (default 20) — above this
            threshold the check warns instead of passing.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for outdated apps.
    """
    now = utc_now()
    max_outdated_pct: float = parameters.get("max_outdated_percent", 20)

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

    # Build scoped agent IDs
    agent_ids: list[str] = []
    async for doc in db["s1_agents"].find(scope_filter or {}, {"s1_agent_id": 1}):
        agent_ids.append(doc["s1_agent_id"])

    if not agent_ids:
        return not_applicable_result(
            control_id=control_id,
            framework_id=framework_id,
            control_name=control_name,
            category=category,
            severity=severity,
            checked_at=now,
        )

    # Aggregation: find the most common version per app, then find agents
    # running older versions
    pipeline: list[dict[str, Any]] = [
        {"$match": {"agent_id": {"$in": agent_ids}}},
        {
            "$group": {
                "_id": {"app": "$normalized_name", "version": "$version"},
                "count": {"$sum": 1},
                "agents": {"$push": "$agent_id"},
            }
        },
        {"$sort": {"_id.app": 1, "count": -1}},
        {
            "$group": {
                "_id": "$_id.app",
                "top_version": {"$first": "$_id.version"},
                "top_count": {"$first": "$count"},
                "all_versions": {
                    "$push": {
                        "version": "$_id.version",
                        "count": "$count",
                        "agents": "$agents",
                    }
                },
            }
        },
        # Only include apps where there are at least 2 different versions
        {"$match": {"$expr": {"$gt": [{"$size": "$all_versions"}, 1]}}},
    ]

    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    # Resolve hostnames for violation reporting
    hostname_map: dict[str, str] = {}

    async for app_doc in db["s1_installed_apps"].aggregate(pipeline):
        app_name = app_doc["_id"]
        top_version = app_doc["top_version"]

        for version_entry in app_doc["all_versions"]:
            if version_entry["version"] == top_version:
                continue
            for agent_id in version_entry["agents"]:
                non_compliant_agents.add(agent_id)
                # Defer hostname lookup
                if agent_id not in hostname_map:
                    hostname_map[agent_id] = ""
                violations.append(
                    ComplianceViolation(
                        agent_id=agent_id,
                        agent_hostname="",  # Resolved below
                        violation_detail=(
                            f"'{app_name}' version {version_entry['version']} "
                            f"installed, fleet standard is {top_version}"
                        ),
                        app_name=app_name,
                        app_version=version_entry["version"],
                        remediation=(f"Update '{app_name}' to version {top_version}"),
                    )
                )

    # Batch-resolve hostnames
    if hostname_map:
        async for agent_doc in db["s1_agents"].find(
            {"s1_agent_id": {"$in": list(hostname_map.keys())}},
            {"s1_agent_id": 1, "hostname": 1},
        ):
            hostname_map[agent_doc["s1_agent_id"]] = agent_doc.get("hostname", "unknown")

        for violation in violations:
            violation.agent_hostname = hostname_map.get(violation.agent_id, "unknown")

    non_compliant = len(non_compliant_agents)
    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]
    compliant = total_agents - non_compliant
    outdated_pct = (non_compliant / total_agents * 100) if total_agents > 0 else 0

    if non_compliant == 0:
        status = CheckStatus.passed
    elif outdated_pct <= max_outdated_pct:
        status = CheckStatus.warning
    else:
        status = CheckStatus.failed

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
            f"{compliant}/{total_agents} endpoints running current app versions. "
            f"{non_compliant} endpoint(s) with outdated software ({outdated_pct:.1f}%)."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
