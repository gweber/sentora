"""Export domain DTOs.

Data transfer objects for the software inventory export API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CpeInfo(BaseModel):
    """CPE identifier data for an application."""

    cpe_uri: str | None = None
    vendor: str | None = None
    product: str | None = None
    version: str | None = None
    match_confidence: float | None = None


class EolInfo(BaseModel):
    """EOL lifecycle data for an application."""

    product_id: str | None = None
    cycle: str | None = None
    eol_date: str | None = None
    is_eol: bool = False
    is_security_only: bool = False
    support_end: str | None = None


class SoftwareInventoryItem(BaseModel):
    """A single application in the exported software inventory."""

    app_name: str
    app_version: str | None = None
    publisher: str | None = None
    classification: str | None = None
    install_count: int = 0
    agent_count: int = 0
    cpe: CpeInfo | None = None
    eol: EolInfo | None = None
    taxonomy_categories: list[str] = Field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class ExportMetadata(BaseModel):
    """Metadata for an export response."""

    tenant_id: str = ""
    generated_at: datetime
    total_agents: int = 0
    total_unique_apps: int = 0
    filters_applied: dict = Field(default_factory=dict)


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total_items: int
    total_pages: int


class SoftwareInventoryExportResponse(BaseModel):
    """Full JSON export response."""

    export_metadata: ExportMetadata
    software_inventory: list[SoftwareInventoryItem]
    pagination: PaginationInfo
