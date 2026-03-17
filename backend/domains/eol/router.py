"""EOL domain router.

Admin endpoints for EOL data management: sync trigger, product browsing,
match review, and source status.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.websockets import WebSocketDisconnect

from database import get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.eol import repository, service
from domains.eol.dto import (
    ConfirmMatchRequest,
    EOLFuzzyMatchReviewItem,
    EOLFuzzyMatchReviewResponse,
    EOLProductListResponse,
    EOLProductResponse,
    EOLSourceInfoResponse,
    EOLSyncStatusResponse,
    NameMappingItem,
    NameMappingListResponse,
    UpsertNameMappingRequest,
)
from middleware.auth import get_current_user, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# WebSocket — real-time sync progress
# ---------------------------------------------------------------------------


@router.websocket("/sync/progress")
async def eol_sync_progress_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint — streams EOL sync progress to connected clients.

    Authenticates via the ``Sec-WebSocket-Protocol`` header (subprotocol
    ``bearer.<token>``) to prevent token leakage in logs.
    """
    from utils.ws_auth import authenticate_websocket

    payload = await authenticate_websocket(
        websocket,
        allowed_roles={UserRole.admin},
    )
    if payload is None:
        return

    service.ws.connect_accepted(websocket)

    # Send current status as initial snapshot
    status = service.get_sync_status()
    await service.ws.send_to(
        websocket,
        {
            "type": "snapshot",
            "source": "endoflife",
            **status,
        },
    )

    try:
        last_msg_time = 0.0
        while True:
            await websocket.receive_text()
            now = time.monotonic()
            if now - last_msg_time < 0.1:
                continue
            last_msg_time = now
    except WebSocketDisconnect:
        pass
    finally:
        service.ws.disconnect(websocket)


# ---------------------------------------------------------------------------
# Source info (for Library Sources UI)
# ---------------------------------------------------------------------------


@router.get(
    "/source",
    response_model=EOLSourceInfoResponse,
    summary="Get EOL source status",
)
async def get_source_info(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(get_current_user),
) -> EOLSourceInfoResponse:
    """Return status information for the endoflife.date library source.

    Used by the Library Sources UI to display the EOL source card
    alongside existing sources (NIST CPE, MITRE, etc.).

    Args:
        db: Tenant database handle.

    Returns:
        Source info including sync status, product count, and match stats.
    """
    last_synced = await repository.get_last_sync_time(db)
    total_products = await repository.get_product_count(db)
    matched_apps = await repository.get_matched_app_count(db)

    # Determine status based on last sync time
    status = "unknown"
    if last_synced:
        from utils.dt import ensure_utc, utc_now

        hours_since = (utc_now() - ensure_utc(last_synced)).total_seconds() / 3600
        if hours_since < 25:
            status = "healthy"
        elif hours_since < 48:
            status = "stale"
        else:
            status = "outdated"
    elif total_products == 0:
        status = "never_synced"

    # Count EOL cycles across all products
    total_eol_cycles = 0
    async for doc in db["eol_products"].find({}, {"cycles": 1}):
        for cycle in doc.get("cycles", []):
            if cycle.get("is_eol"):
                total_eol_cycles += 1

    return EOLSourceInfoResponse(
        last_synced=last_synced,
        total_products=total_products,
        total_eol_cycles=total_eol_cycles,
        matched_apps=matched_apps,
        status=status,
    )


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


