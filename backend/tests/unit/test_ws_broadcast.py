"""Tests for the shared WebSocket broadcaster."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.ws_broadcast import WsBroadcaster


@pytest.mark.asyncio
async def test_connect_adds_client() -> None:
    """connect() should accept the websocket and add it to the client set."""
    ws = AsyncMock()
    broadcaster = WsBroadcaster("test")
    await broadcaster.connect(ws)
    ws.accept.assert_awaited_once()
    assert broadcaster.client_count == 1


def test_connect_accepted_adds_client() -> None:
    """connect_accepted() should add a pre-accepted websocket."""
    ws = MagicMock()
    broadcaster = WsBroadcaster("test")
    broadcaster.connect_accepted(ws)
    assert broadcaster.client_count == 1


def test_disconnect_removes_client() -> None:
    """disconnect() should remove the websocket from the set."""
    ws = MagicMock()
    broadcaster = WsBroadcaster("test")
    broadcaster.connect_accepted(ws)
    assert broadcaster.client_count == 1
    broadcaster.disconnect(ws)
    assert broadcaster.client_count == 0


def test_disconnect_unknown_is_noop() -> None:
    """disconnect() on an unknown websocket should not raise."""
    ws = MagicMock()
    broadcaster = WsBroadcaster("test")
    broadcaster.disconnect(ws)  # no error
    assert broadcaster.client_count == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all() -> None:
    """broadcast() should send the payload to every connected client."""
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    broadcaster = WsBroadcaster("test")
    broadcaster.connect_accepted(ws1)
    broadcaster.connect_accepted(ws2)

    await broadcaster.broadcast({"event": "sync.done"})

    ws1.send_text.assert_awaited_once()
    ws2.send_text.assert_awaited_once()
    # Both should receive the same JSON string
    sent1 = ws1.send_text.call_args[0][0]
    sent2 = ws2.send_text.call_args[0][0]
    assert sent1 == sent2
    assert '"event"' in sent1


@pytest.mark.asyncio
async def test_broadcast_prunes_dead_clients() -> None:
    """broadcast() should remove clients that fail to receive messages."""
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = ConnectionError("gone")

    broadcaster = WsBroadcaster("test")
    broadcaster.connect_accepted(ws_alive)
    broadcaster.connect_accepted(ws_dead)
    assert broadcaster.client_count == 2

    await broadcaster.broadcast({"ping": True})

    assert broadcaster.client_count == 1


@pytest.mark.asyncio
async def test_broadcast_empty_clients_is_noop() -> None:
    """broadcast() with no clients should return immediately."""
    broadcaster = WsBroadcaster("test")
    await broadcaster.broadcast({"data": 1})  # no error


@pytest.mark.asyncio
async def test_broadcast_accepts_string_payload() -> None:
    """broadcast() should send pre-serialised strings as-is."""
    ws = AsyncMock()
    broadcaster = WsBroadcaster("test")
    broadcaster.connect_accepted(ws)
    await broadcaster.broadcast('{"raw": true}')
    ws.send_text.assert_awaited_once_with('{"raw": true}')
