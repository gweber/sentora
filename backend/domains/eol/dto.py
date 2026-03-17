"""EOL domain DTOs.

Data transfer objects for the EOL REST API responses.  These are the
shapes returned to the frontend — entities never leak through the API
boundary.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class EOLCycleResponse(BaseModel):
    """A single release cycle in an EOL product."""

    cycle: str
    release_date: date | None = None
    support_end: date | None = None
    eol_date: date | None = None
    lts: bool = False
    latest_version: str | None = None
    latest_version_date: date | None = None
    is_eol: bool = False
    is_security_only: bool = False


class EOLProductResponse(BaseModel):
    """An EOL product with its lifecycle cycles."""

    product_id: str
    name: str
    cycles: list[EOLCycleResponse] = Field(default_factory=list)
    last_synced: datetime | None = None
    total_cycles: int = 0
    eol_cycles: int = 0
    matched_apps: int = 0


class EOLProductListResponse(BaseModel):
    """Paginated list of EOL products."""

    products: list[EOLProductResponse]
    total: int
    page: int
    page_size: int


class EOLSyncStatusResponse(BaseModel):
    """Status of the EOL data sync."""

    last_synced: datetime | None = None
    total_products: int = 0
    status: str = "idle"
    message: str = ""


class EOLMatchResponse(BaseModel):
    """EOL match data for a single application."""

    eol_product_id: str
    matched_cycle: str
    match_source: str
    match_confidence: float
    is_eol: bool
    eol_date: date | None = None
    is_security_only: bool = False
    support_end: date | None = None


class EOLFuzzyMatchReviewItem(BaseModel):
    """A fuzzy match pending human review."""

    app_name: str
    normalized_name: str
    suggested_product_id: str
    suggested_product_name: str
    confidence: float
    agent_count: int = 0


class EOLFuzzyMatchReviewResponse(BaseModel):
    """List of fuzzy matches pending review."""

    items: list[EOLFuzzyMatchReviewItem]
    total: int


class EOLSourceInfoResponse(BaseModel):
    """Information about the endoflife.date library source."""

    name: str = "endoflife.date"
    display_name: str = "EOL Lifecycle Data"
    last_synced: datetime | None = None
    total_products: int = 0
    total_eol_cycles: int = 0
    matched_apps: int = 0
    status: str = "unknown"


class ConfirmMatchRequest(BaseModel):
    """Request to confirm or dismiss a fuzzy match."""

    normalized_name: str
    eol_product_id: str
    action: str = Field(pattern="^(confirm|dismiss)$")


# ---------------------------------------------------------------------------
# Name mapping DTOs
# ---------------------------------------------------------------------------


class NameMappingItem(BaseModel):
    """A user-configured app name → EOL product mapping."""

    app_name_prefix: str
    eol_product_id: str
    updated_at: datetime | None = None
    created_at: datetime | None = None


class NameMappingListResponse(BaseModel):
    """All name mappings (built-in + user)."""

    builtin: list[NameMappingItem]
    custom: list[NameMappingItem]
    total_builtin: int
    total_custom: int


class UpsertNameMappingRequest(BaseModel):
    """Request to create or update a name mapping."""

    app_name_prefix: str = Field(min_length=1, max_length=200)
    eol_product_id: str = Field(min_length=1, max_length=100)
