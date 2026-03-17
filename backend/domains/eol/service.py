"""EOL domain service.

Orchestrates EOL data sync from endoflife.date, product matching, and
provides the public API for the EOL domain.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import httpx
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.eol import repository
from domains.eol.matching import run_eol_matching
from utils.ws_broadcast import WsBroadcaster

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EOL_API_BASE = "https://endoflife.date/api/v1"
MAX_REQUESTS_PER_SECOND = 3
_REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND  # ~0.33s between requests
_BROADCAST_INTERVAL = 10  # broadcast every N products

# Module-level sync state
_sync_running = False
_sync_status: dict[str, Any] = {"status": "idle", "message": ""}

# WebSocket broadcaster — shared across the module, connected clients
# receive real-time progress during EOL sync.
ws = WsBroadcaster("eol_sync")

BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]


# ---------------------------------------------------------------------------
# Sync service
# ---------------------------------------------------------------------------


async def _broadcast_progress(msg: dict[str, Any]) -> None:
    """Broadcast a progress message to connected WebSocket clients.

    Also updates the module-level sync status for poll-based consumers.

    Args:
        msg: Progress message dict.
    """
    global _sync_status  # noqa: PLW0603
    _sync_status = {
        "status": msg.get("status", "running"),
        "message": msg.get("message", ""),
    }
    await ws.broadcast(msg)


async def sync_eol_data(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Sync EOL lifecycle data from endoflife.date.

    Fetches the product list, then lifecycle data for each product.
    Stores results in the ``eol_products`` collection.

    EOL matching is NOT run here — it runs automatically after the next
    S1 app sync via the post-sync chain (``rebuild_app_summaries`` →
    ``run_eol_matching_for_apps``).  EOL dates don't change between
    syncs, so matching on every EOL sync is wasteful.

    Logs to the shared ``library_ingestion_runs`` collection so the run
    appears in the Library Sources ingestion history alongside other
    sources (NIST CPE, MITRE, etc.).

    Args:
        db: Motor database handle.

    Returns:
        Summary dict with counts and status.
    """
    global _sync_running, _sync_status  # noqa: PLW0603

    if _sync_running:
        return {"status": "already_running", "message": "EOL sync is already in progress"}

    _sync_running = True

    # Create ingestion run record in the library DB
    from database import get_library_db
    from domains.library.entities import IngestionRun
    from domains.library.repository import insert_ingestion_run, update_ingestion_run

    library_db = get_library_db()
    run = IngestionRun(source="endoflife")
    await insert_ingestion_run(library_db, run)

    await _broadcast_progress(
        {
            "type": "progress",
            "source": "endoflife",
            "status": "running",
            "message": "Fetching product list...",
            "products_synced": 0,
            "products_failed": 0,
            "products_total": 0,
            "phase": "fetch_list",
        }
    )

    try:
        result = await _do_sync(db, broadcast=_broadcast_progress)

        synced = result.get("products_synced", 0)

        # Update ingestion run as completed
        from utils.dt import utc_now

        await update_ingestion_run(
            library_db,
            run.id,
            {
                "status": "completed",
                "completed_at": utc_now(),
                "entries_created": synced,
                "entries_updated": synced,
                "entries_skipped": result.get("products_failed", 0),
                "errors": result.get("errors", [])[:20],
            },
        )

        await _broadcast_progress(
            {
                "type": "completed",
                "source": "endoflife",
                "status": "completed",
                "message": f"Synced {synced} products. Matching runs on next app sync.",
                "products_synced": synced,
                "products_failed": result.get("products_failed", 0),
                "products_total": result.get("products_total", 0),
                "phase": "done",
            }
        )
        return result

    except Exception as exc:
        logger.error("EOL sync failed: {}", exc)

        # Update ingestion run as failed
        try:
            from utils.dt import utc_now

            await update_ingestion_run(
                library_db,
                run.id,
                {
                    "status": "failed",
                    "completed_at": utc_now(),
                    "errors": [str(exc)],
                },
            )
        except Exception:
            pass

        await _broadcast_progress(
            {
                "type": "failed",
                "source": "endoflife",
                "status": "failed",
                "message": str(exc),
                "products_synced": 0,
                "products_failed": 0,
                "products_total": 0,
                "phase": "error",
            }
        )
        return {"status": "failed", "message": str(exc)}
    finally:
        _sync_running = False


