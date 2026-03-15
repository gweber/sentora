"""Enforcement domain DTOs.

Pydantic models for API request/response boundaries.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class EnforcementRuleResponse(BaseModel):
    """A single enforcement rule."""

    id: str
    name: str
    description: str | None = None
    taxonomy_category_id: str
    type: str
    severity: str
    enabled: bool
    scope_groups: list[str] = Field(default_factory=list)
    scope_tags: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    created_by: str | None = None


class RuleListResponse(BaseModel):
    """Paginated list of enforcement rules."""

    rules: list[EnforcementRuleResponse]
    total: int


class ViolationResponse(BaseModel):
    """A single enforcement violation."""

    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None


class EnforcementResultResponse(BaseModel):
    """Result of evaluating a single rule."""

    rule_id: str
    rule_name: str
    rule_type: str
    severity: str
    checked_at: str
    status: str
    total_agents: int
    compliant_agents: int
    non_compliant_agents: int
    violations: list[ViolationResponse] = Field(default_factory=list)


class CheckRunResponse(BaseModel):
    """Response after triggering an enforcement check run."""

    run_id: str
    rules_evaluated: int
    passed: int
    failed: int
    total_violations: int
    duration_ms: int


class SummaryResponse(BaseModel):
    """Aggregated enforcement summary."""

    total_rules: int
    enabled_rules: int
    passing: int
    failing: int
    total_violations: int
    by_severity: dict[str, int] = Field(default_factory=dict)
    last_checked_at: str | None = None


class ViolationDetailResponse(BaseModel):
    """Violation with rule context for the violations feed."""

    rule_id: str
    rule_name: str
    rule_type: str
    severity: str
    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None
    checked_at: str


class ViolationListResponse(BaseModel):
    """Paginated violation list."""

    violations: list[ViolationDetailResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


class CreateRuleRequest(BaseModel):
    """Request to create an enforcement rule."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    taxonomy_category_id: str = Field(..., min_length=1)
    type: str = Field(..., description="required, forbidden, or allowlist")
    severity: str = Field(..., description="critical, high, medium, or low")
    scope_groups: list[str] = Field(default_factory=list)
    scope_tags: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)


class UpdateRuleRequest(BaseModel):
    """Request to update an enforcement rule."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    taxonomy_category_id: str | None = None
    type: str | None = None
    severity: str | None = None
    scope_groups: list[str] | None = None
    scope_tags: list[str] | None = None
    labels: list[str] | None = None
