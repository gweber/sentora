"""Compliance domain — query handlers (CQRS read side).

All read-only operations go through this module.  Queries never
modify state.  They assemble DTOs from repository data and framework
definitions.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.dto import (
    CheckResultResponse,
    ControlHistoryEntry,
    ControlHistoryResponse,
    ControlResponse,
    DashboardResponse,
    FrameworkDetailResponse,
    FrameworkListResponse,
    FrameworkScoreResponse,
    FrameworkSummaryResponse,
    LatestResultsResponse,
    ScheduleResponse,
    ViolationDetailResponse,
    ViolationListResponse,
    ViolationResponse,
)
from domains.compliance.entities import CheckStatus
from domains.compliance.frameworks.registry import (
    get_all_frameworks,
    get_framework,
    get_framework_controls,
)
from domains.compliance.repository import (
    get_all_control_configs,
    get_all_current_violations,
    get_all_framework_configs,
    get_control_history,
    get_latest_results,
    get_schedule,
    list_custom_controls,
)
from errors import FrameworkNotFoundError


async def list_frameworks(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> FrameworkListResponse:
    """List all available frameworks with their enabled state and control counts.

    Args:
        db: Motor database handle.

    Returns:
        FrameworkListResponse with all frameworks.
    """
    frameworks = get_all_frameworks()
    configs = await get_all_framework_configs(db)
    all_control_configs = await get_all_control_configs(db)

    # Build per-framework disabled control sets
    disabled_controls: dict[str, set[str]] = {}
    for cc in all_control_configs:
        if not cc.enabled:
            disabled_controls.setdefault(cc.framework_id, set()).add(cc.control_id)

    summaries: list[FrameworkSummaryResponse] = []
    for fw in frameworks:
        built_in_count = len(get_framework_controls(fw.id))
        custom_controls = await list_custom_controls(db, fw.id)
        total = built_in_count + len(custom_controls)

        disabled = disabled_controls.get(fw.id, set())
        enabled_count = total - len(disabled)

        summaries.append(
            FrameworkSummaryResponse(
                id=fw.id,
                name=fw.name,
                version=fw.version,
                description=fw.description,
                disclaimer=fw.disclaimer,
                enabled=configs.get(fw.id, False),
                total_controls=total,
                enabled_controls=enabled_count,
            )
        )

    return FrameworkListResponse(frameworks=summaries)


async def get_framework_detail(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str,
) -> FrameworkDetailResponse:
    """Get full detail for a framework including all controls.

    Args:
        db: Motor database handle.
        framework_id: The framework to query.

    Returns:
        FrameworkDetailResponse with all controls.

    Raises:
        FrameworkNotFoundError: If the framework is unknown.
    """
    fw = get_framework(framework_id)
    if fw is None:
        raise FrameworkNotFoundError(f"Unknown framework: {framework_id}")

    configs = await get_all_framework_configs(db)
    control_configs = await get_all_control_configs(db, framework_id)
    config_map = {cc.control_id: cc for cc in control_configs}

    controls: list[ControlResponse] = []

    # Built-in controls
    for defn in get_framework_controls(framework_id):
        cc = config_map.get(defn.id)
        controls.append(
            ControlResponse(
                id=defn.id,
                framework_id=framework_id,
                name=defn.name,
                description=defn.description,
                category=defn.category,
                severity=(
                    cc.severity_override.value
                    if cc and cc.severity_override
                    else defn.severity.value
                ),
                check_type=defn.check_type,
                parameters=(
                    {**defn.parameters, **(cc.parameters_override or {})}
                    if cc
                    else dict(defn.parameters)
                ),
                scope_tags=(
                    cc.scope_tags_override
                    if cc and cc.scope_tags_override is not None
                    else list(defn.scope_tags)
                ),
                scope_groups=(
                    cc.scope_groups_override
                    if cc and cc.scope_groups_override is not None
                    else list(defn.scope_groups)
                ),
                enabled=cc.enabled if cc else True,
                hipaa_type=defn.hipaa_type.value if defn.hipaa_type else None,
                bsi_level=defn.bsi_level.value if defn.bsi_level else None,
                remediation=defn.remediation,
                is_custom=False,
            )
        )

    # Custom controls
    custom_controls = await list_custom_controls(db, framework_id)
    for custom in custom_controls:
        cc = config_map.get(custom.id)
        controls.append(
            ControlResponse(
                id=custom.id,
                framework_id=framework_id,
                name=custom.name,
                description=custom.description,
                category=custom.category,
                severity=(
                    cc.severity_override.value
                    if cc and cc.severity_override
                    else custom.severity.value
                ),
                check_type=custom.check_type,
                parameters=(
                    {**custom.parameters, **(cc.parameters_override or {})}
                    if cc
                    else dict(custom.parameters)
                ),
                scope_tags=(
                    cc.scope_tags_override
                    if cc and cc.scope_tags_override is not None
                    else list(custom.scope_tags)
                ),
                scope_groups=(
                    cc.scope_groups_override
                    if cc and cc.scope_groups_override is not None
                    else list(custom.scope_groups)
                ),
                enabled=cc.enabled if cc else True,
                remediation=custom.remediation,
                is_custom=True,
            )
        )

    return FrameworkDetailResponse(
        id=fw.id,
        name=fw.name,
        version=fw.version,
        description=fw.description,
        disclaimer=fw.disclaimer,
        enabled=configs.get(fw.id, False),
        controls=controls,
    )


async def get_dashboard(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> DashboardResponse:
    """Get the aggregated compliance dashboard across all enabled frameworks.

    Args:
        db: Motor database handle.

    Returns:
        DashboardResponse with per-framework scores and totals.
    """
    configs = await get_all_framework_configs(db)
    enabled_fw_ids = [fw_id for fw_id, enabled in configs.items() if enabled]

    if not enabled_fw_ids:
        return DashboardResponse(
            frameworks=[],
            overall_score_percent=0.0,
            total_violations=0,
            last_run_at=None,
        )

    latest = await get_latest_results(db)

    # Group results by framework
    by_framework: dict[str, list[dict[str, Any]]] = {}
    for r in latest:
        fw_id = r.get("framework_id", "")
        if fw_id in enabled_fw_ids:
            by_framework.setdefault(fw_id, []).append(r)

    frameworks: list[FrameworkScoreResponse] = []
    total_passed = 0
    total_applicable = 0
    total_violations = 0
    last_run_at: str | None = None

    for fw_id in enabled_fw_ids:
        fw = get_framework(fw_id)
        results = by_framework.get(fw_id, [])

        passed = sum(1 for r in results if r["status"] == CheckStatus.passed.value)
        failed = sum(1 for r in results if r["status"] == CheckStatus.failed.value)
        warning = sum(1 for r in results if r["status"] == CheckStatus.warning.value)
        error = sum(1 for r in results if r["status"] == CheckStatus.error.value)
        na = sum(1 for r in results if r["status"] == CheckStatus.not_applicable.value)

        applicable = len(results) - na
        score = (passed / applicable * 100) if applicable > 0 else 0.0

        total_passed += passed
        total_applicable += applicable

        for r in results:
            total_violations += len(r.get("violations", []))
            checked = r.get("checked_at")
            if checked:
                checked_str = checked.isoformat() if hasattr(checked, "isoformat") else str(checked)
                if last_run_at is None or checked_str > last_run_at:
                    last_run_at = checked_str

        frameworks.append(
            FrameworkScoreResponse(
                framework_id=fw_id,
                framework_name=fw.name if fw else fw_id,
                total_controls=len(results),
                passed=passed,
                failed=failed,
                warning=warning,
                error=error,
                not_applicable=na,
                score_percent=round(score, 1),
            )
        )

    overall = (total_passed / total_applicable * 100) if total_applicable > 0 else 0.0

    return DashboardResponse(
        frameworks=frameworks,
        overall_score_percent=round(overall, 1),
        total_violations=total_violations,
        last_run_at=last_run_at,
    )


async def get_latest_check_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> LatestResultsResponse:
    """Get the latest check result for each active control.

    Args:
        db: Motor database handle.
        framework_id: Optional framework filter.

    Returns:
        LatestResultsResponse with all results.
    """
    results = await get_latest_results(db, framework_id)

    items: list[CheckResultResponse] = []
    last_checked: str | None = None

    for r in results:
        checked_at = r.get("checked_at")
        checked_str = (
            checked_at.isoformat() if hasattr(checked_at, "isoformat") else str(checked_at or "")
        )
        if checked_str and (last_checked is None or checked_str > last_checked):
            last_checked = checked_str

        violations = [
            ViolationResponse(
                agent_id=v.get("agent_id", ""),
                agent_hostname=v.get("agent_hostname", ""),
                violation_detail=v.get("violation_detail", ""),
                app_name=v.get("app_name"),
                app_version=v.get("app_version"),
                remediation=v.get("remediation", ""),
            )
            for v in r.get("violations", [])
        ]

        items.append(
            CheckResultResponse(
                control_id=r.get("control_id", ""),
                framework_id=r.get("framework_id", ""),
                control_name=r.get("control_name", ""),
                category=r.get("category", ""),
                severity=r.get("severity", ""),
                status=r.get("status", ""),
                checked_at=checked_str,
                total_endpoints=r.get("total_endpoints", 0),
                compliant_endpoints=r.get("compliant_endpoints", 0),
                non_compliant_endpoints=r.get("non_compliant_endpoints", 0),
                evidence_summary=r.get("evidence_summary", ""),
                violations=violations,
            )
        )

    return LatestResultsResponse(
        results=items,
        total=len(items),
        checked_at=last_checked,
    )


async def get_control_trend(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    control_id: str,
    limit: int = 90,
) -> ControlHistoryResponse:
    """Get historical check results for trend analysis.

    Args:
        db: Motor database handle.
        control_id: The control to query.
        limit: Maximum entries to return.

    Returns:
        ControlHistoryResponse with historical entries.
    """
    history = await get_control_history(db, control_id, limit)

    entries: list[ControlHistoryEntry] = []
    framework_id = ""
    for h in history:
        if not framework_id:
            framework_id = h.get("framework_id", "")
        checked_at = h.get("checked_at")
        entries.append(
            ControlHistoryEntry(
                status=h.get("status", ""),
                checked_at=(
                    checked_at.isoformat()
                    if hasattr(checked_at, "isoformat")
                    else str(checked_at or "")
                ),
                total_endpoints=h.get("total_endpoints", 0),
                compliant_endpoints=h.get("compliant_endpoints", 0),
                non_compliant_endpoints=h.get("non_compliant_endpoints", 0),
                evidence_summary=h.get("evidence_summary", ""),
            )
        )

    return ControlHistoryResponse(
        control_id=control_id,
        framework_id=framework_id,
        entries=entries,
        total=len(entries),
    )


async def list_violations(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
    severity: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> ViolationListResponse:
    """Get paginated list of current violations.

    Args:
        db: Motor database handle.
        framework_id: Optional framework filter.
        severity: Optional severity filter.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        ViolationListResponse with paginated violations.
    """
    violations, total = await get_all_current_violations(
        db, framework_id, severity, page, page_size
    )

    items = [
        ViolationDetailResponse(
            control_id=v["control_id"],
            framework_id=v["framework_id"],
            control_name=v["control_name"],
            severity=v["severity"],
            agent_id=v["agent_id"],
            agent_hostname=v["agent_hostname"],
            violation_detail=v["violation_detail"],
            app_name=v.get("app_name"),
            app_version=v.get("app_version"),
            remediation=v.get("remediation", ""),
            checked_at=v.get("checked_at", ""),
        )
        for v in violations
    ]

    return ViolationListResponse(
        violations=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_schedule_config(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> ScheduleResponse:
    """Get the current compliance check schedule.

    Args:
        db: Motor database handle.

    Returns:
        ScheduleResponse with schedule details.
    """
    schedule = await get_schedule(db)
    return ScheduleResponse(
        run_after_sync=schedule.run_after_sync,
        cron_expression=schedule.cron_expression,
        enabled=schedule.enabled,
        updated_at=(schedule.updated_at.isoformat() if schedule.updated_at else None),
        updated_by=schedule.updated_by,
    )
