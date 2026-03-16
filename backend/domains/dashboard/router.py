"""Dashboard stats endpoints — served from pre-computed cache.

Stats are computed once after each sync and stored in ``dashboard_stats``.
On first load (no cache yet) the endpoint computes on demand and primes the
cache.  A manual ``POST /dashboard/refresh`` is also available.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.entities import UserRole
from middleware.auth import get_current_user, require_role

from .cache import (
    compute_apps,
    compute_fingerprinting,
    compute_fleet,
    refresh_all,
)

router = APIRouter()


_CACHE_TTL_SECONDS = 300  # 5 minutes


async def _from_cache_or_compute(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key: str,
    compute_fn: Callable[[AsyncIOMotorDatabase], Awaitable[dict[str, Any]]],  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Return cached dashboard stats for *key*, recomputing if stale.

    The cache is considered stale when the TTL has expired **or** a sync
    has completed more recently than the cached value was written.

    Args:
        db: Tenant MongoDB database handle.
        key: Cache document identifier (e.g. ``"fleet"``, ``"apps"``).
        compute_fn: Async callable that computes the stats dict from *db*.

    Returns:
        The (possibly freshly computed) stats dictionary.
    """
    from datetime import datetime

    from utils.dt import utc_now

    cached = await db["dashboard_stats"].find_one({"_id": key})
    if cached:
        computed_at = cached.get("computed_at")
        if computed_at:
            try:
                cached_time = datetime.fromisoformat(computed_at)
                age = (utc_now() - cached_time).total_seconds()
            except (ValueError, TypeError):
                age = _CACHE_TTL_SECONDS + 1  # treat unparseable as expired

            if age <= _CACHE_TTL_SECONDS:
                # Cache is fresh by TTL — but still recompute if a sync
                # finished after the cache was written.
                meta = await db["s1_sync_meta"].find_one({"_id": "global"})
                if meta:
                    synced_at = meta.get("agents_synced_at")
                    if synced_at and synced_at > computed_at:
                        pass  # sync is newer → fall through to recompute
                    else:
                        return cached["data"]
                else:
                    return cached["data"]

    # Compute and prime the cache
    now = utc_now()
    data = await compute_fn(db)
    await db["dashboard_stats"].replace_one(
        {"_id": key},
        {"_id": key, "data": data, "computed_at": now.isoformat()},
        upsert=True,
    )
    return data


@router.get("/fleet", dependencies=[Depends(get_current_user)])
async def get_fleet(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Return fleet overview stats (total agents, OS breakdown, etc.)."""
    return await _from_cache_or_compute(db, "fleet", compute_fleet)


@router.get("/apps", dependencies=[Depends(get_current_user)])
async def get_apps(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Return installed-application stats (top apps, publisher breakdown, etc.)."""
    return await _from_cache_or_compute(db, "apps", compute_apps)


@router.get("/fingerprinting", dependencies=[Depends(get_current_user)])
async def get_fingerprinting(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Return fingerprinting coverage stats (groups fingerprinted, marker counts, etc.)."""
    return await _from_cache_or_compute(db, "fingerprinting", compute_fingerprinting)


@router.post("/refresh", dependencies=[Depends(require_role(UserRole.admin))])
async def refresh_dashboard(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, str]:
    """Manually trigger a full dashboard cache recompute."""
    await refresh_all(db)
    return {"status": "refreshed"}
