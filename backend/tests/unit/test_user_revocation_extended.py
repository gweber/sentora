"""Extended tests for user_revocation — covers refresh loop and error handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import utils.user_revocation as mod
from utils.user_revocation import (
    is_user_revoked,
    refresh_revoked_users,
    refresh_revoked_users_loop,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset module state before each test."""
    mod._revoked_usernames = frozenset()
    mod._last_refresh = 0.0


class TestRefreshWithDbError:
    """Test refresh_revoked_users gracefully handles DB errors."""

    @pytest.mark.asyncio
    async def test_refresh_swallows_db_exception(self) -> None:
        """When get_db raises, the cache stays unchanged (no crash)."""
        with patch("database.get_db", side_effect=RuntimeError("db down")):
            await refresh_revoked_users()
        # Should not crash; cache remains empty
        assert is_user_revoked("anyone") is False

    @pytest.mark.asyncio
    async def test_refresh_with_status_filter(self) -> None:
        """Users with suspended/deactivated/deleted status are revoked."""

        class FakeCursor:
            def __init__(self, docs: list) -> None:
                self._docs = docs
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx >= len(self._docs):
                    raise StopAsyncIteration
                doc = self._docs[self._idx]
                self._idx += 1
                return doc

        docs = [
            {"username": "suspended_user"},
            {"username": "deleted_user"},
            {"username": ""},  # empty username should be skipped
        ]

        mock_db = AsyncMock()
        mock_db.__getitem__ = lambda self, key: self
        mock_db.find = lambda *a, **kw: FakeCursor(docs)

        with patch("database.get_db", return_value=mock_db):
            await refresh_revoked_users()

        assert is_user_revoked("suspended_user") is True
        assert is_user_revoked("deleted_user") is True
        assert is_user_revoked("") is False


class TestRefreshLoop:
    """Test the background refresh loop."""

    @pytest.mark.asyncio
    async def test_loop_runs_and_cancels(self) -> None:
        """The loop should call refresh and stop cleanly on cancellation."""
        call_count = 0

        async def mock_refresh() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with patch("utils.user_revocation.refresh_revoked_users", side_effect=mock_refresh):
            with patch("utils.user_revocation._REFRESH_INTERVAL_SECONDS", 0.01):
                with pytest.raises(asyncio.CancelledError):
                    await refresh_revoked_users_loop()

        assert call_count >= 1
