"""Config domain DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AppConfigResponse(BaseModel):
    """Full config returned by GET /api/v1/config/."""

    classification_threshold: float
    partial_threshold: float
    ambiguity_gap: float
    universal_app_threshold: float
    suggestion_score_threshold: float
    page_size_agents: int
    page_size_apps: int
    page_size_audit: int
    refresh_interval_minutes: int
    schedule_sites_minutes: int
    schedule_groups_minutes: int
    schedule_agents_minutes: int
    schedule_apps_minutes: int
    schedule_tags_minutes: int
    proposal_coverage_min: float
    proposal_outside_max: float
    proposal_lift_min: float
    proposal_top_k: int
    library_ingestion_enabled: bool
    library_ingestion_interval_hours: int
    library_ingestion_sources: list[str]
    nvd_api_key_set: bool  # True if a key is configured (never expose the actual key)
    session_max_lifetime_days: int = 30
    session_inactivity_timeout_days: int = 30
    account_lockout_threshold: int = 5
    account_lockout_duration_minutes: int = 15
    password_min_length: int = 12
    password_require_uppercase: bool = True
    password_require_lowercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = False
    password_history_count: int = 5
    password_max_age_days: int = 0
    password_check_breached: bool = True
    brand_app_name: str
    brand_tagline: str
    brand_primary_color: str
    brand_logo_url: str
    brand_favicon_url: str
    updated_at: str


class AppConfigUpdateRequest(BaseModel):
    """Partial update accepted by PUT /api/v1/config/."""

    classification_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    partial_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    ambiguity_gap: float | None = Field(default=None, ge=0.0, le=1.0)
    universal_app_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    suggestion_score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    page_size_agents: int | None = Field(default=None, ge=1, le=5000)
    page_size_apps: int | None = Field(default=None, ge=1, le=5000)
    page_size_audit: int | None = Field(default=None, ge=1, le=1000)
    refresh_interval_minutes: int | None = Field(default=None, ge=0, le=1440)
    schedule_sites_minutes: int | None = Field(default=None, ge=0, le=10080)
    schedule_groups_minutes: int | None = Field(default=None, ge=0, le=10080)
    schedule_agents_minutes: int | None = Field(default=None, ge=0, le=10080)
    schedule_apps_minutes: int | None = Field(default=None, ge=0, le=10080)
    schedule_tags_minutes: int | None = Field(default=None, ge=0, le=10080)
    proposal_coverage_min: float | None = Field(default=None, ge=0.0, le=1.0)
    proposal_outside_max: float | None = Field(default=None, ge=0.0, le=1.0)
    proposal_lift_min: float | None = Field(default=None, ge=1.0, le=50.0)
    proposal_top_k: int | None = Field(default=None, ge=1, le=200)
    library_ingestion_enabled: bool | None = None
    library_ingestion_interval_hours: int | None = Field(default=None, ge=1, le=168)
    library_ingestion_sources: list[str] | None = None
    nvd_api_key: str | None = Field(default=None, max_length=200)
    session_max_lifetime_days: int | None = Field(default=None, ge=1, le=365)
    session_inactivity_timeout_days: int | None = Field(default=None, ge=1, le=365)
    account_lockout_threshold: int | None = Field(default=None, ge=1, le=100)
    account_lockout_duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    password_min_length: int | None = Field(default=None, ge=8, le=128)
    password_require_uppercase: bool | None = None
    password_require_lowercase: bool | None = None
    password_require_digit: bool | None = None
    password_require_special: bool | None = None
    password_history_count: int | None = Field(default=None, ge=0, le=24)
    password_max_age_days: int | None = Field(default=None, ge=0, le=365)
    password_check_breached: bool | None = None
    brand_app_name: str | None = Field(default=None, max_length=50)
    brand_tagline: str | None = Field(default=None, max_length=100)
    brand_primary_color: str | None = Field(
        default=None, pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"
    )
    brand_logo_url: str | None = Field(default=None, max_length=10_000)
    brand_favicon_url: str | None = Field(default=None, max_length=10_000)


class BrandingResponse(BaseModel):
    """Public branding info returned by GET /api/v1/branding (no auth required)."""

    app_name: str
    tagline: str
    primary_color: str
    logo_url: str
    favicon_url: str
