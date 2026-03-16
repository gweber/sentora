"""Platform compliance router.

Sentora's own security posture evaluation — separate from the endpoint
software compliance module.  Evaluates RBAC, audit logging, backups,
MFA adoption, and other platform-level controls against SOC 2 and
ISO 27001.

Endpoints:
    GET    /platform/dashboard/{framework}  — live control status
    POST   /platform/reports                — generate a report
    GET    /platform/reports                — list reports
    GET    /platform/reports/{id}           — get report detail
    DELETE /platform/reports/{id}           — delete a report
    GET    /platform/reports/{id}/csv       — export as CSV
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.compliance.platform import service
from domains.compliance.platform.dto import (
    GeneratePlatformReportRequest,
    PlatformDashboardResponse,
    PlatformReportDetailResponse,
    PlatformReportListResponse,
    PlatformReportResponse,
)
from domains.compliance.platform.entities import Framework
from middleware.auth import get_current_user, require_role

router = APIRouter()


def _parse_framework(framework: str) -> Framework:
    """Parse and validate framework string.

    Args:
        framework: Framework identifier.

    Returns:
        Validated Framework enum value.

    Raises:
        HTTPException: If the framework is unknown.
    """
    try:
        return Framework(framework)
    except ValueError as err:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown framework '{framework}'. Supported: soc2, iso27001",
        ) from err


@router.get(
    "/dashboard/{framework}",
    response_model=PlatformDashboardResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_dashboard(
    framework: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> PlatformDashboardResponse:
    """Return live platform compliance posture for a framework.

    Evaluates all platform controls in real-time against current data.
    """
    fw = _parse_framework(framework)
    data = await service.get_dashboard(db, fw)
    return PlatformDashboardResponse(**data)


@router.post(
    "/reports",
    response_model=PlatformReportResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def generate_report(
    payload: GeneratePlatformReportRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> PlatformReportResponse:
    """Generate a point-in-time platform compliance report.

    Evaluates all controls and persists the results as a snapshot.
    Admin only.
    """
    fw = _parse_framework(payload.framework)
    report = await service.generate_report(db, fw, payload.period_days, user.sub)
    return PlatformReportResponse(
        id=report.id,
        framework=report.framework,
        generated_at=report.generated_at,
        generated_by=report.generated_by,
        period_start=report.period_start,
        period_end=report.period_end,
        status=report.status,
        total_controls=report.total_controls,
        passing_controls=report.passing_controls,
        warning_controls=report.warning_controls,
        failing_controls=report.failing_controls,
    )


@router.get(
    "/reports",
    response_model=PlatformReportListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_reports(
    framework: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> PlatformReportListResponse:
    """List generated platform compliance reports (metadata only)."""
    reports = await service.list_reports(db, framework, limit)
    return PlatformReportListResponse(
        reports=[PlatformReportResponse(**r) for r in reports],
        total=len(reports),
    )


@router.get(
    "/reports/{report_id}",
    response_model=PlatformReportDetailResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_report(
    report_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> PlatformReportDetailResponse:
    """Get a single platform report with full control details."""
    report = await service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return PlatformReportDetailResponse(**report)


@router.delete(
    "/reports/{report_id}",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def delete_report(
    report_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> JSONResponse:
    """Delete a generated platform report. Admin only."""
    deleted = await service.delete_report(db, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return JSONResponse({"detail": "Report deleted"})


@router.get(
    "/reports/{report_id}/csv",
    dependencies=[Depends(get_current_user)],
)
async def export_report_csv(
    report_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> StreamingResponse:
    """Export a platform compliance report as CSV for auditor delivery."""
    report = await service.get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    from utils.csv_sanitize import sanitize_csv_cell

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Framework",
            "Reference",
            "Control",
            "Category",
            "Status",
            "Evidence Summary",
            "Evidence Count",
            "Period Start",
            "Period End",
            "Checked At",
        ]
    )
    for ctrl in report.get("controls", []):
        writer.writerow(
            [
                sanitize_csv_cell(report["framework"]),
                sanitize_csv_cell(ctrl.get("reference", "")),
                sanitize_csv_cell(ctrl.get("title", "")),
                sanitize_csv_cell(ctrl.get("category", "")),
                sanitize_csv_cell(ctrl.get("status", "")),
                sanitize_csv_cell(ctrl.get("evidence_summary", "")),
                ctrl.get("evidence_count", 0),
                sanitize_csv_cell(report.get("period_start", "")),
                sanitize_csv_cell(report.get("period_end", "")),
                sanitize_csv_cell(ctrl.get("last_checked", "")),
            ]
        )

    output.seek(0)
    filename = f"platform-compliance-{report['framework']}-{report_id[:8]}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
