"""Library FastAPI router.

Mounts at /api/v1/library. Provides endpoints for:
- Library entry CRUD (browse, create, update, delete, publish, deprecate)
- Group subscriptions (subscribe, unsubscribe, list, sync)
- Source ingestion (list sources, trigger/resume/cancel per source,
  view run history, WebSocket progress)
- Library statistics

Library entries and ingestion data are stored in the shared library database
(accessible to all tenants). Subscriptions and fingerprints are per-tenant.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from database import get_library_db, get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.library import repository, service
from domains.library.dto import (
    IngestionRunListResponse,
    IngestionRunResponse,
    LibraryEntryCreateRequest,
    LibraryEntryListResponse,
    LibraryEntryResponse,
    LibraryEntryUpdateRequest,
    LibraryStatsResponse,
    SourceInfo,
    SourceListResponse,
    SubscribeRequest,
    SubscriptionListResponse,
    SubscriptionResponse,
    TriggerAllRequest,
)
from domains.library.ingestion_manager import ADAPTERS, ingestion_manager
from errors import IngestionError
from middleware.auth import get_current_user, require_platform_role, require_role

router = APIRouter()


# ── Library entries (shared library DB) ──────────────────────────────────────


@router.get(
    "/",
    response_model=LibraryEntryListResponse,
    summary="Browse library entries",
    dependencies=[Depends(get_current_user)],
)
async def list_entries(
    status: str | None = Query(default="published"),
    source: str | None = Query(default=None),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> LibraryEntryListResponse:
    return await service.list_entries(
        library_db,
        status=status,
        source=source,
        category=category,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/stats",
    response_model=LibraryStatsResponse,
    summary="Library statistics",
    dependencies=[Depends(get_current_user)],
)
async def get_stats(
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> LibraryStatsResponse:
    return await service.get_stats(library_db, tenant_db)


@router.get(
    "/entries/{entry_id}",
    response_model=LibraryEntryResponse,
    summary="Get a library entry",
    dependencies=[Depends(get_current_user)],
)
async def get_entry(
    entry_id: str,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> LibraryEntryResponse:
    return await service.get_entry(library_db, entry_id)


@router.post(
    "/",
    response_model=LibraryEntryResponse,
    status_code=201,
    summary="Create a library entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def create_entry(
    body: LibraryEntryCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> LibraryEntryResponse:
    return await service.create_entry(library_db, body, submitted_by=user.sub)


@router.patch(
    "/entries/{entry_id}",
    response_model=LibraryEntryResponse,
    summary="Update a library entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def update_entry(
    entry_id: str,
    body: LibraryEntryUpdateRequest,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> LibraryEntryResponse:
    return await service.update_entry(library_db, entry_id, body)


@router.delete(
    "/entries/{entry_id}",
    status_code=204,
    summary="Delete a library entry",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def delete_entry(
    entry_id: str,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> None:
    await service.delete_entry(library_db, tenant_db, entry_id)


@router.post(
    "/entries/{entry_id}/publish",
    response_model=LibraryEntryResponse,
    summary="Publish a library entry",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def publish_entry(
    entry_id: str,
    user: TokenPayload = Depends(get_current_user),
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> LibraryEntryResponse:
    return await service.publish_entry(library_db, entry_id, reviewer=user.sub)


@router.post(
    "/entries/{entry_id}/deprecate",
    response_model=LibraryEntryResponse,
    summary="Deprecate a library entry",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def deprecate_entry(
    entry_id: str,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> LibraryEntryResponse:
    return await service.deprecate_entry(library_db, entry_id)


class PromoteToTaxonomyRequest(BaseModel):
    """Optional overrides when promoting a library entry to taxonomy."""

    category: str | None = Field(default=None, description="Taxonomy category key override")


@router.get(
    "/entries/{entry_id}/promote-preview",
    summary="Preview what promoting this entry to taxonomy would do",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def promote_preview(
    entry_id: str,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Preview the taxonomy mapping without creating anything.

    Returns the proposed category, patterns, and whether it would
    create a new entry or merge into an existing one.
    """
    return await service.promote_preview(library_db, tenant_db, entry_id)


