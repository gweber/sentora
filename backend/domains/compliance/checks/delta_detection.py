"""Check: delta detection for software changes.

Identifies new or removed applications since the last compliance
check, flagging unauthorised software changes on scoped endpoints.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import MAX_VIOLATIONS, not_applicable_result
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
    """Detect new application installations since the last sync window.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: ``lookback_hours`` (default 24) — window to check
            for new installations.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for new unreviewed installations.
    """
    now = utc_now()
    lookback_hours: int = parameters.get("lookback_hours", 24)
    cutoff = now - timedelta(hours=lookback_hours)

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

    # Find recently synced apps (new installations within the lookback window)
    # that are on scoped agents
    agent_ids: list[str] = []
    if scope_filter:
        async for doc in db[AGENTS].find(scope_filter, {"source_id": 1}):
            agent_ids.append(doc["source_id"])
    else:
        # No scope = all agents; use a pipeline that doesn't need IDs
        agent_ids = []

    app_filter: dict[str, Any] = {"last_synced_at": {"$gte": cutoff}}
    if agent_ids:
        app_filter["agent_id"] = {"$in": agent_ids}

    # Count new apps in the window
    new_app_count = await db[INSTALLED_APPS].count_documents(app_filter)

    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    if new_app_count > 0:
        # Get details for reporting (limit to avoid overwhelming results)
        pipeline: list[dict[str, Any]] = [
            {"$match": app_filter},
            {
                "$group": {
                    "_id": "$agent_id",
                    "new_apps": {
                        "$push": {
                            "name": "$normalized_name",
                            "version": "$version",
                        }
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 100},
        ]

        hostname_map: dict[str, str] = {}
        agent_new_apps: dict[str, list[dict[str, str]]] = {}

        async for doc in db[INSTALLED_APPS].aggregate(pipeline):
            aid = doc["_id"]
            non_compliant_agents.add(aid)
            agent_new_apps[aid] = doc["new_apps"][:10]  # Cap per agent
            hostname_map[aid] = ""

        # Resolve hostnames
        if hostname_map:
            async for agent_doc in db[AGENTS].find(
                {"source_id": {"$in": list(hostname_map.keys())}},
                {"source_id": 1, "hostname": 1},
            ):
                hostname_map[agent_doc["source_id"]] = agent_doc.get("hostname", "unknown")

        for aid, apps in agent_new_apps.items():
            hostname = hostname_map.get(aid, "unknown")
            for app in apps:
                violations.append(
                    ComplianceViolation(
                        agent_id=aid,
                        agent_hostname=hostname,
                        violation_detail=(
                            f"New application detected: '{app['name']}' "
                            f"v{app.get('version', 'unknown')}"
                        ),
                        app_name=app["name"],
                        app_version=app.get("version"),
                        remediation=(f"Review and classify '{app['name']}' on {hostname}"),
                    )
                )

    non_compliant = len(non_compliant_agents)
    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]
    compliant = total_agents - non_compliant

    status = CheckStatus.passed if new_app_count == 0 else CheckStatus.warning

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
            f"{new_app_count} new application(s) detected across "
            f"{non_compliant} endpoint(s) in the last {lookback_hours}h. "
            f"{compliant}/{total_agents} endpoints unchanged."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
