"""Shared WebSocket broadcaster for real-time event streaming.

Provides a reusable base for any domain that needs to broadcast JSON
messages to connected WebSocket clients (audit log, sync progress,
library ingestion progress).

Usage::

    from utils.ws_broadcast import WsBroadcaster

    my_ws = WsBroadcaster("my_domain")
    await my_ws.connect(websocket)
    await my_ws.broadcast({"event": "done"})
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket
from loguru import logger


class WsBroadcaster:
    """Manages WebSocket connections and broadcasts JSON payloads.

    Maintains a set of active WebSocket clients and broadcasts messages
    to all of them.  Dead connections are automatically pruned during
    each broadcast cycle.

    Attributes:
        name: Descriptive name for logging (e.g. ``"audit"``, ``"sync"``).
    """

    def __init__(self, name: str) -> None:
        """Initialise the broadcaster.

        Args:
            name: Human-readable name for log messages.
        """
        self.name = name
        self._clients: set[WebSocket] = set()

    @property
    def client_count(self) -> int:
        """Return the number of currently connected clients."""
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket client.

        Args:
            ws: The incoming WebSocket connection to accept.
        """
        await ws.accept()
        self._clients.add(ws)

    def connect_accepted(self, ws: WebSocket) -> None:
        """Register an already-accepted WebSocket client.

        Use this when the connection has been accepted by an upstream
        authentication handler (e.g. ``authenticate_websocket``).

        Args:
            ws: The already-accepted WebSocket connection to register.
        """
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        """Unregister a WebSocket client.

        Args:
            ws: The WebSocket connection to remove.
        """
        self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any] | str) -> None:
        """Send a message to every connected client.

        Clients that fail to receive the message are silently removed.

        Args:
            payload: A dict (serialised to JSON) or a pre-serialised string.
        """
        if not self._clients:
            return
        text = json.dumps(payload, default=str) if isinstance(payload, dict) else payload
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_text(text)
            except Exception as exc:
                logger.debug("{} WS client dropped: {}", self.name, exc)
                dead.add(ws)
        self._clients -= dead

    async def send_to(self, ws: WebSocket, payload: dict[str, Any] | str) -> bool:
        """Send a message to a single client.

        Args:
            ws: Target WebSocket.
            payload: A dict (serialised to JSON) or a pre-serialised string.

        Returns:
            True if the message was sent, False if the client was dropped.
        """
        text = json.dumps(payload, default=str) if isinstance(payload, dict) else payload
        try:
            await ws.send_text(text)
            return True
        except Exception:
            self._clients.discard(ws)
            return False
