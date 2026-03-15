"""Server-side session registry for immediate token invalidation and device management.

Each login creates a session document in MongoDB. The session_id is embedded
as a ``sid`` claim in the JWT access token. On every authenticated request the
middleware checks an in-memory cache of revoked session IDs — if the session
has been revoked, the JWT is rejected immediately (not at refresh time).

This gives Sentora the ability to:
- List active sessions per user (device management like Google Account)
- Revoke individual sessions or all sessions at once
- Automatically invalidate sessions on password change or account disable
- Track session activity for anomaly detection
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from utils.dt import utc_now

from .entities import Session


def _generate_session_id() -> str:
    """Generate a cryptographically random session identifier."""
    return secrets.token_urlsafe(32)


def _doc_to_session(doc: dict[str, Any]) -> Session:
    """Convert a MongoDB session document to a Session entity.

    Args:
        doc: Raw MongoDB document from the ``sessions`` collection.

    Returns:
        Fully hydrated Session entity.
    """
    return Session(
        id=doc["session_id"],
        user_id=doc.get("user_id", ""),
        username=doc["username"],
        tenant_id=doc.get("tenant_id"),
        created_at=doc["created_at"],
        last_active_at=doc["last_active_at"],
        expires_at=doc["expires_at"],
        ip_address=doc.get("ip_address", ""),
        user_agent=doc.get("user_agent", ""),
        is_active=doc.get("is_active", True),
        revoked_at=doc.get("revoked_at"),
        revoked_reason=doc.get("revoked_reason"),
        refresh_token_family=doc.get("refresh_token_family", ""),
    )


async def create_session(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    user_id: str,
    username: str,
    tenant_id: str | None,
    ip_address: str,
    user_agent: str,
    refresh_token_family: str,
) -> Session:
    """Create a new server-side session.

    Called during every login flow (password, OIDC, SAML). The returned
    session_id is embedded in the JWT access token as the ``sid`` claim.

    Args:
        db: Motor database handle.
        user_id: MongoDB ObjectId of the user (as string).
        username: Username for display and lookup.
        tenant_id: Tenant context for multi-tenancy.
        ip_address: Client IP address.
        user_agent: Client User-Agent header.
        refresh_token_family: Token family ID linking session to refresh chain.

    Returns:
        The newly created Session entity.
    """
    settings = get_settings()
    now = utc_now()
    session_id = _generate_session_id()
    session_ttl_days = settings.session_max_lifetime_days

    doc: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "username": username,
        "tenant_id": tenant_id,
        "created_at": now,
        "last_active_at": now,
        "expires_at": now + timedelta(days=session_ttl_days),
        "ip_address": ip_address,
        "user_agent": user_agent,
        "is_active": True,
        "revoked_at": None,
        "revoked_reason": None,
        "refresh_token_family": refresh_token_family,
    }
    await db["sessions"].insert_one(doc)
    logger.debug("Session created: sid={} user={}", session_id[:8], username)
    return _doc_to_session(doc)


async def get_session(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    session_id: str,
) -> Session | None:
    """Look up a session by its ID.

    Args:
        db: Motor database handle.
        session_id: The session identifier.

    Returns:
        Session entity if found, None otherwise.
    """
    doc = await db["sessions"].find_one({"session_id": session_id})
    if not doc:
        return None
    return _doc_to_session(doc)


async def list_user_sessions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
    *,
    active_only: bool = True,
) -> list[Session]:
    """List all sessions for a user.

    Args:
        db: Motor database handle.
        username: Username to filter by.
        active_only: If True, only return active (non-revoked) sessions.

    Returns:
        List of Session entities sorted by last_active_at descending.
    """
    query: dict[str, Any] = {"username": username}
    if active_only:
        query["is_active"] = True
        query["expires_at"] = {"$gt": utc_now()}
    cursor = db["sessions"].find(query).sort("last_active_at", -1)
    sessions: list[Session] = []
    async for doc in cursor:
        sessions.append(_doc_to_session(doc))
    return sessions


async def revoke_session(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    session_id: str,
    reason: str = "user_revoked",
) -> bool:
    """Revoke a single session.

    Also revokes the associated refresh token family to prevent token refresh.

    Args:
        db: Motor database handle.
        session_id: Session to revoke.
        reason: Human-readable revocation reason.

    Returns:
        True if a session was revoked, False if not found.
    """
    now = utc_now()
    result = await db["sessions"].find_one_and_update(
        {"session_id": session_id, "is_active": True},
        {"$set": {"is_active": False, "revoked_at": now, "revoked_reason": reason}},
    )
    if not result:
        return False

    # Also revoke the associated refresh token family
    family = result.get("refresh_token_family")
    if family:
        await db["refresh_tokens"].delete_many({"family_id": family})

    # Update the in-memory revocation cache immediately
    from .session_revocation import mark_session_revoked

    mark_session_revoked(session_id)

    logger.info("Session revoked: sid={} reason={}", session_id[:8], reason)
    return True


async def revoke_all_user_sessions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
    reason: str = "all_sessions",
    *,
    exclude_session_id: str | None = None,
) -> int:
    """Revoke all active sessions for a user.

    Used on password change, account disable, or "logout everywhere".

    Args:
        db: Motor database handle.
        username: Username whose sessions to revoke.
        reason: Revocation reason.
        exclude_session_id: Optionally keep one session active (current device).

    Returns:
        Number of sessions revoked.
    """
    now = utc_now()
    query: dict[str, Any] = {"username": username, "is_active": True}
    if exclude_session_id:
        query["session_id"] = {"$ne": exclude_session_id}

    # Collect session IDs before revoking for cache update
    cursor = db["sessions"].find(query, {"session_id": 1, "refresh_token_family": 1})
    session_ids: list[str] = []
    family_ids: list[str] = []
    async for doc in cursor:
        session_ids.append(doc["session_id"])
        if doc.get("refresh_token_family"):
            family_ids.append(doc["refresh_token_family"])

    if not session_ids:
        return 0

    # Bulk revoke sessions
    result = await db["sessions"].update_many(
        {"session_id": {"$in": session_ids}},
        {"$set": {"is_active": False, "revoked_at": now, "revoked_reason": reason}},
    )

    # Revoke associated refresh token families
    if family_ids:
        await db["refresh_tokens"].delete_many({"family_id": {"$in": family_ids}})

    # Update in-memory cache
    from .session_revocation import mark_sessions_revoked

    mark_sessions_revoked(session_ids)

    logger.info(
        "Revoked {} session(s) for user '{}' (reason={})",
        result.modified_count,
        username,
        reason,
    )
    return result.modified_count


async def update_session_activity(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    session_id: str,
) -> None:
    """Update the last_active_at timestamp for a session.

    Called periodically (not on every request) to track session activity
    without excessive database writes.

    Args:
        db: Motor database handle.
        session_id: Session to update.
    """
    await db["sessions"].update_one(
        {"session_id": session_id, "is_active": True},
        {"$set": {"last_active_at": utc_now()}},
    )


async def is_session_valid(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    session_id: str,
) -> bool:
    """Check if a session is still active and not expired.

    Args:
        db: Motor database handle.
        session_id: Session to check.

    Returns:
        True if the session is active and not expired.
    """
    doc = await db["sessions"].find_one(
        {
            "session_id": session_id,
            "is_active": True,
            "expires_at": {"$gt": utc_now()},
        },
        {"_id": 1},
    )
    return doc is not None


async def cleanup_expired_sessions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> int:
    """Delete sessions that have passed their absolute expiry.

    This is a housekeeping operation. Active sessions past their expires_at
    are marked as revoked first, then old revoked sessions are deleted.

    Args:
        db: Motor database handle.

    Returns:
        Number of sessions cleaned up.
    """
    now = utc_now()

    # Mark expired but still-active sessions as revoked
    await db["sessions"].update_many(
        {"is_active": True, "expires_at": {"$lt": now}},
        {"$set": {"is_active": False, "revoked_at": now, "revoked_reason": "expired"}},
    )

    # Delete sessions revoked more than 30 days ago (retention period)
    cutoff = now - timedelta(days=30)
    result = await db["sessions"].delete_many(
        {"is_active": False, "revoked_at": {"$lt": cutoff}},
    )
    if result.deleted_count:
        logger.info("Cleaned up {} expired session(s)", result.deleted_count)
    return result.deleted_count
