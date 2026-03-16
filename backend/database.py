"""MongoDB connection management using Motor (async driver).

Provides a single Motor AsyncIOMotorClient instance and helpers to obtain
the application database. Call ``connect_db()`` on startup and
``close_db()`` on shutdown via FastAPI lifespan events.

Supports replica set connections with configurable read preference,
write concern, and connection pool settings for high-availability deployments.
"""

from __future__ import annotations

import contextlib

from fastapi import Request
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import WriteConcern

from config import get_settings

_client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]

_VALID_READ_PREFERENCES = {
    "primary",
    "primaryPreferred",
    "secondaryPreferred",
    "secondary",
    "nearest",
}


async def connect_db() -> None:
    """Open the Motor connection pool.

    Should be called once during application startup (FastAPI lifespan).
    Logs a warning if MongoDB is unreachable but does not crash the process —
    the app starts in a degraded state and DB-dependent endpoints return 503.

    Connection pool and replica set settings are read from config.
    """
    global _client
    settings = get_settings()
    logger.info("Connecting to MongoDB at {} / {}", settings.mongo_uri_safe, settings.mongo_db)

    # Build write concern
    w_value: int | str = settings.mongo_write_concern_w
    with contextlib.suppress(ValueError):
        w_value = int(settings.mongo_write_concern_w)
    write_concern = WriteConcern(w=w_value, j=settings.mongo_write_concern_j)

    # Resolve read preference (PyMongo expects the camelCase string)
    read_pref_input = settings.mongo_read_preference.strip()
    read_pref = next(
        (v for v in _VALID_READ_PREFERENCES if v.lower() == read_pref_input.lower()),
        "primary",
    )

    _client = AsyncIOMotorClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=3_000,
        maxPoolSize=settings.mongo_max_pool_size,
        minPoolSize=settings.mongo_min_pool_size,
        maxIdleTimeMS=settings.mongo_max_idle_time_ms,
        readPreference=read_pref,
        w=write_concern.document.get("w", "majority"),
        journal=write_concern.document.get("j", True),
    )
    try:
        await _client.admin.command("ping")
        logger.info("MongoDB connection established")

        # Log replica set info if available
        try:
            rs_status = await _client.admin.command("replSetGetStatus")
            members = rs_status.get("members", [])
            primary = next(
                (m["name"] for m in members if m.get("stateStr") == "PRIMARY"), "unknown"
            )
            logger.info(
                "Replica set '{}' detected — {} members, primary={}",
                rs_status.get("set", "?"),
                len(members),
                primary,
            )
        except Exception:
            logger.debug("Not running in replica set mode (standalone MongoDB)")
    except Exception as exc:
        logger.warning(
            "MongoDB not reachable at {} — starting in degraded mode ({}). "
            "DB-dependent features will return 503 until the database is available.",
            settings.mongo_uri_safe,
            exc,
        )


async def close_db() -> None:
    """Close the Motor connection pool.

    Should be called during application shutdown (FastAPI lifespan).
    """
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")


class DatabaseUnavailableError(Exception):
    """Raised when the database client is not connected."""


def get_client() -> AsyncIOMotorClient:  # type: ignore[type-arg]
    """Return the raw Motor client for advanced operations.

    Returns:
        The Motor AsyncIOMotorClient instance.

    Raises:
        DatabaseUnavailableError: If MongoDB is not connected.
    """
    if _client is None:
        raise DatabaseUnavailableError(
            "MongoDB is not reachable — start MongoDB and restart the backend"
        )
    return _client


def get_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Return the application database handle.

    Returns:
        Motor AsyncIOMotorDatabase for the configured database name.

    Raises:
        DatabaseUnavailableError: If MongoDB is not reachable.
    """
    if _client is None:
        raise DatabaseUnavailableError(
            "MongoDB is not reachable — start MongoDB and restart the backend"
        )
    return _client[get_settings().mongo_db]


def get_tenant_db(request: Request) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Return the tenant-specific database for the current request.

    When multi-tenancy is enabled, reads the database name from
    ``request.state.tenant_db_name`` (set by TenantMiddleware).
    When disabled, falls back to the default application database.

    This is a FastAPI dependency — use ``Depends(get_tenant_db)`` in routers.
    """
    if _client is None:
        raise DatabaseUnavailableError(
            "MongoDB is not reachable — start MongoDB and restart the backend"
        )
    db_name = getattr(getattr(request, "state", None), "tenant_db_name", None)
    if not db_name and get_settings().multi_tenancy_enabled:
        raise DatabaseUnavailableError(
            "Tenant context not resolved — request may have bypassed TenantMiddleware"
        )
    if db_name:
        return _client[db_name]
    return _client[get_settings().mongo_db]


def get_master_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Return the master database for tenant registry and cross-tenant ops.

    Returns:
        Motor AsyncIOMotorDatabase for the master database.

    Raises:
        DatabaseUnavailableError: If MongoDB is not connected.
    """
    if _client is None:
        raise DatabaseUnavailableError(
            "MongoDB is not reachable — start MongoDB and restart the backend"
        )
    return _client[get_settings().master_db_name]


def get_library_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Return the shared library database.

    When multi-tenancy is enabled, library entries and ingestion runs are stored
    in the master database so they are shared across all tenants.
    When multi-tenancy is disabled, falls back to the default application database.

    Returns:
        Motor AsyncIOMotorDatabase for library data.

    Raises:
        DatabaseUnavailableError: If MongoDB is not connected.
    """
    if _client is None:
        raise DatabaseUnavailableError(
            "MongoDB is not reachable — start MongoDB and restart the backend"
        )
    settings = get_settings()
    if settings.multi_tenancy_enabled:
        return _client[settings.master_db_name]
    return _client[settings.mongo_db]


async def check_replica_set_status() -> dict | None:
    """Check replica set status if running in replica set mode.

    Returns:
        A dict with set name, member count, primary, and member details,
        or None if not running in replica set mode.
    """
    if _client is None:
        return None
    try:
        rs_status = await _client.admin.command("replSetGetStatus")
        members = []
        for m in rs_status.get("members", []):
            members.append(
                {
                    "name": m.get("name"),
                    "state": m.get("stateStr"),
                    "health": m.get("health"),
                    "uptime": m.get("uptime"),
                }
            )
        primary = next((m["name"] for m in members if m.get("state") == "PRIMARY"), None)
        return {
            "set_name": rs_status.get("set"),
            "member_count": len(members),
            "primary": primary,
            "members": members,
            "ok": rs_status.get("ok"),
        }
    except Exception:
        return None
