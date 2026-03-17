"""Config domain router.

GET  /api/v1/config/     — return current persisted config
PUT  /api/v1/config/     — merge-update config and persist
GET  /api/v1/branding    — return public branding info (no auth)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from database import get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from middleware.auth import get_current_user, require_role

from . import repository
from .dto import AppConfigResponse, AppConfigUpdateRequest, BrandingResponse

router = APIRouter()

_FLOAT_FIELDS = (
    "classification_threshold",
    "partial_threshold",
    "ambiguity_gap",
    "universal_app_threshold",
    "suggestion_score_threshold",
    "proposal_coverage_min",
    "proposal_outside_max",
    "proposal_lift_min",
)
_INT_FIELDS = (
    "page_size_agents",
    "page_size_apps",
    "page_size_audit",
    "refresh_interval_minutes",
    "schedule_sites_minutes",
    "schedule_groups_minutes",
    "schedule_agents_minutes",
    "schedule_apps_minutes",
    "schedule_tags_minutes",
    "proposal_top_k",
    "library_ingestion_interval_hours",
    "session_max_lifetime_days",
    "session_inactivity_timeout_days",
    "account_lockout_threshold",
    "account_lockout_duration_minutes",
    "password_min_length",
    "password_history_count",
    "password_max_age_days",
)
_BOOL_FIELDS = (
    "library_ingestion_enabled",
    "password_require_uppercase",
    "password_require_lowercase",
    "password_require_digit",
    "password_require_special",
    "password_check_breached",
    "oidc_enabled",
    "saml_enabled",
)
_LIST_FIELDS = ("library_ingestion_sources",)
_STR_FIELDS = (
    "brand_app_name",
    "brand_tagline",
    "brand_primary_color",
    "brand_logo_url",
    "brand_favicon_url",
    "nvd_api_key",
    "oidc_discovery_url",
    "oidc_client_id",
    "oidc_client_secret",
    "oidc_redirect_uri",
    "oidc_default_role",
    "saml_idp_metadata_url",
    "saml_sp_entity_id",
    "saml_sp_acs_url",
    "saml_default_role",
    "backup_storage_type",
    "backup_local_path",
    "backup_s3_endpoint",
    "backup_s3_bucket",
    "backup_s3_access_key",
    "backup_s3_secret_key",
    "backup_s3_region",
)
# Fields that must be encrypted before persisting to MongoDB
_ENCRYPTED_STR_FIELDS = frozenset(
    {"nvd_api_key", "oidc_client_secret", "backup_s3_access_key", "backup_s3_secret_key"}
)


def _check_path_writable(path_str: str) -> bool:
    """Check whether the server process can write to the given directory.

    Creates the directory if it does not exist, then attempts to write
    and immediately remove a small probe file.

    Args:
        path_str: Filesystem path to test.

    Returns:
        True if the directory is writable.
    """
    try:
        p = Path(path_str).resolve()
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".sentora_write_probe"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def _to_response(cfg: object) -> AppConfigResponse:
    from .entities import AppConfig

    assert isinstance(cfg, AppConfig)
    return AppConfigResponse(
        classification_threshold=cfg.classification_threshold,
        partial_threshold=cfg.partial_threshold,
        ambiguity_gap=cfg.ambiguity_gap,
        universal_app_threshold=cfg.universal_app_threshold,
        suggestion_score_threshold=cfg.suggestion_score_threshold,
        page_size_agents=cfg.page_size_agents,
        page_size_apps=cfg.page_size_apps,
        page_size_audit=cfg.page_size_audit,
        refresh_interval_minutes=cfg.refresh_interval_minutes,
        schedule_sites_minutes=cfg.schedule_sites_minutes,
        schedule_groups_minutes=cfg.schedule_groups_minutes,
        schedule_agents_minutes=cfg.schedule_agents_minutes,
        schedule_apps_minutes=cfg.schedule_apps_minutes,
        schedule_tags_minutes=cfg.schedule_tags_minutes,
        proposal_coverage_min=cfg.proposal_coverage_min,
        proposal_outside_max=cfg.proposal_outside_max,
        proposal_lift_min=cfg.proposal_lift_min,
        proposal_top_k=cfg.proposal_top_k,
        library_ingestion_enabled=cfg.library_ingestion_enabled,
        library_ingestion_interval_hours=cfg.library_ingestion_interval_hours,
        library_ingestion_sources=cfg.library_ingestion_sources,
        nvd_api_key_set=bool(cfg.nvd_api_key),
        backup_local_path=cfg.backup_local_path,
        backup_local_path_writable=_check_path_writable(cfg.backup_local_path),
        brand_app_name=cfg.brand_app_name,
        brand_tagline=cfg.brand_tagline,
        brand_primary_color=cfg.brand_primary_color,
        brand_logo_url=cfg.brand_logo_url,
        brand_favicon_url=cfg.brand_favicon_url,
        updated_at=cfg.updated_at,
    )


@router.get("/", response_model=AppConfigResponse, dependencies=[Depends(get_current_user)])
async def get_config(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppConfigResponse:
    """Return the current persisted configuration."""
    cfg = await repository.get(db)
    return _to_response(cfg)


@router.put(
    "/", response_model=AppConfigResponse, dependencies=[Depends(require_role(UserRole.admin))]
)
async def update_config(
    payload: AppConfigUpdateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppConfigResponse:
    """Merge-update configuration fields and persist."""
    cfg = await repository.get(db)

    # Build the set of changed fields from the request payload using
    # model_dump(exclude_none=True) to avoid manually maintaining field lists.
    # NOTE: Keep _FLOAT_FIELDS, _INT_FIELDS, _BOOL_FIELDS, _LIST_FIELDS, and
    # _STR_FIELDS in sync with AppConfigUpdateRequest if you add new fields.
    changed: dict[str, object] = {}
    for field in _FLOAT_FIELDS + _INT_FIELDS + _BOOL_FIELDS + _LIST_FIELDS + _STR_FIELDS:
        value = getattr(payload, field, None)
        if value is not None:
            changed[field] = value

    # Validate backup_local_path: must be non-empty, no null bytes, and
    # the server process must be able to write to it.
    if "backup_local_path" in changed:
        raw_path = str(changed["backup_local_path"]).strip()
        if not raw_path or "\x00" in raw_path:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail="backup_local_path must be a non-empty path",
            )
        if not _check_path_writable(raw_path):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail=f"Server cannot write to '{raw_path}'. "
                "Check that the directory exists and the server process "
                "has write permissions.",
            )
        changed["backup_local_path"] = raw_path

    # Build an updated copy and persist — only replace the in-memory config
    # object after the DB write succeeds to avoid inconsistency on failure.
    updated_cfg = cfg.model_copy(update=changed)
    saved = await repository.save(db, updated_cfg)

    if changed:
        await audit(
            db,
            domain="config",
            action="config.updated",
            actor=user.sub,
            summary=f"Config updated: {', '.join(f'{k}={v}' for k, v in changed.items())}",
            details={"changes": changed},
        )

    return _to_response(saved)


# ── Public branding endpoint (no auth required) ─────────────────────────────

branding_router = APIRouter()


@branding_router.get("/", response_model=BrandingResponse)
async def get_branding(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> BrandingResponse:
    """Return public branding configuration (no authentication required).

    This endpoint is called by the frontend before login to display
    custom branding on the login page.
    """
    cfg = await repository.get(db)
    return BrandingResponse(
        app_name=cfg.brand_app_name,
        tagline=cfg.brand_tagline,
        primary_color=cfg.brand_primary_color,
        logo_url=cfg.brand_logo_url,
        favicon_url=cfg.brand_favicon_url,
    )
