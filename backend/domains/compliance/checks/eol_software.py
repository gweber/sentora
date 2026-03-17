"""Check: End-of-Life software detection.

Identifies applications that have reached End-of-Life status by evaluating
each agent's installed version against endoflife.date lifecycle cycles.

The ``eol_match`` field on ``app_summaries`` stores only the product mapping
(which endoflife.date product an app maps to).  This check evaluates the
actual installed version per agent at runtime to avoid false positives from
version-agnostic app summaries.
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
from domains.eol.matching import extract_cycle_match
from domains.eol.repository import get_all_products_with_cycles
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
    """Identify endpoints with End-of-Life software installed.

    Reads product mappings from ``app_summaries.eol_match``, then evaluates
    each agent's actual installed version against the product's EOL cycles.
    This per-agent evaluation avoids false positives from version-agnostic
    app summaries.

    Args:
        db: Motor database handle.
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        parameters: Check parameters:
            - ``flag_security_only`` (bool, default True): Also flag apps in
              security-only phase.
            - ``min_match_confidence`` (float, default 0.8): Only consider
              matches above this confidence threshold.
            - ``exclude_products`` (list[str]): Product IDs to skip.
        scope_filter: MongoDB filter for scoped agents.

    Returns:
        CheckResult with violations for EOL software.
    """
    now = utc_now()
    flag_security_only: bool = parameters.get("flag_security_only", True)
    min_confidence: float = parameters.get("min_match_confidence", 0.8)
    exclude_products: list[str] = parameters.get("exclude_products", [])

    # Count agents in scope
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

    # Build scoped agent IDs
    agent_ids: list[str] = []
    async for doc in db[AGENTS].find(scope_filter or {}, {"source_id": 1}):
        agent_ids.append(doc["source_id"])

    if not agent_ids:
        return not_applicable_result(
            control_id=control_id,
            framework_id=framework_id,
            control_name=control_name,
            category=category,
            severity=severity,
            checked_at=now,
        )

    # Load all EOL product cycles for runtime version evaluation
    all_cycles = await get_all_products_with_cycles(db)

    # Find apps with EOL product mappings above confidence threshold
    match_query: dict[str, Any] = {
        "eol_match": {"$exists": True},
        "eol_match.match_confidence": {"$gte": min_confidence},
        "eol_match.match_source": {"$in": ["cpe", "manual"]},
    }
    if exclude_products:
        match_query["eol_match.eol_product_id"] = {"$nin": exclude_products}

    # Build app → product mapping
    app_product_map: dict[str, str] = {}  # normalized_name → eol_product_id
    app_display_map: dict[str, str] = {}  # normalized_name → display_name
    async for doc in db["app_summaries"].find(match_query):
        nname = doc["normalized_name"]
        pid = doc["eol_match"]["eol_product_id"]
        if pid in all_cycles:
            app_product_map[nname] = pid
            app_display_map[nname] = doc.get("display_name", nname)

    if not app_product_map:
        return CheckResult(
            control_id=control_id,
            framework_id=framework_id,
            status=CheckStatus.passed,
            checked_at=now,
            total_endpoints=total_agents,
            compliant_endpoints=total_agents,
            non_compliant_endpoints=0,
            violations=[],
            evidence_summary=(f"No End-of-Life software detected across {total_agents} endpoints."),
            severity=ControlSeverity(severity),
            category=category,
            control_name=control_name,
        )

    # For each mapped app, query per-agent versions and evaluate against cycles
    violations: list[ComplianceViolation] = []
    non_compliant_agents: set[str] = set()
    hostname_map: dict[str, str] = {}
    eol_app_count = 0
    sec_only_app_count = 0

    mapped_app_names = list(app_product_map.keys())

    # Aggregate: (agent, app) → version
    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "agent_id": {"$in": agent_ids},
                "normalized_name": {"$in": mapped_app_names},
            }
        },
        {
            "$group": {
                "_id": {"agent": "$agent_id", "app": "$normalized_name"},
                "version": {"$first": "$version"},
            }
        },
    ]

    # Track which apps have at least one EOL version (for evidence summary)
    eol_apps_seen: set[str] = set()
    sec_only_apps_seen: set[str] = set()

    async for doc in db[INSTALLED_APPS].aggregate(pipeline):
        agent_id = doc["_id"]["agent"]
        app_name = doc["_id"]["app"]
        version = doc.get("version") or "unknown"

        product_id = app_product_map[app_name]
        cycles = all_cycles[product_id]
        display_name = app_display_map.get(app_name, app_name)

        # Evaluate THIS agent's specific version against cycles
        cycle = extract_cycle_match(version, cycles)
        if cycle is None:
            continue

        is_eol = cycle.is_eol
        is_security_only = cycle.is_security_only

        if not is_eol and not (flag_security_only and is_security_only):
            continue

        non_compliant_agents.add(agent_id)
        if agent_id not in hostname_map:
            hostname_map[agent_id] = ""

        if is_eol:
            eol_apps_seen.add(app_name)
            eol_date = cycle.eol_date.isoformat() if cycle.eol_date else "unknown"
            detail = (
                f"'{display_name}' version {version} is End-of-Life "
                f"since {eol_date}. No security patches are available."
            )
            remediation = (
                f"Upgrade {display_name} to a supported version. "
                f"Current version {version} reached End-of-Life on "
                f"{eol_date}. See https://endoflife.date/{product_id} "
                f"for supported versions."
            )
        else:
            sec_only_apps_seen.add(app_name)
            support_end = cycle.support_end.isoformat() if cycle.support_end else "unknown"
            detail = (
                f"'{display_name}' version {version} is in security-only "
                f"support since {support_end}. Active support has ended."
            )
            remediation = (
                f"Consider upgrading {display_name} to a fully supported "
                f"version. Active support ended on {support_end}. "
                f"See https://endoflife.date/{product_id} for current "
                f"versions."
            )

        violations.append(
            ComplianceViolation(
                agent_id=agent_id,
                agent_hostname="",
                violation_detail=detail,
                app_name=display_name,
                app_version=version,
                remediation=remediation,
            )
        )

    # Batch-resolve hostnames
    if hostname_map:
        async for agent_doc in db[AGENTS].find(
            {"source_id": {"$in": list(hostname_map.keys())}},
            {"source_id": 1, "hostname": 1},
        ):
            hostname_map[agent_doc["source_id"]] = agent_doc.get("hostname", "unknown")

        for violation in violations:
            violation.agent_hostname = hostname_map.get(violation.agent_id, "unknown")

    non_compliant = len(non_compliant_agents)
    if len(violations) > MAX_VIOLATIONS:
        violations = violations[:MAX_VIOLATIONS]
    compliant = total_agents - non_compliant

    eol_app_count = len(eol_apps_seen)
    sec_only_app_count = len(sec_only_apps_seen)

    status = CheckStatus.failed if non_compliant > 0 else CheckStatus.passed

    evidence_parts = [
        f"{non_compliant}/{total_agents} endpoints have End-of-Life software.",
        f"{eol_app_count} EOL application(s) detected.",
    ]
    if flag_security_only and sec_only_app_count > 0:
        evidence_parts.append(f"{sec_only_app_count} application(s) in security-only support.")

    return CheckResult(
        control_id=control_id,
        framework_id=framework_id,
        status=status,
        checked_at=now,
        total_endpoints=total_agents,
        compliant_endpoints=compliant,
        non_compliant_endpoints=non_compliant,
        violations=violations,
        evidence_summary=" ".join(evidence_parts),
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