@router.post(
    "/sync",
    response_model=EOLSyncStatusResponse,
    summary="Trigger EOL data sync",
)
async def trigger_sync(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> EOLSyncStatusResponse:
    """Trigger a manual EOL data sync from endoflife.date.

    Runs the sync in the background and returns immediately with status.
    Use ``GET /eol/sync/status`` to poll for completion.

    Args:
        db: Tenant database handle.

    Returns:
        Current sync status.
    """
    asyncio.create_task(service.sync_eol_data(db))

    return EOLSyncStatusResponse(
        status="running",
        message="EOL data sync started",
        total_products=await repository.get_product_count(db),
        last_synced=await repository.get_last_sync_time(db),
    )


@router.get(
    "/sync/status",
    response_model=EOLSyncStatusResponse,
    summary="Get EOL sync status",
)
async def get_sync_status(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(get_current_user),
) -> EOLSyncStatusResponse:
    """Return the current EOL sync status.

    Args:
        db: Tenant database handle.

    Returns:
        Sync status with product count and last sync time.
    """
    sync_state = service.get_sync_status()
    return EOLSyncStatusResponse(
        status=sync_state["status"],
        message=sync_state.get("message", ""),
        total_products=await repository.get_product_count(db),
        last_synced=await repository.get_last_sync_time(db),
    )


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get(
    "/products",
    response_model=EOLProductListResponse,
    summary="List EOL products",
)
async def list_products(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(get_current_user),
    search: str | None = Query(None, description="Search term for product name/ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> EOLProductListResponse:
    """List all synced EOL products with pagination and search.

    Args:
        db: Tenant database handle.
        search: Optional search filter.
        page: Page number.
        page_size: Page size.

    Returns:
        Paginated product list with cycle counts and match stats.
    """
    docs, total = await repository.list_products(db, search=search, page=page, page_size=page_size)

    products = []
    for doc in docs:
        cycles = doc.get("cycles", [])
        eol_count = sum(1 for c in cycles if c.get("is_eol"))

        # Count matched apps for this product
        matched_apps = await db["app_summaries"].count_documents(
            {"eol_match.eol_product_id": doc["product_id"]}
        )

        products.append(
            EOLProductResponse(
                product_id=doc["product_id"],
                name=doc.get("name", doc["product_id"]),
                last_synced=doc.get("last_synced"),
                total_cycles=len(cycles),
                eol_cycles=eol_count,
                matched_apps=matched_apps,
            )
        )

    return EOLProductListResponse(
        products=products,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/products/{product_id}",
    response_model=EOLProductResponse,
    summary="Get EOL product detail",
)
async def get_product(
    product_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(get_current_user),
) -> EOLProductResponse:
    """Return detail for a single EOL product including all cycles.

    Args:
        product_id: endoflife.date product slug.
        db: Tenant database handle.

    Returns:
        Product detail with full cycle data.

    Raises:
        HTTPException: 404 if product not found.
    """
    from fastapi import HTTPException

    doc = await repository.get_product(db, product_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"EOL product '{product_id}' not found")

    from domains.eol.dto import EOLCycleResponse

    cycles = doc.get("cycles", [])
    cycle_responses = [
        EOLCycleResponse(
            cycle=c.get("cycle", ""),
            release_date=c.get("release_date"),
            support_end=c.get("support_end"),
            eol_date=c.get("eol_date"),
            lts=c.get("lts", False),
            latest_version=c.get("latest_version"),
            latest_version_date=c.get("latest_version_date"),
            is_eol=c.get("is_eol", False),
            is_security_only=c.get("is_security_only", False),
        )
        for c in cycles
    ]

    matched_apps = await db["app_summaries"].count_documents(
        {"eol_match.eol_product_id": product_id}
    )

    return EOLProductResponse(
        product_id=doc["product_id"],
        name=doc.get("name", doc["product_id"]),
        cycles=cycle_responses,
        last_synced=doc.get("last_synced"),
        total_cycles=len(cycles),
        eol_cycles=sum(1 for c in cycles if c.get("is_eol")),
        matched_apps=matched_apps,
    )


# ---------------------------------------------------------------------------
# Match review
# ---------------------------------------------------------------------------


@router.get(
    "/matches/review",
    response_model=EOLFuzzyMatchReviewResponse,
    summary="List fuzzy matches for review",
)
async def list_fuzzy_matches(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> EOLFuzzyMatchReviewResponse:
    """List fuzzy EOL matches pending human review.

    Fuzzy matches are never auto-included in compliance results.
    They appear here for MSPs to confirm or dismiss.

    Args:
        db: Tenant database handle.
        page: Page number.
        page_size: Page size.

    Returns:
        Paginated list of fuzzy matches.
    """
    docs, total = await repository.get_fuzzy_matches_for_review(db, page=page, page_size=page_size)

    items = []
    for doc in docs:
        match = doc.get("eol_match", {})
        # Look up the product name
        product = await repository.get_product(db, match.get("eol_product_id", ""))
        product_name = product["name"] if product else match.get("eol_product_id", "")

        items.append(
            EOLFuzzyMatchReviewItem(
                app_name=doc.get("display_name", doc.get("normalized_name", "")),
                normalized_name=doc.get("normalized_name", ""),
                suggested_product_id=match.get("eol_product_id", ""),
                suggested_product_name=product_name,
                confidence=match.get("match_confidence", 0.0),
                agent_count=doc.get("agent_count", 0),
            )
        )

    return EOLFuzzyMatchReviewResponse(items=items, total=total)


@router.post(
    "/matches/review",
    summary="Confirm or dismiss a fuzzy match",
)
async def review_match(
    body: ConfirmMatchRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> dict[str, Any]:
    """Confirm or dismiss a fuzzy EOL match.

    Confirmed matches are promoted to ``match_source: manual`` and
    included in compliance checks.  Dismissed matches are removed.

    Args:
        body: Request with normalized_name, eol_product_id, and action.
        db: Tenant database handle.

    Returns:
        Status message.
    """
    if body.action == "confirm":
        ok = await repository.confirm_match(db, body.normalized_name, body.eol_product_id)
        return {"status": "confirmed" if ok else "not_found"}
    else:
        ok = await repository.dismiss_match(db, body.normalized_name)
        return {"status": "dismissed" if ok else "not_found"}


# ---------------------------------------------------------------------------
# Name mappings (app name prefix → EOL product)
# ---------------------------------------------------------------------------


@router.get(
    "/mappings",
    response_model=NameMappingListResponse,
    summary="List all name → EOL product mappings",
)
async def list_name_mappings(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(get_current_user),
) -> NameMappingListResponse:
    """Return all name mappings — both built-in and user-configured.

    Built-in mappings come from the static ``NAME_TO_EOL_MAP`` in code.
    Custom mappings are stored in the ``eol_name_mappings`` collection
    and override built-in ones when the same prefix exists.

    Args:
        db: Tenant database handle.

    Returns:
        Separate lists of built-in and custom mappings.
    """
    from domains.eol.matching import NAME_TO_EOL_MAP

    custom_docs = await repository.list_name_mappings(db)

    builtin = [
        NameMappingItem(app_name_prefix=k, eol_product_id=v)
        for k, v in sorted(NAME_TO_EOL_MAP.items())
    ]
    custom = [
        NameMappingItem(
            app_name_prefix=d["app_name_prefix"],
            eol_product_id=d["eol_product_id"],
            updated_at=d.get("updated_at"),
            created_at=d.get("created_at"),
        )
        for d in custom_docs
    ]

    return NameMappingListResponse(
        builtin=builtin,
        custom=custom,
        total_builtin=len(builtin),
        total_custom=len(custom),
    )


@router.put(
    "/mappings",
    summary="Create or update a name mapping",
)
async def upsert_name_mapping(
    body: UpsertNameMappingRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> dict[str, Any]:
    """Create or update a custom app name → EOL product mapping.

    The ``app_name_prefix`` is matched against normalized app names using
    prefix matching.  For example, ``"zscaler"`` matches all apps whose
    normalized name starts with ``"zscaler"``.

    Custom mappings override built-in ones when the same prefix exists.
    Changes take effect on the next S1 app sync (when EOL matching runs).

    Args:
        body: Mapping to create/update.
        db: Tenant database handle.

    Returns:
        Status message.
    """
    prefix = body.app_name_prefix.lower().strip()
    created = await repository.upsert_name_mapping(db, prefix, body.eol_product_id)
    return {"status": "created" if created else "updated", "app_name_prefix": prefix}


@router.delete(
    "/mappings/{app_name_prefix:path}",
    summary="Delete a name mapping",
)
async def delete_name_mapping(
    app_name_prefix: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    _user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> dict[str, Any]:
    """Delete a custom name mapping.

    Built-in mappings cannot be deleted — only user-created ones.
    To override a built-in mapping, create a custom mapping with the
    same prefix pointing to a different product (or to ``""`` to disable).

    Args:
        app_name_prefix: The mapping key to delete.
        db: Tenant database handle.

    Returns:
        Status message.
    """
    from urllib.parse import unquote

    prefix = unquote(app_name_prefix).lower().strip()
    deleted = await repository.delete_name_mapping(db, prefix)
    return {"status": "deleted" if deleted else "not_found"}
