"""Atomic first-user claim logic.

The first user to register (via local registration or SSO provisioning)
is automatically promoted to admin (on-prem) or super_admin (SaaS).

This module provides a single ``claim_first_user`` function that
atomically checks and claims first-user status using MongoDB's
find_one_and_update with upsert, preventing TOCTOU races when two
registrations arrive simultaneously.
"""

from __future__ import annotations

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import get_settings
from utils.dt import utc_now

from .entities import UserRole


async def claim_first_user(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
) -> UserRole:
    """Atomically claim first-user status and return the appropriate role.

    If this is the first user ever registered, claims the first-user slot
    and returns ``UserRole.admin`` (on-prem) or ``UserRole.super_admin`` (SaaS).
    Otherwise returns ``UserRole.viewer``.

    The claim is atomic: uses MongoDB ``find_one_and_update`` with ``upsert=True``
    on a unique ``_id`` to prevent two concurrent registrations from both
    receiving elevated privileges.

    Args:
        db: Motor database handle.
        username: The username of the registering user (for audit trail).

    Returns:
        The role to assign to the new user.
    """
    try:
        claimed = await db["system_config"].find_one_and_update(
            {"_id": "first_user_claimed", "claimed": {"$ne": True}},
            {
                "$set": {
                    "claimed": True,
                    "claimed_by": username,
                    "claimed_at": utc_now(),
                }
            },
            upsert=True,
            return_document=ReturnDocument.BEFORE,
        )
        is_first_user = claimed is None or not claimed.get("claimed")
    except DuplicateKeyError:
        is_first_user = False

    if is_first_user:
        settings = get_settings()
        role = UserRole.admin if settings.is_onprem else UserRole.super_admin
        logger.info("First user '{}' auto-promoted to {}", username, role.value)
        return role

    return UserRole.viewer
