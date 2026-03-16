"""Check: prohibited applications installed on endpoints.

Queries the classification results for agents that have applications
classified as ``Prohibited`` and cross-references with the scoped
agent set.
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

    # Aggregation: find agents with prohibited apps via classification_results
    # classification_results stores per-agent verdicts including app classifications
    pipeline: list[dict[str, Any]] = []

    # Stage 1: match scoped agents
    if scope_filter:
        pipeline.append({"$match": scope_filter})

    # Stage 2: lookup classification results for each agent
    pipeline.extend(
        [
            {
                "$lookup": {
                    "from": "classification_results",
                    "localField": "s1_agent_id",
                    "foreignField": "agent_id",
                    "as": "classification",
                }
            },
            {"$unwind": {"path": "$classification", "preserveNullAndEmptyArrays": True}},
        ]
    )

    # Stage 3: lookup installed apps that are flagged as prohibited
    # We check fingerprints for prohibited markers matching installed apps
    pipeline.extend(
        [
            {
                "$lookup": {
                    "from": "s1_installed_apps",
                    "let": {"agent_id": "$s1_agent_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$agent_id", "$$agent_id"]}}},
                        {"$match": {"risk_level": "prohibited"}},
                        {"$project": {"normalized_name": 1, "version": 1, "agent_id": 1}},
                    ],
                    "as": "prohibited_apps",
                }
            },
            {"$match": {"prohibited_apps": {"$ne": []}}},
            {
                "$project": {
                    "s1_agent_id": 1,
                    "hostname": 1,
                    "prohibited_apps": 1,
                }
            },
        ]
    )

    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()

    async for doc in db["s1_agents"].aggregate(pipeline):
        agent_id = doc["s1_agent_id"]
        hostname = doc.get("hostname", "unknown")
        non_compliant_agents.add(agent_id)
        for app in doc.get("prohibited_apps", []):
            app_name = app.get("normalized_name", "unknown")
            app_version = app.get("version", "")
            violations.append(
                ComplianceViolation(
                    agent_id=agent_id,
                    agent_hostname=hostname,
                    violation_detail=(
                        f"Prohibited application '{app_name}' v{app_version} installed"
                    ),
                    app_name=app_name,
                    app_version=app_version,
                    remediation=f"Uninstall '{app_name}' from endpoint {hostname}",
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
            f"{compliant}/{total_agents} endpoints free of prohibited software. "
            f"{len(violations)} violation(s) found on {non_compliant} endpoint(s)."
        ),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
