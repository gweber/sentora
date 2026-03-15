"""Unit tests for the server-side session service.

Tests cover:
- Session creation
- Session listing
- Session revocation (single and bulk)
- Session validity checks
- Session cleanup
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase


@pytest_asyncio.fixture
async def db_with_session(test_db: AsyncIOMotorDatabase) -> tuple:
    """Create a session in the test database and return (db, session)."""
    from domains.auth.session_service import create_session

    session = await create_session(
        test_db,
        user_id="user123",
        username="testuser",
        tenant_id=None,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Test Browser",
        refresh_token_family="family123",
    )
    return test_db, session


class TestCreateSession:
    """Session creation."""

    @pytest.mark.asyncio
    async def test_create_session(self, test_db: AsyncIOMotorDatabase) -> None:
        """create_session returns a Session with all fields populated."""
        from domains.auth.session_service import create_session

        session = await create_session(
            test_db,
            user_id="user1",
            username="alice",
            tenant_id=None,
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
            refresh_token_family="fam1",
        )
        assert session.id  # non-empty
        assert session.username == "alice"
        assert session.ip_address == "10.0.0.1"
        assert session.user_agent == "TestAgent/1.0"
        assert session.is_active is True
        assert session.revoked_at is None
        assert session.refresh_token_family == "fam1"

    @pytest.mark.asyncio
    async def test_session_persisted_in_db(self, test_db: AsyncIOMotorDatabase) -> None:
        """Session is stored in MongoDB."""
        from domains.auth.session_service import create_session

        session = await create_session(
            test_db,
            user_id="user1",
            username="bob",
            tenant_id=None,
            ip_address="10.0.0.2",
            user_agent="TestAgent/2.0",
            refresh_token_family="fam2",
        )
        doc = await test_db["sessions"].find_one({"session_id": session.id})
        assert doc is not None
        assert doc["username"] == "bob"


class TestListSessions:
    """Session listing."""

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, db_with_session: tuple) -> None:
        """list_user_sessions returns all active sessions for a user."""
        db, session = db_with_session
        from domains.auth.session_service import list_user_sessions

        sessions = await list_user_sessions(db, "testuser")
        assert len(sessions) >= 1
        assert sessions[0].username == "testuser"

    @pytest.mark.asyncio
    async def test_list_sessions_excludes_other_users(self, db_with_session: tuple) -> None:
        """Sessions from other users are not returned."""
        db, _ = db_with_session
        from domains.auth.session_service import list_user_sessions

        sessions = await list_user_sessions(db, "otheruser")
        assert len(sessions) == 0


class TestRevokeSession:
    """Session revocation."""

    @pytest.mark.asyncio
    async def test_revoke_session(self, db_with_session: tuple) -> None:
        """Revoking a session marks it as inactive."""
        db, session = db_with_session
        from domains.auth.session_service import get_session, revoke_session

        result = await revoke_session(db, session.id, reason="test_revoke")
        assert result is True

        revoked = await get_session(db, session.id)
        assert revoked is not None
        assert revoked.is_active is False
        assert revoked.revoked_reason == "test_revoke"

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_session(self, test_db: AsyncIOMotorDatabase) -> None:
        """Revoking a nonexistent session returns False."""
        from domains.auth.session_service import revoke_session

        result = await revoke_session(test_db, "nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_user_sessions(self, test_db: AsyncIOMotorDatabase) -> None:
        """Revoking all sessions for a user invalidates them all."""
        from domains.auth.session_service import (
            create_session,
            list_user_sessions,
            revoke_all_user_sessions,
        )

        # Create multiple sessions
        for i in range(3):
            await create_session(
                test_db,
                user_id=f"user_{i}",
                username="multiuser",
                tenant_id=None,
                ip_address=f"10.0.0.{i}",
                user_agent=f"Agent/{i}",
                refresh_token_family=f"fam_{i}",
            )

        count = await revoke_all_user_sessions(test_db, "multiuser", reason="test")
        assert count == 3

        active = await list_user_sessions(test_db, "multiuser", active_only=True)
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_revoke_all_excludes_current(self, test_db: AsyncIOMotorDatabase) -> None:
        """Revoking all sessions can exclude the current session."""
        from domains.auth.session_service import (
            create_session,
            list_user_sessions,
            revoke_all_user_sessions,
        )

        sessions = []
        for i in range(3):
            s = await create_session(
                test_db,
                user_id=f"user_{i}",
                username="excludetest",
                tenant_id=None,
                ip_address=f"10.0.0.{i}",
                user_agent=f"Agent/{i}",
                refresh_token_family=f"fam_{i}",
            )
            sessions.append(s)

        count = await revoke_all_user_sessions(
            test_db, "excludetest", reason="test", exclude_session_id=sessions[0].id,
        )
        assert count == 2

        active = await list_user_sessions(test_db, "excludetest", active_only=True)
        assert len(active) == 1
        assert active[0].id == sessions[0].id


class TestSessionRevocationCache:
    """In-memory session revocation cache."""

    def test_mark_and_check_revoked(self) -> None:
        """mark_session_revoked adds to the revoked set."""
        from domains.auth.session_revocation import (
            is_session_revoked,
            mark_session_revoked,
        )

        mark_session_revoked("test_sid_1")
        assert is_session_revoked("test_sid_1") is True
        assert is_session_revoked("test_sid_2") is False

    def test_mark_multiple_revoked(self) -> None:
        """mark_sessions_revoked adds multiple IDs at once."""
        from domains.auth.session_revocation import (
            is_session_revoked,
            mark_sessions_revoked,
        )

        mark_sessions_revoked(["batch_1", "batch_2", "batch_3"])
        assert is_session_revoked("batch_1") is True
        assert is_session_revoked("batch_2") is True
        assert is_session_revoked("batch_3") is True
