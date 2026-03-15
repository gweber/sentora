"""Config domain router.

GET  /api/v1/config/     — return current persisted config
PUT  /api/v1/config/     — merge-update config and persist
GET  /api/v1/branding    — return public branding info (no auth)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from database import get_tenant_db
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
)
_LIST_FIELDS = ("library_ingestion_sources",)
_STR_FIELDS = (
    "brand_app_name",
    "brand_tagline",
    "brand_primary_color",
    "brand_logo_url",
    "brand_favicon_url",
    "nvd_api_key",
)


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
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> AppConfigResponse:
    """Merge-update configuration fields and persist."""
    cfg = await repository.get(db)

    changed: dict[str, object] = {}
    for field in _FLOAT_FIELDS + _INT_FIELDS + _BOOL_FIELDS + _LIST_FIELDS + _STR_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            changed[field] = value

    # Apply changes and persist — only mutate in-memory after DB write succeeds
    for field, value in changed.items():
        setattr(cfg, field, value)
    saved = await repository.save(db, cfg)

    if changed:
        await audit(
            db,
            domain="config",
            action="config.updated",
            actor="user",
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
