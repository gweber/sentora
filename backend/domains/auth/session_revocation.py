"""In-memory cache of revoked session IDs for fast JWT rejection.

Similar to ``utils.user_revocation`` but tracks individual session IDs
instead of usernames. This cache is checked on every authenticated request
(via the auth middleware) to immediately reject tokens whose session has
been revoked — without a database call.

The cache is refreshed periodically from MongoDB and also updated instantly
when sessions are revoked via the session service.

.. warning:: Per-process limitation in multi-worker deployments

   The ``mark_session_revoked`` / ``mark_sessions_revoked`` helpers update
   **only the current worker's in-memory frozenset**.  Other workers will
   not see the revocation until their next ``refresh_revoked_sessions``
   cycle completes — up to ``_REFRESH_INTERVAL_SECONDS`` (30 s) later.

   During this window, a revoked session can still be accepted by a
   different worker.  This is an acceptable trade-off: the MongoDB-backed
   periodic refresh guarantees eventual consistency, and the 30-second gap
   is short enough for most threat models.  If zero-gap revocation is
   required, replace this module with a shared cache (e.g. Redis pub/sub).
"""

from __future__ import annotations

import asyncio
import time

from loguru import logger

_REFRESH_INTERVAL_SECONDS: float = 30.0

# Thread-safe for asyncio — only mutated by a single coroutine.
_revoked_session_ids: frozenset[str] = frozenset()
_last_refresh: float = 0.0


def is_session_revoked(session_id: str) -> bool:
    """Check whether a session ID is in the revoked set.

    Args:
        session_id: The session identifier from the JWT ``sid`` claim.

    Returns:
        True if the session was revoked at the last cache refresh or
        via an immediate mark.
    """
    return session_id in _revoked_session_ids


async def refresh_revoked_sessions() -> None:
    """Refresh the revoked-session set from MongoDB.

    Queries the ``sessions`` collection for revoked (inactive) sessions
    that haven't expired yet and rebuilds the in-memory frozenset.
    """
    global _revoked_session_ids, _last_refresh  # noqa: PLW0603

    try:
        from database import get_db
        from utils.dt import utc_now

        db = get_db()
        now = utc_now()
        # Only cache recently revoked sessions (within the last 24 hours)
        # — older ones won't have valid JWTs anyway.
        from datetime import timedelta

        cutoff = now - timedelta(hours=24)
        cursor = db["sessions"].find(
            {"is_active": False, "revoked_at": {"$gt": cutoff}},
            {"session_id": 1, "_id": 0},
        )
        session_ids: set[str] = set()
        async for doc in cursor:
            if doc.get("session_id"):
                session_ids.add(doc["session_id"])
        _revoked_session_ids = frozenset(session_ids)
        _last_refresh = time.monotonic()
    except Exception as exc:
        logger.warning("Failed to refresh revoked-session cache: {}", exc)


async def refresh_revoked_sessions_loop() -> None:
    """Long-running background task that refreshes the cache periodically.

    Designed to be started as an ``asyncio.Task`` during application lifespan.
    """
    try:
        while True:
            await refresh_revoked_sessions()
            await asyncio.sleep(_REFRESH_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.debug("Revoked-session cache refresh loop stopped")
        raise


def mark_session_revoked(session_id: str) -> None:
    """Immediately add a session ID to the revoked set.

    Called by the session service when a session is revoked, providing
    instant invalidation without waiting for the next cache refresh.

    Args:
        session_id: The session identifier to revoke.
    """
    global _revoked_session_ids  # noqa: PLW0603
    _revoked_session_ids = _revoked_session_ids | {session_id}


def mark_sessions_revoked(session_ids: list[str]) -> None:
    """Immediately add multiple session IDs to the revoked set.

    Args:
        session_ids: List of session identifiers to revoke.
    """
    global _revoked_session_ids  # noqa: PLW0603
    _revoked_session_ids = _revoked_session_ids | frozenset(session_ids)
