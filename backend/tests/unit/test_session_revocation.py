"""Tests for session revocation cache."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import domains.auth.session_revocation as mod
from domains.auth.session_revocation import (
    is_session_revoked,
    mark_session_revoked,
    mark_sessions_revoked,
    refresh_revoked_sessions,
    refresh_revoked_sessions_loop,
)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    mod._revoked_session_ids = frozenset()
    mod._last_refresh = 0.0


class TestSessionRevocation:
    def test_unknown_session_not_revoked(self) -> None:
        assert is_session_revoked("sess_abc") is False

    def test_mark_session_revoked(self) -> None:
        mark_session_revoked("sess_123")
        assert is_session_revoked("sess_123") is True

    def test_mark_sessions_revoked_batch(self) -> None:
        mark_sessions_revoked(["sess_a", "sess_b", "sess_c"])
        assert is_session_revoked("sess_a") is True
        assert is_session_revoked("sess_b") is True
        assert is_session_revoked("sess_c") is True
        assert is_session_revoked("sess_d") is False

    def test_mark_single_doesnt_affect_others(self) -> None:
        mark_session_revoked("sess_x")
        mark_session_revoked("sess_y")
        assert is_session_revoked("sess_x") is True
        assert is_session_revoked("sess_y") is True


class TestRefreshFromDb:
    @pytest.mark.asyncio
    async def test_refresh_populates_from_db(self) -> None:
        class FakeCursor:
            def __init__(self, docs):
                self._docs = iter(docs)
            def __aiter__(self):
                return self
            async def __anext__(self):
                try:
                    return next(self._docs)
                except StopIteration:
                    raise StopAsyncIteration

        mock_db = AsyncMock()
        collection = AsyncMock()
        collection.find = lambda *a, **kw: FakeCursor([
            {"session_id": "revoked_1"},
            {"session_id": "revoked_2"},
            {"session_id": ""},  # empty should be skipped
        ])
        mock_db.__getitem__ = lambda self, key: collection

        with patch("database.get_db", return_value=mock_db):
            await refresh_revoked_sessions()

        assert is_session_revoked("revoked_1") is True
        assert is_session_revoked("revoked_2") is True
        assert is_session_revoked("") is False

    @pytest.mark.asyncio
    async def test_refresh_handles_db_error(self) -> None:
        with patch("database.get_db", side_effect=RuntimeError("db down")):
            await refresh_revoked_sessions()
        # Should not crash
        assert is_session_revoked("any") is False


class TestRefreshLoop:
    @pytest.mark.asyncio
    async def test_loop_cancels_cleanly(self) -> None:
        call_count = 0

        async def mock_refresh():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with (
            patch.object(mod, "refresh_revoked_sessions", side_effect=mock_refresh),
            patch.object(mod, "_REFRESH_INTERVAL_SECONDS", 0.01),
        ):
            with pytest.raises(asyncio.CancelledError):
                await refresh_revoked_sessions_loop()

        assert call_count >= 1
