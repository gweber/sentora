"""Tests for the in-memory user revocation cache."""

from __future__ import annotations

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.user_revocation import (
    is_user_revoked,
    mark_user_restored,
    mark_user_revoked,
)


class TestUserRevocation:
    """Test the synchronous in-memory revocation set operations."""

    def setup_method(self) -> None:
        """Reset the global revocation state before each test."""
        import utils.user_revocation as mod

        mod._revoked_usernames = frozenset()

    def test_unknown_user_is_not_revoked(self) -> None:
        """An unknown username should not be considered revoked."""
        assert is_user_revoked("alice") is False

    def test_mark_user_revoked(self) -> None:
        """After marking a user revoked, is_user_revoked returns True."""
        mark_user_revoked("bob")
        assert is_user_revoked("bob") is True

    def test_mark_user_restored(self) -> None:
        """After marking a user restored, is_user_revoked returns False."""
        mark_user_revoked("carol")
        assert is_user_revoked("carol") is True
        mark_user_restored("carol")
        assert is_user_revoked("carol") is False

    def test_mark_revoked_is_additive(self) -> None:
        """Multiple revocations do not interfere with each other."""
        mark_user_revoked("dave")
        mark_user_revoked("eve")
        assert is_user_revoked("dave") is True
        assert is_user_revoked("eve") is True

    def test_mark_restored_only_affects_target(self) -> None:
        """Restoring one user does not restore others."""
        mark_user_revoked("frank")
        mark_user_revoked("grace")
        mark_user_restored("frank")
        assert is_user_revoked("frank") is False
        assert is_user_revoked("grace") is True


@pytest.mark.asyncio
async def test_refresh_revoked_users_populates_from_db(test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """refresh_revoked_users queries the users collection for disabled accounts."""
    import utils.user_revocation as mod
    from utils.user_revocation import refresh_revoked_users

    # Seed two users, one disabled
    await test_db["users"].insert_many(
        [
            {"username": "active_user", "email": "a@t.co", "disabled": False},
            {"username": "disabled_user", "email": "d@t.co", "disabled": True},
        ]
    )

    # Patch get_db to return test_db (not just the client — get_db reads settings.mongo_db)
    import database
    from config import get_settings

    prev_client = database._client
    database._client = test_db.client
    settings = get_settings()
    prev_mongo_db = settings.mongo_db
    object.__setattr__(settings, "mongo_db", test_db.name)
    try:
        await refresh_revoked_users()
        assert is_user_revoked("disabled_user") is True
        assert is_user_revoked("active_user") is False
    finally:
        database._client = prev_client
        object.__setattr__(settings, "mongo_db", prev_mongo_db)
        mod._revoked_usernames = frozenset()
