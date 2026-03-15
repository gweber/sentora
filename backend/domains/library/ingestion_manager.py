"""Library ingestion manager — independent per-source runners + WebSocket hub.

Each source (nist_cpe, mitre, chocolatey, homebrew) is an independent
``SourceRunner`` that can be triggered, resumed, and cancelled on its own.

"Ingest All" triggers all sources in parallel — there is no sequential
orchestration.  Mirrors the sync domain's ``SyncManager`` pattern.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from fastapi import WebSocket
from loguru import logger

from domains.library.adapters.base import SourceAdapter
from domains.library.adapters.chocolatey import ChocolateyAdapter
from domains.library.adapters.homebrew import HomebrewAdapter
from domains.library.adapters.homebrew_cask import HomebrewCaskAdapter
from domains.library.adapters.mitre_attack import MitreAttackAdapter
from domains.library.adapters.nist_cpe import NistCpeAdapter
from domains.library.dto import IngestionProgressMessage, SourceProgress
from domains.library.source_runner import SourceRunner

# Registry of available adapters
ADAPTERS: dict[str, SourceAdapter] = {
    "nist_cpe": NistCpeAdapter(),
    "mitre": MitreAttackAdapter(),
    "chocolatey": ChocolateyAdapter(),
    "homebrew": HomebrewAdapter(),
    "homebrew_cask": HomebrewCaskAdapter(),
}


class IngestionManager:
    """WebSocket hub + convenience wrappers around independent source runners."""

    ALL_SOURCES = list(ADAPTERS.keys())

    _PUBSUB_CHANNEL = "library_ingestion_progress"

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._broadcast_lock = asyncio.Lock()
        self._pubsub: Any = None
        self._pubsub_task: asyncio.Task | None = None  # type: ignore[type-arg]

        # One runner per source — each is fully independent
        self._runners: dict[str, SourceRunner] = {}
        for name, adapter in ADAPTERS.items():
            self._runners[name] = SourceRunner(
                source_name=name,
                adapter=adapter,
                broadcast=self._source_broadcast,
            )

    def get_runner(self, source: str) -> SourceRunner | None:
        """Return the runner for a given source name, or ``None``."""
        return self._runners.get(source)

    async def init(self) -> None:
        """Start cross-worker PubSub relay for WebSocket broadcasting."""
        try:
            from database import get_library_db
            from utils.pubsub import PubSub

            self._pubsub = PubSub(get_library_db())
            self._pubsub_task = await self._pubsub.subscribe(
                self._PUBSUB_CHANNEL,
                self._on_pubsub_message,
            )
            logger.info("IngestionManager — PubSub relay started on '{}'", self._PUBSUB_CHANNEL)
        except Exception as exc:
            logger.warning("IngestionManager — PubSub relay failed to start: {}", exc)

    # ── Properties ─────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """Return whether any source is currently ingesting."""
        return any(r.is_running for r in self._runners.values())

    @property
    def current_source(self) -> str | None:
        """Return the name of a currently running source, if any (compat)."""
        for name, runner in self._runners.items():
            if runner.is_running:
                return name
        return None

    def running_sources(self) -> list[str]:
        """Return names of all currently running sources."""
        return [n for n, r in self._runners.items() if r.is_running]

    # ── WebSocket client management ────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        """Accept a WebSocket client and send a progress snapshot if running."""
        await ws.accept()
        await self._register_and_snapshot(ws)

    async def connect_accepted(self, ws: WebSocket) -> None:
        """Register an already-accepted WebSocket client.

        Use this when the connection has been accepted by an upstream
        authentication handler (e.g. ``authenticate_websocket``).

        Args:
            ws: The already-accepted WebSocket connection.
        """
        await self._register_and_snapshot(ws)

    async def _register_and_snapshot(self, ws: WebSocket) -> None:
        """Register a client and send a progress snapshot if running."""
        self._clients.add(ws)
        if self.is_running():
            source_details = self._snapshot()
            for name, runner in self._runners.items():
                if runner.is_running:
                    await self._send_to(
                        ws,
                        IngestionProgressMessage(
                            type="progress",
                            run_id=runner.run_id or "",
                            source=name,
                            status="running",
                            message=runner.message,
                            source_details=source_details,
                        ),
                    )
                    break  # send one snapshot with all details

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket client from the broadcast set."""
        self._clients.discard(ws)

    async def _send_to(self, ws: WebSocket, msg: IngestionProgressMessage) -> None:
        try:
            await ws.send_text(msg.model_dump_json())
        except Exception:
            self._clients.discard(ws)

    async def _broadcast(self, msg: IngestionProgressMessage) -> None:
        """Send to local WS clients and publish to PubSub for other workers."""
        payload = msg.model_dump_json()
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.publish(self._PUBSUB_CHANNEL, payload)

    async def _on_pubsub_message(self, payload: str) -> None:
        """Relay a PubSub message from another worker to local WS clients."""
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ── State snapshot ─────────────────────────────────────────────────────

    def _snapshot(self) -> dict[str, SourceProgress]:
        """Build a per-source status snapshot."""
        details: dict[str, SourceProgress] = {}
        for name, runner in self._runners.items():
            details[name] = SourceProgress(
                status=runner.status,
                synced=runner.synced,
                total=runner.total,
                message=runner.message,
            )
        return details

    async def _source_broadcast(self, data: dict[str, Any]) -> None:
        """Callback from source runners → snapshot state → broadcast to WS."""
        async with self._broadcast_lock:
            source = data.get("source", "")
            source_details = self._snapshot()

            msg_type = data.get("type", "progress")
            ws_type = msg_type
            ws_status = data.get("status", "running")

            # Check if ALL sources are done after a terminal event
            if msg_type in (  # noqa: SIM102
                "source_completed",
                "source_failed",
                "source_cancelled",
            ):
                if not self.is_running():
                    any_failed = any(r.status == "failed" for r in self._runners.values())
                    ws_type = "failed" if any_failed else "completed"
                    ws_status = "failed" if any_failed else "completed"

                    # Reset finished runners to idle
                    for r in self._runners.values():
                        r.reset_to_idle()

            await self._broadcast(
                IngestionProgressMessage(
                    type=ws_type,
                    run_id=data.get("run_id", ""),
                    source=source,
                    status=ws_status,
                    message=data.get("message"),
                    source_details=source_details,
                )
            )

    # ── Trigger / Cancel / Resume ──────────────────────────────────────────

    async def trigger_source(
        self,
        source_name: str,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Trigger a single source independently."""
        runner = self._runners.get(source_name)
        if not runner:
            return None
        return await runner.trigger(config=config)

    async def trigger_all(
        self,
        sources: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Trigger multiple sources in parallel."""
        target = [s for s in self.ALL_SOURCES if s in (sources or self.ALL_SOURCES)]
        started: list[str] = []
        for source_name in target:
            runner = self._runners[source_name]
            if runner.is_running:
                continue
            result = await runner.trigger(config=config)
            if result is not None:
                started.append(source_name)
        return {"sources_started": started}

    async def cancel_source(self, source_name: str) -> bool:
        """Cancel a single running source."""
        runner = self._runners.get(source_name)
        if not runner:
            return False
        return await runner.cancel()

    async def cancel_all(self) -> bool:
        """Cancel all running sources."""
        cancelled_any = False
        for runner in self._runners.values():
            if runner.is_running:
                await runner.cancel()
                cancelled_any = True
        return cancelled_any

    async def resume_source(self, source_name: str) -> dict[str, Any] | None:
        """Resume a single source from checkpoint."""
        runner = self._runners.get(source_name)
        if not runner:
            return None
        return await runner.resume()

    async def resume_all(self) -> dict[str, Any]:
        """Resume all sources that have checkpoints."""
        resumed: list[str] = []
        for name, runner in self._runners.items():
            if runner.is_running:
                continue
            cp = await runner.load_checkpoint()
            if cp and cp.get("status") != "completed":
                result = await runner.resume()
                if result is not None:
                    resumed.append(name)
        return {"sources_resumed": resumed}

    # ── Per-source status ──────────────────────────────────────────────────

    def source_status(self) -> dict[str, dict[str, Any]]:
        """Return per-source progress info."""
        return {name: runner.progress for name, runner in self._runners.items()}


# Module-level singleton
ingestion_manager = IngestionManager()
