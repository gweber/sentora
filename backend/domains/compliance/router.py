"""Compliance domain router.

CQRS-aligned endpoint organisation: command endpoints (POST/PUT/DELETE)
delegate to ``commands``, query endpoints (GET) delegate to ``queries``.

Endpoints:
    GET    /frameworks                    — list all frameworks
    GET    /frameworks/{id}               — framework detail with controls
    PUT    /frameworks/{id}/enable        — enable framework
    PUT    /frameworks/{id}/disable       — disable framework
    GET    /controls/{id}                 — control detail (via framework)
    PUT    /controls/{id}                 — configure control overrides
    POST   /controls/custom              — create custom control
    POST   /run                          — trigger compliance run
    GET    /results/latest               — latest results
    GET    /results/{control_id}/history  — control history
    GET    /dashboard                    — aggregated dashboard
    GET    /violations                   — paginated violations
    GET    /violations/export            — CSV export
    GET    /schedule                     — get schedule
    PUT    /schedule                     — update schedule
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.compliance import commands, queries
from domains.compliance.dto import (
    ConfigureControlRequest,
    ControlHistoryResponse,
    ControlResponse,
    CreateCustomControlRequest,
    DashboardResponse,
    FrameworkDetailResponse,
    FrameworkListResponse,
    LatestResultsResponse,
    RunComplianceRequest,
    RunResultResponse,
    ScheduleResponse,
    UnifiedViolationListResponse,
    UnifiedViolationResponse,
    UpdateScheduleRequest,
    ViolationListResponse,
)
from domains.compliance.entities import CheckStatus
from domains.compliance.platform.router import router as platform_router
from middleware.auth import get_current_user, require_role

router = APIRouter()

# Mount the platform self-audit sub-router under /compliance/platform/
router.include_router(platform_router, prefix="/platform", tags=["platform-compliance"])


# ---------------------------------------------------------------------------
# Framework management
# ---------------------------------------------------------------------------


@router.get(
    "/frameworks",
    response_model=FrameworkListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_frameworks(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FrameworkListResponse:
    """List all available compliance frameworks with enabled state."""
    return await queries.list_frameworks(db)


@router.get(
    "/frameworks/{framework_id}",
    response_model=FrameworkDetailResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_framework_detail(
    framework_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> FrameworkDetailResponse:
    """Get full framework detail including all controls."""
    return await queries.get_framework_detail(db, framework_id)


@router.put(
    "/frameworks/{framework_id}/enable",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def enable_framework(
    framework_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, str]:
    """Enable a compliance framework. Admin only."""
    await commands.enable_framework(db, framework_id, actor=user.sub)
    return {"detail": f"Framework {framework_id} enabled"}


@router.put(
    "/frameworks/{framework_id}/disable",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def disable_framework(
    framework_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, str]:
    """Disable a compliance framework. Admin only."""
    await commands.disable_framework(db, framework_id, actor=user.sub)
    return {"detail": f"Framework {framework_id} disabled"}


# ---------------------------------------------------------------------------
# Control configuration
# ---------------------------------------------------------------------------


@router.put(
    "/controls/{control_id}",
    response_model=ControlResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def configure_control(
    control_id: str,
    payload: ConfigureControlRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ControlResponse:
    """Configure a control's tenant-specific overrides. Admin only."""
    config = await commands.configure_control(
        db,
        control_id,
        actor=user.sub,
        enabled=payload.enabled,
        severity_override=payload.severity_override,
        parameters_override=payload.parameters_override,
        scope_tags_override=payload.scope_tags_override,
        scope_groups_override=payload.scope_groups_override,
    )
    return ControlResponse(
        id=config.control_id,
        framework_id=config.framework_id,
        name=config.control_id,
        description="",
        category="",
        severity=(config.severity_override.value if config.severity_override else ""),
        check_type="",
        parameters=config.parameters_override,
        scope_tags=config.scope_tags_override or [],
        scope_groups=config.scope_groups_override or [],
        enabled=config.enabled,
    )


