"""Compliance domain DTOs.

Pydantic models for API request and response boundaries.  These are
the only shapes that cross the HTTP transport layer — domain entities
never appear directly in API responses.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class FrameworkSummaryResponse(BaseModel):
    """Summary of a single compliance framework."""

    id: str
    name: str
    version: str
    description: str
    disclaimer: str
    enabled: bool
    total_controls: int
    enabled_controls: int


class FrameworkListResponse(BaseModel):
    """List of all available frameworks."""

    frameworks: list[FrameworkSummaryResponse]


class ControlResponse(BaseModel):
    """A single control with its current configuration."""

    id: str
    framework_id: str
    name: str
    description: str
    category: str
    severity: str
    check_type: str
    parameters: dict = Field(default_factory=dict)
    scope_tags: list[str] = Field(default_factory=list)
    scope_groups: list[str] = Field(default_factory=list)
    enabled: bool = True
    disable_reason: str | None = None
    hipaa_type: str | None = None
    bsi_level: str | None = None
    remediation: str = ""
    is_custom: bool = False


class FrameworkDetailResponse(BaseModel):
    """Full framework detail with all its controls."""

    id: str
    name: str
    version: str
    description: str
    disclaimer: str
    enabled: bool
    controls: list[ControlResponse]


class ViolationResponse(BaseModel):
    """A single compliance violation."""

    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None
    remediation: str = ""


class CheckResultResponse(BaseModel):
    """Result of evaluating a single control."""

    control_id: str
    framework_id: str
    control_name: str
    category: str
    severity: str
    status: str
    checked_at: str
    total_endpoints: int
    compliant_endpoints: int
    non_compliant_endpoints: int
    evidence_summary: str
    violations: list[ViolationResponse] = Field(default_factory=list)


class LatestResultsResponse(BaseModel):
    """Latest check results across all active controls."""

    results: list[CheckResultResponse]
    total: int
    checked_at: str | None = None


class ControlHistoryEntry(BaseModel):
    """A single historical check result for trend analysis."""

    status: str
    checked_at: str
    total_endpoints: int
    compliant_endpoints: int
    non_compliant_endpoints: int
    evidence_summary: str


class ControlHistoryResponse(BaseModel):
    """Historical trend for a single control."""

    control_id: str
    framework_id: str
    entries: list[ControlHistoryEntry]
    total: int


class FrameworkScoreResponse(BaseModel):
    """Aggregated compliance score for a single framework."""

    framework_id: str
    framework_name: str
    total_controls: int
    passed: int
    failed: int
    warning: int
    error: int
    not_applicable: int
    score_percent: float


class DashboardResponse(BaseModel):
    """Aggregated compliance dashboard across all enabled frameworks."""

    frameworks: list[FrameworkScoreResponse]
    overall_score_percent: float
    total_violations: int
    last_run_at: str | None = None


class ViolationListResponse(BaseModel):
    """Paginated list of current violations."""

    violations: list[ViolationDetailResponse]
    total: int
    page: int
    page_size: int


class ViolationDetailResponse(BaseModel):
    """Violation with control context for the violations list."""

    control_id: str
    framework_id: str
    control_name: str
    severity: str
    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None
    remediation: str = ""
    checked_at: str


class RunResultResponse(BaseModel):
    """Response after triggering a compliance run."""

    run_id: str
    status: str
    controls_evaluated: int
    passed: int
    failed: int
    warning: int
    duration_ms: int


class ScheduleResponse(BaseModel):
    """Current compliance check schedule."""

    run_after_sync: bool
    cron_expression: str | None = None
    enabled: bool
    updated_at: str | None = None
    updated_by: str | None = None


# ---------------------------------------------------------------------------
# Unified violations (compliance + enforcement merged)
# ---------------------------------------------------------------------------


class UnifiedViolationResponse(BaseModel):
    """A violation from either compliance or enforcement, with source tag."""

    source: str
    control_id: str
    control_name: str
    framework_id: str
    severity: str
    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None
    remediation: str = ""
    checked_at: str


class UnifiedViolationListResponse(BaseModel):
    """Merged violations from both modules."""

    violations: list[UnifiedViolationResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


class ConfigureControlRequest(BaseModel):
    """Request to update a control's tenant-specific configuration."""

    enabled: bool | None = None
    disable_reason: str | None = Field(
        None,
        max_length=1000,
        description="Justification for disabling a control (Statement of Applicability)",
    )
    severity_override: str | None = Field(
        None,
        description="Override severity: critical, high, medium, low",
    )
    parameters_override: dict | None = None
    scope_tags_override: list[str] | None = None
    scope_groups_override: list[str] | None = None


class CreateCustomControlRequest(BaseModel):
    """Request to create a tenant-specific custom control."""

    id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^custom-[a-z0-9][a-z0-9._-]*$",
        description=(
            "Must start with 'custom-', lowercase alphanumeric with dots/dashes/underscores"
        ),
    )
    framework_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., min_length=1, max_length=100)
    severity: str = Field(
        ...,
        description="critical, high, medium, low",
    )
    check_type: str = Field(
        ...,
        description="One of the supported check types",
    )
    parameters: dict = Field(default_factory=dict)
    scope_tags: list[str] = Field(default_factory=list)
    scope_groups: list[str] = Field(default_factory=list)
    remediation: str = Field("", max_length=2000)


class UpdateScheduleRequest(BaseModel):
    """Request to update the compliance check schedule."""

    run_after_sync: bool | None = None
    cron_expression: str | None = None
    enabled: bool | None = None


class RunComplianceRequest(BaseModel):
    """Request to trigger a compliance run with optional filters."""

    framework_id: str | None = Field(
        None,
        description="Run only controls for this framework",
    )
