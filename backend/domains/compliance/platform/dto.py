"""Platform compliance DTOs.

Response models for the platform security posture endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlatformControlResponse(BaseModel):
    """Single platform control evaluation result."""

    control_id: str
    framework: str
    reference: str
    title: str
    category: str
    status: str
    evidence_summary: str
    evidence_count: int = 0
    last_checked: str = ""


class PlatformDashboardResponse(BaseModel):
    """Aggregate platform compliance posture for a framework."""

    framework: str
    total_controls: int
    passing: int
    warning: int
    failing: int
    not_applicable: int
    score_percent: float = Field(description="Passing / (total - not_applicable) * 100")
    controls: list[PlatformControlResponse]


class PlatformReportResponse(BaseModel):
    """Metadata for a generated platform compliance report."""

    id: str
    framework: str
    generated_at: str
    generated_by: str
    period_start: str
    period_end: str
    status: str
    total_controls: int
    passing_controls: int
    warning_controls: int
    failing_controls: int


class PlatformReportListResponse(BaseModel):
    """List of generated platform reports."""

    reports: list[PlatformReportResponse]
    total: int


class PlatformReportDetailResponse(PlatformReportResponse):
    """Full platform report including control details."""

    controls: list[PlatformControlResponse]


class GeneratePlatformReportRequest(BaseModel):
    """Request to generate a new platform compliance report."""

    framework: str = Field(description="soc2 or iso27001")
    period_days: int = Field(default=90, ge=1, le=365, description="Evidence period in days")