@router.post(
    "/controls/custom",
    response_model=ControlResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
    status_code=201,
)
async def create_custom_control(
    payload: CreateCustomControlRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ControlResponse:
    """Create a tenant-specific custom control. Admin only."""
    custom = await commands.create_custom_control(
        db,
        actor=user.sub,
        control_id=payload.id,
        framework_id=payload.framework_id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        severity=payload.severity,
        check_type=payload.check_type,
        parameters=payload.parameters,
        scope_tags=payload.scope_tags,
        scope_groups=payload.scope_groups,
        remediation=payload.remediation,
    )
    return ControlResponse(
        id=custom.id,
        framework_id=custom.framework_id,
        name=custom.name,
        description=custom.description,
        category=custom.category,
        severity=custom.severity.value,
        check_type=custom.check_type,
        parameters=custom.parameters,
        scope_tags=custom.scope_tags,
        scope_groups=custom.scope_groups,
        enabled=True,
        remediation=custom.remediation,
        is_custom=True,
    )


# ---------------------------------------------------------------------------
# Check execution
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=RunResultResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def run_compliance(
    payload: RunComplianceRequest | None = None,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> RunResultResponse:
    """Trigger a compliance check run. Admin only."""
    framework_id = payload.framework_id if payload else None
    run_id, results, duration_ms = await commands.trigger_compliance_run(
        db, actor=user.sub, framework_id=framework_id
    )

    passed = sum(1 for r in results if r.status == CheckStatus.passed)
    failed = sum(1 for r in results if r.status == CheckStatus.failed)
    warning = sum(1 for r in results if r.status == CheckStatus.warning)

    return RunResultResponse(
        run_id=run_id,
        status="completed",
        controls_evaluated=len(results),
        passed=passed,
        failed=failed,
        warning=warning,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Results & dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/results/latest",
    response_model=LatestResultsResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_latest_results(
    framework: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> LatestResultsResponse:
    """Get the latest check results for all active controls."""
    return await queries.get_latest_check_results(db, framework)


@router.get(
    "/results/{control_id}/history",
    response_model=ControlHistoryResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_control_history(
    control_id: str,
    limit: int = Query(90, ge=1, le=365),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ControlHistoryResponse:
    """Get historical check results for trend analysis."""
    return await queries.get_control_trend(db, control_id, limit)


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> DashboardResponse:
    """Get aggregated compliance scores across all enabled frameworks."""
    return await queries.get_dashboard(db)


@router.get(
    "/violations",
    response_model=ViolationListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_violations(
    framework: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ViolationListResponse:
    """Get paginated list of current compliance violations."""
    return await queries.list_violations(db, framework, severity, page, page_size)


@router.get(
    "/violations/export",
    dependencies=[Depends(get_current_user)],
)
async def export_violations_csv(
    framework: str | None = Query(None),
    severity: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> StreamingResponse:
    """Export current violations as CSV."""
    from utils.csv_sanitize import sanitize_csv_cell

    result = await queries.list_violations(db, framework, severity, page=1, page_size=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Framework",
            "Control ID",
            "Control Name",
            "Severity",
            "Agent ID",
            "Hostname",
            "Violation",
            "Application",
            "Version",
            "Remediation",
            "Checked At",
        ]
    )

    for v in result.violations:
        writer.writerow(
            [
                sanitize_csv_cell(v.framework_id),
                sanitize_csv_cell(v.control_id),
                sanitize_csv_cell(v.control_name),
                sanitize_csv_cell(v.severity),
                sanitize_csv_cell(v.agent_id),
                sanitize_csv_cell(v.agent_hostname),
                sanitize_csv_cell(v.violation_detail),
                sanitize_csv_cell(v.app_name or ""),
                sanitize_csv_cell(v.app_version or ""),
                sanitize_csv_cell(v.remediation),
                sanitize_csv_cell(v.checked_at),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="compliance-violations.csv"'},
    )


# ---------------------------------------------------------------------------
# Unified violations (compliance + enforcement)
# ---------------------------------------------------------------------------


@router.get(
    "/violations/unified",
    response_model=UnifiedViolationListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_unified_violations(
    source: str | None = Query(None, description="Filter: compliance, enforcement, or all"),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> UnifiedViolationListResponse:
    """Get paginated violations from both compliance and enforcement.

    A single feed for the MSP technician to see everything that's broken,
    filterable by source module and severity.

    Pagination is pushed into each sub-query to avoid loading all violations
    into memory. Each source contributes at most ``page_size`` items; the
    combined result is then merged, sorted, and truncated to ``page_size``.
    Total counts are obtained cheaply from each source.
    """
    all_violations: list[UnifiedViolationResponse] = []
    total = 0

    # Compliance violations — fetch only the requested page
    if source in (None, "compliance"):
        compliance_result = await queries.list_violations(
            db, None, severity, page=page, page_size=page_size
        )
        total += compliance_result.total
        for v in compliance_result.violations:
            all_violations.append(
                UnifiedViolationResponse(
                    source="compliance",
                    control_id=v.control_id,
                    control_name=v.control_name,
                    framework_id=v.framework_id,
                    severity=v.severity,
                    agent_id=v.agent_id,
                    agent_hostname=v.agent_hostname,
                    violation_detail=v.violation_detail,
                    app_name=v.app_name,
                    app_version=v.app_version,
                    remediation=v.remediation,
                    checked_at=v.checked_at,
                )
            )

    # Enforcement violations — fetch only the requested page
    if source in (None, "enforcement"):
        from domains.enforcement import service as enforcement_service

        enforcement_result = await enforcement_service.list_current_violations(
            db, severity, page=page, page_size=page_size
        )
        total += enforcement_result.total
        for v in enforcement_result.violations:  # type: ignore[assignment]
            all_violations.append(
                UnifiedViolationResponse(
                    source="enforcement",
                    control_id=v.rule_id,  # type: ignore[attr-defined]
                    control_name=v.rule_name,  # type: ignore[attr-defined]
                    framework_id=v.rule_type,  # type: ignore[attr-defined]
                    severity=v.severity,
                    agent_id=v.agent_id,
                    agent_hostname=v.agent_hostname,
                    violation_detail=v.violation_detail,
                    app_name=v.app_name,
                    app_version=v.app_version,
                    remediation="",
                    checked_at=v.checked_at,
                )
            )

    # Sort merged page by severity priority then checked_at
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_violations.sort(
        key=lambda v: (severity_order.get(v.severity, 9), v.checked_at),
    )

    # Trim to page_size (we may have up to 2*page_size from two sources)
    paginated = all_violations[:page_size]

    return UnifiedViolationListResponse(
        violations=paginated,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


@router.get(
    "/schedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_schedule(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ScheduleResponse:
    """Get the current compliance check schedule."""
    return await queries.get_schedule_config(db)


@router.put(
    "/schedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def update_schedule(
    payload: UpdateScheduleRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ScheduleResponse:
    """Update the compliance check schedule. Admin only."""
    schedule = await commands.update_schedule(
        db,
        actor=user.sub,
        run_after_sync=payload.run_after_sync,
        cron_expression=payload.cron_expression,
        enabled=payload.enabled,
    )
    return ScheduleResponse(
        run_after_sync=schedule.run_after_sync,
        cron_expression=schedule.cron_expression,
        enabled=schedule.enabled,
        updated_at=(schedule.updated_at.isoformat() if schedule.updated_at else None),
        updated_by=schedule.updated_by,
    )