@router.post(
    "/entries/{entry_id}/promote-to-taxonomy",
    status_code=201,
    summary="Promote a library entry to the taxonomy catalog",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def promote_to_taxonomy(
    entry_id: str,
    body: PromoteToTaxonomyRequest = PromoteToTaxonomyRequest(),
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Convert a library entry into a taxonomy entry.

    Creates a new taxonomy entry with the library entry's name, vendor,
    patterns (from markers), and description.  If a taxonomy entry with
    the same name already exists, its patterns are merged.

    Pass ``category`` in the body to override the default category mapping.
    """
    return await service.promote_to_taxonomy(
        library_db,
        tenant_db,
        entry_id,
        user.sub,
        category_override=body.category,
    )


# ── Subscriptions (library_db for entries, tenant_db for subscriptions) ──────


@router.post(
    "/entries/{entry_id}/subscribe",
    response_model=SubscriptionResponse,
    status_code=201,
    summary="Subscribe a group to a library entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def subscribe(
    entry_id: str,
    body: SubscribeRequest,
    user: TokenPayload = Depends(get_current_user),
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SubscriptionResponse:
    return await service.subscribe(
        library_db,
        tenant_db,
        entry_id,
        body.group_id,
        subscribed_by=user.sub,
        auto_update=body.auto_update,
    )


@router.delete(
    "/entries/{entry_id}/subscribe/{group_id}",
    status_code=204,
    summary="Unsubscribe a group from a library entry",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def unsubscribe(
    entry_id: str,
    group_id: str,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> None:
    await service.unsubscribe(library_db, tenant_db, entry_id, group_id)


@router.get(
    "/subscriptions/group/{group_id}",
    response_model=SubscriptionListResponse,
    summary="List subscriptions for a group",
    dependencies=[Depends(get_current_user)],
)
async def list_group_subscriptions(
    group_id: str,
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SubscriptionListResponse:
    return await service.list_subscriptions_by_group(library_db, tenant_db, group_id)


@router.post(
    "/subscriptions/sync",
    summary="Sync all stale subscriptions",
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def sync_subscriptions(
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    count = await service.sync_stale_subscriptions(library_db, tenant_db)
    return {"synced": count}


# ── Ingestion (shared library DB, super_admin only) ─────────────────────────


@router.websocket("/sources/progress")
async def ingestion_progress_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint — streams IngestionProgressMessage JSON to all clients.

    Authenticates via the ``Sec-WebSocket-Protocol`` header (subprotocol
    ``bearer.<token>``) to prevent token leakage in logs. Incoming messages
    are discarded; a simple rate limit prevents flooding.
    """
    from utils.ws_auth import authenticate_websocket

    payload = await authenticate_websocket(
        websocket,
        allowed_roles={UserRole.admin},
    )
    if payload is None:
        return

    import time

    await ingestion_manager.connect_accepted(websocket)
    try:
        last_msg_time = 0.0
        while True:
            await websocket.receive_text()
            now = time.monotonic()
            if now - last_msg_time < 0.1:  # max 10 msg/s per client
                continue
            last_msg_time = now
    except WebSocketDisconnect:
        pass
    finally:
        ingestion_manager.disconnect(websocket)


@router.get(
    "/sources/",
    response_model=SourceListResponse,
    summary="List available ingestion sources",
    dependencies=[Depends(require_platform_role())],
)
async def list_sources(
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> SourceListResponse:
    sources: list[SourceInfo] = []
    for name, adapter in ADAPTERS.items():
        runner = ingestion_manager.get_runner(name)
        last_run = await repository.get_last_run_for_source(library_db, name)
        run_resp = None
        if last_run:
            run_resp = IngestionRunResponse(
                id=last_run.id,
                source=last_run.source,
                status=last_run.status,
                started_at=last_run.started_at.isoformat(),
                completed_at=last_run.completed_at.isoformat() if last_run.completed_at else None,
                entries_created=last_run.entries_created,
                entries_updated=last_run.entries_updated,
                entries_skipped=last_run.entries_skipped,
                errors=last_run.errors,
            )
        sources.append(
            SourceInfo(
                name=name,
                description=adapter.description,
                status=runner.status if runner else "idle",
                last_run=run_resp,
            )
        )
    return SourceListResponse(sources=sources)


@router.get(
    "/sources/status",
    summary="Per-source ingestion status",
    dependencies=[Depends(require_platform_role())],
)
async def source_status() -> dict:
    return ingestion_manager.source_status()


@router.post(
    "/sources/{source}/ingest",
    summary="Trigger an ingestion run for a single source",
    dependencies=[Depends(require_platform_role())],
)
async def trigger_ingestion(
    source: str,
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Trigger an ingestion run for a single source.

    Loads source-specific config from the persisted AppConfig (e.g. the NVD
    API key for ``nist_cpe``) and passes it to the adapter.
    """
    if source not in ADAPTERS:
        raise IngestionError(f"Unknown source: {source}")

    runner = ingestion_manager.get_runner(source)
    if runner and runner.is_running:
        raise IngestionError(f"Source {source} is already running")

    # Load persisted config for source-specific settings
    config: dict[str, Any] = {}
    try:
        from domains.config import repository as config_repo

        cfg = await config_repo.get(tenant_db)
        if source == "nist_cpe" and cfg.nvd_api_key:
            config["api_key"] = cfg.nvd_api_key
    except Exception as exc:
        from loguru import logger as _logger

        _logger.warning("Could not load source config for '{}': {}", source, exc)

    result = await ingestion_manager.trigger_source(source, config=config)
    if result is None:
        raise IngestionError(f"Could not start {source} (lock held or already running)")

    return {"status": "started", "source": source}


@router.post(
    "/sources/{source}/resume",
    summary="Resume an interrupted ingestion from checkpoint",
    dependencies=[Depends(require_platform_role())],
)
async def resume_ingestion(
    source: str,
) -> dict:
    if source not in ADAPTERS:
        raise IngestionError(f"Unknown source: {source}")

    result = await ingestion_manager.resume_source(source)
    if result is None:
        raise IngestionError(f"No checkpoint to resume for {source}")

    return {"status": "resumed", "source": source}


@router.post(
    "/sources/{source}/cancel",
    summary="Cancel a running ingestion",
    dependencies=[Depends(require_platform_role())],
)
async def cancel_ingestion(
    source: str,
) -> dict:
    if source not in ADAPTERS:
        raise IngestionError(f"Unknown source: {source}")

    cancelled = await ingestion_manager.cancel_source(source)
    if not cancelled:
        raise IngestionError(f"Source {source} is not running")

    return {"status": "cancelling", "source": source}


@router.post(
    "/sources/trigger-all",
    summary="Trigger ingestion for all (or selected) sources in parallel",
    dependencies=[Depends(require_platform_role())],
)
async def trigger_all(
    body: TriggerAllRequest | None = None,
    tenant_db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict:
    """Trigger ingestion for all or selected sources in parallel."""
    sources = body.sources if body else None

    # Load persisted config — only include api_key for nist_cpe to avoid
    # leaking secrets to unrelated source adapters and their checkpoints.
    nvd_api_key: str | None = None
    try:
        from domains.config import repository as config_repo

        cfg = await config_repo.get(tenant_db)
        if cfg.nvd_api_key:
            nvd_api_key = cfg.nvd_api_key
    except Exception as exc:
        from loguru import logger as _logger

        _logger.warning("Could not load source config for trigger-all: {}", exc)

    per_source_config: dict[str, dict[str, Any]] = {}
    if nvd_api_key:
        per_source_config["nist_cpe"] = {"api_key": nvd_api_key}

    result = await ingestion_manager.trigger_all(
        sources=sources,
        per_source_config=per_source_config,
    )
    return result


@router.post(
    "/sources/resume-all",
    summary="Resume all sources with pending checkpoints",
    dependencies=[Depends(require_platform_role())],
)
async def resume_all() -> dict:
    return await ingestion_manager.resume_all()


@router.post(
    "/sources/cancel-all",
    summary="Cancel all running ingestion sources",
    dependencies=[Depends(require_platform_role())],
)
async def cancel_all() -> dict:
    cancelled = await ingestion_manager.cancel_all()
    return {"cancelled": cancelled}


@router.get(
    "/ingestion-runs/",
    response_model=IngestionRunListResponse,
    summary="List ingestion run history",
    dependencies=[Depends(require_platform_role())],
)
async def list_ingestion_runs(
    source: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    library_db: AsyncIOMotorDatabase = Depends(get_library_db),  # type: ignore[type-arg]
) -> IngestionRunListResponse:
    runs = await repository.list_ingestion_runs(library_db, source=source, limit=limit)
    return IngestionRunListResponse(
        runs=[
            IngestionRunResponse(
                id=r.id,
                source=r.source,
                status=r.status,
                started_at=r.started_at.isoformat(),
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                entries_created=r.entries_created,
                entries_updated=r.entries_updated,
                entries_skipped=r.entries_skipped,
                errors=r.errors,
            )
            for r in runs
        ],
        total=len(runs),
    )
