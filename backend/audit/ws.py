"""Audit log WebSocket broadcast manager.

A single global instance (``audit_ws``) keeps track of every connected
WebSocket client.  ``audit/log.py`` calls ``audit_ws.broadcast()`` after
each successful insert so all clients receive new entries in real time.

Uses the shared ``WsBroadcaster`` base class.
"""

from __future__ import annotations

from utils.ws_broadcast import WsBroadcaster

audit_ws = WsBroadcaster("audit")
