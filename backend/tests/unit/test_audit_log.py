"""Tests for audit/log.py — retry queue, plain write, chained write paths."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

import audit.log as audit_mod
from audit.log import _get_retry_queue, _is_chain_initialized, audit


@pytest.fixture(autouse=True)
def _reset_audit_state() -> None:
    audit_mod._retry_queues.clear()
    audit_mod._retry_task = None


def _mock_db(name: str = "test_db") -> MagicMock:
    db = AsyncMock(spec=AsyncIOMotorDatabase)
    db.name = name
    collection = AsyncMock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    db.__getitem__ = MagicMock(return_value=collection)
    return db


class TestGetRetryQueue:
    def test_creates_queue_for_new_db(self) -> None:
        db = _mock_db("tenant_a")
        q = _get_retry_queue(db)
        assert len(q) == 0

    def test_returns_same_queue_for_same_db(self) -> None:
        db = _mock_db("tenant_b")
        q1 = _get_retry_queue(db)
        q2 = _get_retry_queue(db)
        assert q1 is q2

    def test_different_dbs_get_different_queues(self) -> None:
        db1 = _mock_db("tenant_1")
        db2 = _mock_db("tenant_2")
        q1 = _get_retry_queue(db1)
        q2 = _get_retry_queue(db2)
        assert q1 is not q2


class TestIsChainInitialized:
    @pytest.mark.asyncio
    async def test_returns_true_when_genesis_exists(self) -> None:
        db = _mock_db()
        db["audit_log"].find_one = AsyncMock(return_value={"_id": "genesis", "sequence": 0})
        result = await _is_chain_initialized(db)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_genesis(self) -> None:
        db = _mock_db()
        db["audit_log"].find_one = AsyncMock(return_value=None)
        result = await _is_chain_initialized(db)
        assert result is False


class TestAuditFunction:
    @pytest.mark.asyncio
    async def test_plain_write_when_chain_not_initialized(self) -> None:
        db = _mock_db()
        db["audit_log"].find_one = AsyncMock(return_value=None)
        db["audit_log"].insert_one = AsyncMock()

        with patch("audit.ws.audit_ws") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await audit(
                db,
                domain="test",
                action="test.action",
                actor="tester",
                summary="Test event",
            )

        db["audit_log"].insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_chained_write_when_chain_initialized(self) -> None:
        db = _mock_db()
        db["audit_log"].find_one = AsyncMock(return_value={"_id": "g", "sequence": 0})

        with (
            patch("audit.ws.audit_ws") as mock_ws,
            patch("audit.chain.commands.append_chained_entry", new_callable=AsyncMock) as mock_chain,
        ):
            mock_ws.broadcast = AsyncMock()
            mock_chain.return_value = {"action": "test"}
            await audit(
                db,
                domain="test",
                action="test.chained",
                actor="tester",
                summary="Chained event",
            )

        mock_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_chain_check_error_falls_back_to_plain(self) -> None:
        db = _mock_db()
        # Chain check raises — should fall back to plain write
        db["audit_log"].find_one = AsyncMock(side_effect=RuntimeError("db error"))
        db["audit_log"].insert_one = AsyncMock()

        with patch("audit.ws.audit_ws") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await audit(
                db,
                domain="test",
                action="test.fallback",
                actor="tester",
                summary="Fallback event",
            )

        db["audit_log"].insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_plain_write_failure_queues_retry(self) -> None:
        db = _mock_db()
        db["audit_log"].find_one = AsyncMock(return_value=None)
        db["audit_log"].insert_one = AsyncMock(side_effect=RuntimeError("write failed"))

        with patch("audit.log._ensure_retry_task"):
            await audit(
                db,
                domain="test",
                action="test.retry",
                actor="tester",
                summary="Will be retried",
            )

        q = _get_retry_queue(db)
        assert len(q) == 1

    @pytest.mark.asyncio
    async def test_chained_write_failure_falls_back_to_plain(self) -> None:
        db = _mock_db()
        db["audit_log"].find_one = AsyncMock(return_value={"_id": "g", "sequence": 0})
        db["audit_log"].insert_one = AsyncMock()

        with (
            patch("audit.ws.audit_ws") as mock_ws,
            patch(
                "audit.chain.commands.append_chained_entry",
                new_callable=AsyncMock,
                side_effect=RuntimeError("chain error"),
            ),
        ):
            mock_ws.broadcast = AsyncMock()
            await audit(
                db,
                domain="test",
                action="test.chain_fail",
                actor="tester",
                summary="Chain failed, plain fallback",
            )

        # Should have fallen back to plain write
        db["audit_log"].insert_one.assert_called_once()
