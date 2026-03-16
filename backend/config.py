"""Application configuration.

Loads settings from environment variables and provides a single cached
Settings instance available throughout the application. Persisted config
(classification thresholds, exclusion patterns) is managed separately in
MongoDB via the config domain.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from backend/ or project root (one level up)
_HERE = Path(__file__).parent
_ENV_FILES = tuple(p for p in [_HERE / ".env", _HERE.parent / ".env"] if p.exists())


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    Attributes:
        s1_base_url: Base URL for the SentinelOne API (without trailing slash).
        s1_api_token: SentinelOne API bearer token. Never logged or returned in responses.
        s1_rate_limit_per_minute: Maximum S1 API requests per minute.
        mongo_uri: MongoDB connection URI.
        mongo_db: MongoDB database name.
        app_port: Port the backend server listens on.
        app_env: Runtime environment — controls debug mode and log verbosity.
        log_level: Python logging level name.
        classification_threshold: Default minimum score to classify an agent as correct.
        ambiguity_gap: Max gap between top two scores before classifying as ambiguous.
        universal_app_threshold: Fraction of agents an app must appear in to be "universal".
        suggestion_score_threshold: Minimum TF-IDF score for a suggestion to surface.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SentinelOne
    s1_base_url: str = Field(default="https://example.sentinelone.net")
    s1_api_token: str = Field(default="")
    s1_rate_limit_per_minute: int = Field(default=100, ge=1)

    # MongoDB
    mongo_uri: str = Field(default="mongodb://localhost:27017")
    mongo_db: str = Field(default="sentora")

    # App
    app_port: int = Field(default=5002, ge=1, le=65535)
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")

    # JWT Authentication
    jwt_secret_key: str = Field(
        default="",
        description=(
            "Secret key for JWT signing. Auto-generated if empty; MUST be set in production."
        ),
    )
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = Field(default="HS256")
    field_encryption_key: str = Field(
        default="",
        description="Separate key for field-level encryption. "
        "Falls back to jwt_secret_key if empty.",
    )
    jwt_access_expire_minutes: int = Field(default=15, ge=1)
    jwt_refresh_expire_days: int = Field(default=7, ge=1)

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otel_endpoint: str = Field(
        default="http://localhost:4317", description="OTLP exporter endpoint"
    )
    otel_service_name: str = Field(default="sentora", description="OTel service name")

    # OIDC / SSO
    oidc_enabled: bool = Field(default=False, description="Enable OpenID Connect SSO")
    oidc_discovery_url: str = Field(
        default="",
        description="OIDC discovery URL (e.g. https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration)",
    )
    oidc_client_id: str = Field(default="", description="OIDC client ID")
    oidc_client_secret: str = Field(default="", description="OIDC client secret")
    oidc_redirect_uri: str = Field(
        default="",
        description="OIDC redirect URI — must point to the frontend callback route (e.g. http://localhost:5002/auth/oidc/callback)",
    )
    oidc_default_role: str = Field(
        default="viewer",
        description="Default role for OIDC users (viewer/analyst/admin)",
    )

    # SAML SSO
    saml_enabled: bool = Field(default=False, description="Enable SAML 2.0 SSO")
    saml_idp_metadata_url: str = Field(default="", description="SAML IdP metadata URL")
    saml_sp_entity_id: str = Field(default="", description="SAML SP entity ID")
    saml_sp_acs_url: str = Field(default="", description="SAML SP ACS URL (callback)")
    saml_sp_cert: str = Field(default="", description="SP certificate (PEM or file path)")
    saml_sp_key: str = Field(default="", description="SP private key (PEM or file path)")
    saml_default_role: str = Field(default="viewer", description="Default role for SAML users")
    saml_name_id_format: str = Field(
        default="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        description="SAML NameID format",
    )

    # Multi-worker
    enable_distributed_locks: bool = Field(
        default=True,
        description="Use MongoDB distributed locks for multi-worker support",
    )
    workers: int = Field(default=1, ge=1, le=16, description="Number of uvicorn workers")

    # Backup / Restore
    backup_enabled: bool = Field(default=False, description="Enable scheduled backups")
    backup_local_path: str = Field(
        default="/backups", description="Local directory for backup storage"
    )
    backup_retention_count: int = Field(
        default=7, ge=1, le=365, description="Number of backups to retain"
    )
    backup_schedule_cron: str = Field(
        default="0 2 * * *", description="Cron schedule for automated backups"
    )

    # MongoDB High Availability
    mongo_read_preference: str = Field(
        default="primary",
        description=(
            "Read preference: primary, primaryPreferred, secondaryPreferred, secondary, nearest"
        ),
    )
    mongo_write_concern_w: str = Field(
        default="majority",
        description="Write concern: 'majority' or a number (e.g. '1', '2')",
    )
    mongo_write_concern_j: bool = Field(
        default=True,
        description="Write concern journal acknowledgement",
    )
    mongo_max_pool_size: int = Field(
        default=100, ge=1, le=500, description="Max connection pool size"
    )
    mongo_min_pool_size: int = Field(
        default=0, ge=0, le=100, description="Min connection pool size"
    )
    mongo_max_idle_time_ms: int = Field(
        default=30_000, ge=0, description="Max idle time for pooled connections (ms)"
    )

    # Deployment mode
    deployment_mode: Literal["onprem", "saas"] = Field(
        default="onprem",
        description=(
            "Deployment mode: 'onprem' for single-tenant on-premises, 'saas' for multi-tenant SaaS"
        ),
    )

    # Multi-tenancy
    multi_tenancy_enabled: bool = Field(
        default=False, description="Enable database-per-tenant multi-tenancy"
    )
    master_db_name: str = Field(
        default="sentora_master", description="Master database for tenant registry"
    )

    # Session management
    session_max_lifetime_days: int = Field(
        default=30, ge=1, le=365, description="Maximum session lifetime in days"
    )
    session_inactivity_timeout_days: int = Field(
        default=30, ge=1, le=365, description="Session expires after this many days of inactivity"
    )

    # Account lockout
    account_lockout_threshold: int = Field(
        default=5, ge=1, le=100, description="Number of failed login attempts before lockout"
    )
    account_lockout_duration_minutes: int = Field(
        default=15, ge=1, le=1440, description="Account lockout duration in minutes"
    )

    # Password policy
    password_min_length: int = Field(
        default=12, ge=8, le=128, description="Minimum password length"
    )
    password_require_uppercase: bool = Field(default=True, description="Require uppercase letter")
    password_require_lowercase: bool = Field(default=True, description="Require lowercase letter")
    password_require_digit: bool = Field(default=True, description="Require digit")
    password_require_special: bool = Field(
        default=False, description="Require special character (NIST recommends against)"
    )
    password_history_count: int = Field(
        default=5, ge=0, le=24, description="Number of previous passwords to remember"
    )
    password_max_age_days: int = Field(
        default=0,
        ge=0,
        le=365,
        description="Password expiry in days (0 = no expiry, NIST-compliant)",
    )
    password_check_breached: bool = Field(
        default=True,
        description="Check passwords against HaveIBeenPwned breach database (k-Anonymity API)",
    )

    # Rate limiting
    rate_limit_per_minute: int = Field(
        default=100, ge=1, description="Max API requests per minute per IP"
    )
    trusted_proxy_cidrs: str = Field(
        default="",
        description=(
            "Comma-separated CIDRs whose X-Forwarded-For "
            "header is trusted "
            "(e.g. '10.0.0.0/8,172.16.0.0/12')"
        ),
    )

    # Classification defaults
    classification_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    ambiguity_gap: float = Field(default=0.15, ge=0.0, le=1.0)
    universal_app_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    suggestion_score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("mongo_uri")
    @classmethod
    def validate_mongo_uri_scheme(cls, v: str) -> str:
        """Ensure MongoDB URI uses a valid scheme."""
        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGO_URI must start with 'mongodb://' or 'mongodb+srv://'")
        return v

    @field_validator("jwt_secret_key")
    @classmethod
    def generate_jwt_secret_if_empty(cls, v: str, info: ValidationInfo) -> str:
        """Auto-generate a random JWT secret if none is configured.

        Uses the ``app_env`` field (via ``info.data``) to detect production
        rather than reading ``os.environ`` directly, so the check is
        consistent with however the setting was resolved (env var, .env file,
        or default).
        """
        if not v:
            app_env = (info.data.get("app_env") or "development").lower()
            if app_env == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set in production. "
                    "Generate one with: "
                    'python -c "import secrets; '
                    'print(secrets.token_urlsafe(64))"'
                )
            import secrets
            import warnings

            generated = secrets.token_urlsafe(64)
            warnings.warn(
                "JWT_SECRET_KEY not set — using a random key. "
                "Tokens will be invalidated on restart. Set JWT_SECRET_KEY in production.",
                stacklevel=2,
            )
            return generated
        return v

    @field_validator("field_encryption_key")
    @classmethod
    def fallback_encryption_key(cls, v: str, info: ValidationInfo) -> str:
        """Fall back to JWT secret if no dedicated encryption key is set."""
        if not v:
            import warnings

            jwt_key = info.data.get("jwt_secret_key", "")
            if jwt_key:
                warnings.warn(
                    "FIELD_ENCRYPTION_KEY not set — falling back to JWT_SECRET_KEY. "
                    "Set a dedicated key for better security.",
                    stacklevel=2,
                )
                return jwt_key
        return v

    @field_validator("oidc_default_role", "saml_default_role")
    @classmethod
    def validate_sso_default_role(cls, v: str) -> str:
        """Ensure SSO default roles are constrained to known values (AUDIT-053).

        Prevents misconfiguration from granting unintended privileges when
        an operator sets an arbitrary string as the default role.

        Args:
            v: The configured role string.

        Returns:
            The validated role string.

        Raises:
            ValueError: If the role is not one of ``viewer``, ``analyst``,
                or ``admin``.
        """
        allowed = {"viewer", "analyst", "admin"}
        if v not in allowed:
            raise ValueError(f"SSO default role must be one of {sorted(allowed)}, got {v!r}")
        return v

    @field_validator("s1_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Remove trailing slash from base URL for consistent URL construction."""
        return v.rstrip("/")

    @field_validator("s1_api_token")
    @classmethod
    def warn_empty_token(cls, v: str) -> str:
        """Warn at startup if the S1 API token is not configured."""
        if not v or v in ("your-api-token-here", "CHANGE_ME", "build_placeholder"):
            import warnings

            warnings.warn(
                "S1_API_TOKEN is not configured — sync operations will fail. "
                "Set a valid token in your .env file.",
                stacklevel=2,
            )
        return v

    @property
    def mongo_uri_safe(self) -> str:
        """Return the MongoDB URI with credentials redacted for logging."""
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(self.mongo_uri)
        if parsed.username:
            safe = parsed._replace(
                netloc=f"***:***@{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
            )
            return urlunparse(safe)
        return self.mongo_uri

    @property
    def is_development(self) -> bool:
        """True when running in development mode."""
        return self.app_env == "development"

    @property
    def is_onprem(self) -> bool:
        """True when running in on-premises (single-tenant) mode."""
        return self.deployment_mode == "onprem"

    @property
    def is_saas(self) -> bool:
        """True when running in SaaS (multi-tenant) mode."""
        return self.deployment_mode == "saas"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Returns:
        The application Settings instance loaded from environment variables.
    """
    return Settings()
