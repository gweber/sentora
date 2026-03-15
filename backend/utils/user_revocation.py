"""In-memory cache of revoked/disabled usernames for stateless JWT gap mitigation.

Stateless JWTs cannot check the ``disabled`` flag in MongoDB on every request
without defeating the purpose of statelessness.  This module maintains a
lightweight in-memory set of revoked usernames that is refreshed periodically
from the ``users`` collection.

The cache bounds the window during which a disabled user can still use an
existing access token to at most ``_REFRESH_INTERVAL_SECONDS`` (default 30s)
instead of the full JWT expiry (default 15 minutes).

Usage::

    from utils.user_revocation import is_user_revoked, refresh_revoked_users

    # On every authenticated request (called by middleware/auth.py):
    if is_user_revoked(username):
        raise HTTPException(401)

    # Periodic background refresh (started in lifespan):
    asyncio.create_task(refresh_revoked_users_loop())
"""

from __future__ import annotations

import asyncio
import time

from loguru import logger

_REFRESH_INTERVAL_SECONDS: float = 30.0

# Thread-safe for asyncio — only mutated by a single coroutine.
_revoked_usernames: frozenset[str] = frozenset()
_last_refresh: float = 0.0


def is_user_revoked(username: str) -> bool:
    """Check whether a username is in the revoked/disabled set.

    Returns True if the user was disabled at the last cache refresh.
    """
    return username in _revoked_usernames


async def refresh_revoked_users() -> None:
    """Refresh the revoked-user set from MongoDB.

    Queries the ``users`` collection for disabled accounts and rebuilds
    the in-memory frozenset.  Safe to call from any coroutine.
    """
    global _revoked_usernames, _last_refresh  # noqa: PLW0603

    try:
        from database import get_db

        db = get_db()
        cursor = db["users"].find({"disabled": True}, {"username": 1, "_id": 0})
        usernames: set[str] = set()
        async for doc in cursor:
            if doc.get("username"):
                usernames.add(doc["username"])
        _revoked_usernames = frozenset(usernames)
        _last_refresh = time.monotonic()
    except Exception as exc:
        logger.warning("Failed to refresh revoked-user cache: {}", exc)


async def refresh_revoked_users_loop() -> None:
    """Long-running background task that refreshes the cache periodically.

    Designed to be started as an ``asyncio.Task`` during application lifespan.
    Handles ``CancelledError`` for graceful shutdown.
    """
    try:
        while True:
            await refresh_revoked_users()
            await asyncio.sleep(_REFRESH_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.debug("Revoked-user cache refresh loop stopped")
        raise


def mark_user_revoked(username: str) -> None:
    """Immediately add a username to the revoked set (called on disable/delete).

    This provides instant revocation without waiting for the next cache refresh.
    """
    global _revoked_usernames  # noqa: PLW0603
    _revoked_usernames = _revoked_usernames | {username}


def mark_user_restored(username: str) -> None:
    """Immediately remove a username from the revoked set (called on re-enable).

    This provides instant restoration without waiting for the next cache refresh.
    """
    global _revoked_usernames  # noqa: PLW0603
    _revoked_usernames = _revoked_usernames - {username}