async def _do_sync(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    broadcast: BroadcastFn,
) -> dict[str, Any]:
    """Execute the actual EOL data sync.

    Args:
        db: Motor database handle.
        broadcast: Callback for progress updates.

    Returns:
        Summary with products_synced, products_failed, errors.
    """
    products_synced = 0
    products_failed = 0
    errors: list[str] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
    ) as client:
        # Fetch product list
        try:
            resp = await client.get(f"{EOL_API_BASE}/products/")
            resp.raise_for_status()
            raw_response = resp.json()
            # v1 API wraps in {"result": [...]}
            if isinstance(raw_response, dict) and "result" in raw_response:
                product_list = raw_response["result"]
            elif isinstance(raw_response, list):
                product_list = raw_response
            else:
                product_list = []
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to fetch EOL product list: {}", exc)
            # Use cached data — don't fail
            cached_count = await repository.get_product_count(db)
            if cached_count > 0:
                logger.info("Using {} cached EOL products", cached_count)
                return {
                    "status": "partial",
                    "message": f"API unreachable, using {cached_count} cached products",
                    "products_synced": 0,
                    "products_total": 0,
                }
            return {
                "status": "failed",
                "message": f"API unreachable and no cache: {exc}",
                "products_total": 0,
            }

        total = len(product_list)
        logger.info("EOL API returned {} products", total)

        await broadcast(
            {
                "type": "progress",
                "source": "endoflife",
                "status": "running",
                "message": f"Syncing 0/{total} products...",
                "products_synced": 0,
                "products_failed": 0,
                "products_total": total,
                "phase": "sync_products",
            }
        )

        # Fetch lifecycle data for each product
        for i, product_info in enumerate(product_list):
            if isinstance(product_info, str):
                product_id = product_info
                product_name = product_info
            else:
                product_id = product_info.get("name", product_info.get("id", ""))
                product_name = product_info.get("label", product_info.get("name", product_id))

            if not product_id:
                continue

            # Rate limiting
            if i > 0:
                await asyncio.sleep(_REQUEST_INTERVAL)

            try:
                resp = await client.get(f"{EOL_API_BASE}/products/{product_id}/")
                if resp.status_code == 429:
                    # Rate limited — back off and retry once
                    await asyncio.sleep(2.0)
                    resp = await client.get(f"{EOL_API_BASE}/products/{product_id}/")

                if resp.status_code == 404:
                    continue

                resp.raise_for_status()
                raw_product = resp.json()

                # v1 API wraps in {"result": {...}} with "releases" key
                if isinstance(raw_product, dict) and "result" in raw_product:
                    product_data = raw_product["result"]
                    releases = product_data.get("releases", [])
                    # Update product_name from canonical label if available
                    product_name = product_data.get("label", product_name)
                elif isinstance(raw_product, list):
                    releases = raw_product
                else:
                    releases = raw_product.get("releases", [])

                # Parse releases into normalized cycles
                cycles = _parse_cycles(releases)

                await repository.upsert_product(db, product_id, product_name, cycles)
                products_synced += 1

            except (httpx.HTTPError, Exception) as exc:
                products_failed += 1
                if products_failed <= 10:
                    errors.append(f"{product_id}: {exc}")
                logger.debug("Failed to fetch EOL data for {}: {}", product_id, exc)

            # Broadcast progress every N products
            if (i + 1) % _BROADCAST_INTERVAL == 0 or i == total - 1:
                await broadcast(
                    {
                        "type": "progress",
                        "source": "endoflife",
                        "status": "running",
                        "message": f"Syncing {i + 1}/{total} products...",
                        "products_synced": products_synced,
                        "products_failed": products_failed,
                        "products_total": total,
                        "phase": "sync_products",
                    }
                )

    logger.info(
        "EOL sync complete: {} synced, {} failed",
        products_synced,
        products_failed,
    )

    return {
        "status": "completed",
        "products_synced": products_synced,
        "products_failed": products_failed,
        "products_total": total,
        "errors": errors,
    }


def _parse_cycles(releases_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw release/cycle data from the endoflife.date v1 API.

    Normalizes field names from the v1 format (``eolFrom``, ``eoasFrom``,
    ``isLts``) to our internal storage format.

    Args:
        releases_raw: Raw release dicts from the API response.

    Returns:
        Normalized cycle dicts ready for storage.
    """
    today = date.today()
    cycles = []

    for raw in releases_raw:
        cycle_name = str(raw.get("name", raw.get("cycle", "")))
        if not cycle_name:
            continue

        # v1 API uses eolFrom/eoasFrom (dates), isEol/isEoas (booleans)
        # Fall back to legacy field names (eol/support) for compatibility
        eol_date = _parse_date_field(raw.get("eolFrom", raw.get("eol")))
        support_end = _parse_date_field(raw.get("eoasFrom", raw.get("support")))
        release_date = _parse_date_field(raw.get("releaseDate", raw.get("date")))

        # Handle "latest" field (can be string or dict)
        latest = raw.get("latest", {})
        if isinstance(latest, dict):
            latest_version = latest.get("name", latest.get("version"))
            latest_date = _parse_date_field(latest.get("date"))
        else:
            latest_version = str(latest) if latest else None
            latest_date = None

        # Use API-provided booleans if available, else compute from dates
        is_eol = raw.get("isEol", bool(eol_date and eol_date < today))
        is_eoas = raw.get(
            "isEoas",
            bool(support_end and support_end < today and (not eol_date or eol_date >= today)),
        )

        cycles.append(
            {
                "cycle": cycle_name,
                "release_date": release_date.isoformat() if release_date else None,
                "support_end": support_end.isoformat() if support_end else None,
                "eol_date": eol_date.isoformat() if eol_date else None,
                "lts": bool(raw.get("isLts", raw.get("lts", False))),
                "latest_version": latest_version,
                "latest_version_date": (latest_date.isoformat() if latest_date else None),
                "is_eol": bool(is_eol),
                "is_security_only": bool(is_eoas),
            }
        )

    return cycles


def _parse_date_field(value: str | date | bool | None) -> date | None:
    """Parse a date field from the endoflife.date API.

    Args:
        value: Raw value (ISO string, bool, or None).

    Returns:
        Parsed date or ``None``.
    """
    if value is None or value is False or value is True:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, date):
        return value
    return None


def get_sync_status() -> dict[str, Any]:
    """Return the current EOL sync status.

    Returns:
        Status dict with ``status`` and ``message`` keys.
    """
    return dict(_sync_status)


async def run_eol_matching_for_apps(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    delta_only: bool = False,
    changed_app_names: list[str] | None = None,
) -> int:
    """Run EOL matching for apps (called after S1 sync or EOL sync).

    Args:
        db: Motor database handle.
        delta_only: Only match new/changed apps.
        changed_app_names: Specific app names to match.

    Returns:
        Number of apps matched.
    """
    eol_products = await repository.get_all_products_with_cycles(db)
    if not eol_products:
        logger.debug("No EOL products available, skipping matching")
        return 0

    return await run_eol_matching(
        db,
        eol_products,
        delta_only=delta_only,
        changed_app_names=changed_app_names,
    )
