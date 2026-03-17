"""Export domain router.

Provides the CPE-enriched software inventory export API endpoint
with JSON and CSV format support, pagination, and caching.
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
from domains.export import service
from domains.export.dto import SoftwareInventoryExportResponse
from middleware.auth import require_role
from utils.csv_sanitize import sanitize_csv_cell

router = APIRouter()


@router.get(
    "/software-inventory",
    response_model=SoftwareInventoryExportResponse,
    summary="Export CPE-enriched software inventory",
)
async def export_software_inventory(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(require_role(UserRole.admin, UserRole.viewer)),
    format: str = Query("json", pattern="^(json|csv)$", description="Output format"),
    include_eol: bool = Query(True, description="Include EOL lifecycle data"),
    include_cpe: bool = Query(True, description="Include CPE identifiers"),
    scope_groups: str | None = Query(None, description="Comma-separated group names"),
    scope_tags: str | None = Query(None, description="Comma-separated tags"),
    classification: str | None = Query(
        None,
        pattern="^(approved|flagged|prohibited|unclassified)$",
        description="Classification filter",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(1000, ge=1, le=5000, description="Items per page"),
) -> SoftwareInventoryExportResponse | StreamingResponse:
    """Export the software inventory enriched with CPE and EOL data.

    Supports JSON and CSV formats.  Results are paginated and cached
    for performance with large datasets.

    Args:
        db: Tenant database handle.
        format: Output format (``json`` or ``csv``).
        include_eol: Whether to include EOL lifecycle data.
        include_cpe: Whether to include CPE identifiers.
        scope_groups: Comma-separated S1 group names to filter by.
        scope_tags: Comma-separated tags to filter by.
        classification: Classification status filter.
        page: Page number.
        page_size: Page size.

    Returns:
        JSON response or CSV streaming response.
    """
    # Parse comma-separated filters
    groups = [g.strip() for g in scope_groups.split(",") if g.strip()] if scope_groups else None
    tags = [t.strip() for t in scope_tags.split(",") if t.strip()] if scope_tags else None

    # Audit log the export
    try:
        from audit.log import audit

        await audit(
            db,
            domain="export",
            action="export.software_inventory",
            actor=_user.sub,
            status="success",
            summary=f"Software inventory export ({format})",
            details={
                "format": format,
                "include_eol": include_eol,
                "include_cpe": include_cpe,
                "scope_groups": groups,
                "scope_tags": tags,
                "classification": classification,
                "page": page,
                "page_size": page_size,
            },
        )
    except Exception:
        pass  # Don't fail the export if audit logging fails

    result = await service.build_software_inventory(
        db,
        include_eol=include_eol,
        include_cpe=include_cpe,
        scope_groups=groups,
        scope_tags=tags,
        classification=classification,
        page=page,
        page_size=page_size,
    )

    if format == "csv":
        return _build_csv_response(result)

    return result


def _build_csv_response(
    result: SoftwareInventoryExportResponse,
) -> StreamingResponse:
    """Build a CSV streaming response from the export result.

    Flattens nested CPE and EOL objects into flat CSV columns.

    Args:
        result: The export response to convert to CSV.

    Returns:
        FastAPI StreamingResponse with CSV content.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    headers = [
        "app_name",
        "app_version",
        "publisher",
        "classification",
        "install_count",
        "agent_count",
        "cpe_uri",
        "cpe_vendor",
        "cpe_product",
        "eol_product_id",
        "eol_cycle",
        "eol_date",
        "is_eol",
        "taxonomy_categories",
    ]
    writer.writerow(headers)

    for item in result.software_inventory:
        cpe = item.cpe
        eol = item.eol
        writer.writerow(
            [
                sanitize_csv_cell(item.app_name),
                sanitize_csv_cell(item.app_version or ""),
                sanitize_csv_cell(item.publisher or ""),
                sanitize_csv_cell(item.classification or ""),
                item.install_count,
                item.agent_count,
                sanitize_csv_cell(cpe.cpe_uri or "" if cpe else ""),
                sanitize_csv_cell(cpe.vendor or "" if cpe else ""),
                sanitize_csv_cell(cpe.product or "" if cpe else ""),
                sanitize_csv_cell(eol.product_id or "" if eol else ""),
                sanitize_csv_cell(eol.cycle or "" if eol else ""),
                sanitize_csv_cell(eol.eol_date or "" if eol else ""),
                eol.is_eol if eol else "",
                sanitize_csv_cell(";".join(item.taxonomy_categories)),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sentora-software-inventory.csv",
        },
    )
