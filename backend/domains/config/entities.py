"""Config domain entity.

A single global configuration document stored in MongoDB under _id="global".
Classification thresholds and other tunable parameters live here so they
persist across restarts without requiring an .env change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from utils.dt import utc_now


class AppConfig(BaseModel):
    """Persisted application configuration.

    Extra fields in the stored document (e.g. from older code versions)
    are silently ignored so that schema changes don't break config loading.
    """

    model_config = {"extra": "ignore"}

    classification_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    partial_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    ambiguity_gap: float = Field(default=0.15, ge=0.0, le=1.0)
    universal_app_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    suggestion_score_threshold: float = Field(default=0.50, ge=0.0, le=1.0)

    # Per-collection page sizes — UI-configurable defaults used by the frontend
    page_size_agents: int = Field(default=500, ge=1, le=5000)
    page_size_apps: int = Field(default=500, ge=1, le=5000)
    page_size_audit: int = Field(default=100, ge=1, le=1000)

    # Refresh schedule — minutes between automatic incremental refreshes (0 = disabled)
    refresh_interval_minutes: int = Field(default=60, ge=0, le=1440)

    # Per-phase schedule overrides (minutes, 0 = use global refresh_interval_minutes)
    schedule_sites_minutes: int = Field(default=0, ge=0, le=10080)
    schedule_groups_minutes: int = Field(default=0, ge=0, le=10080)
    schedule_agents_minutes: int = Field(default=0, ge=0, le=10080)
    schedule_apps_minutes: int = Field(default=0, ge=0, le=10080)
    schedule_tags_minutes: int = Field(default=0, ge=0, le=10080)

    # Fingerprint proposal thresholds (Lift-based auto-proposer)
    proposal_coverage_min: float = Field(default=0.60, ge=0.0, le=1.0)
    proposal_outside_max: float = Field(default=0.25, ge=0.0, le=1.0)
    proposal_lift_min: float = Field(default=2.0, ge=1.0, le=50.0)
    proposal_top_k: int = Field(default=100, ge=1, le=200)

    # Library ingestion settings
    library_ingestion_enabled: bool = Field(default=False)
    library_ingestion_interval_hours: int = Field(default=24, ge=1, le=168)
    library_ingestion_sources: list[str] = Field(default_factory=list)
    # nvd_api_key is encrypted at rest by the config repository using
    # ``utils.crypto.encrypt_field`` / ``decrypt_field``.  The entity
    # always holds the plaintext value; encryption is transparent.
    nvd_api_key: str = Field(
        default="",
        max_length=200,
        description="NVD API key for faster NIST CPE ingestion (register at nvd.nist.gov). "
        "Encrypted at rest in MongoDB.",
    )

    # Security — session management
    session_max_lifetime_days: int = Field(default=30, ge=1, le=365)
    session_inactivity_timeout_days: int = Field(default=30, ge=1, le=365)

    # Security — account lockout
    account_lockout_threshold: int = Field(default=5, ge=1, le=100)
    account_lockout_duration_minutes: int = Field(default=15, ge=1, le=1440)

    # Security — password policy
    password_min_length: int = Field(default=12, ge=8, le=128)
    password_require_uppercase: bool = Field(default=True)
    password_require_lowercase: bool = Field(default=True)
    password_require_digit: bool = Field(default=True)
    password_require_special: bool = Field(default=False)
    password_history_count: int = Field(default=5, ge=0, le=24)
    password_max_age_days: int = Field(default=0, ge=0, le=365)
    password_check_breached: bool = Field(default=True)

    # Branding / white-labeling
    brand_app_name: str = Field(default="Sentora", max_length=50)
    brand_tagline: str = Field(default="EDR Asset Classification", max_length=100)
    brand_primary_color: str = Field(
        default="#6366f1", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"
    )
    brand_logo_url: str = Field(default="", max_length=10_000)
    brand_favicon_url: str = Field(default="", max_length=10_000)

    updated_at: str = Field(default_factory=lambda: utc_now().isoformat())
