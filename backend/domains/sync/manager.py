"""Sync manager — independent phase runners + WebSocket hub.

Each phase (sites, groups, agents, apps, tags) is an independent
``PhaseRunner`` that can be triggered, resumed, and cancelled on its own.

"Full Sync" and "Refresh" simply trigger all phases in parallel —
there is no sequential orchestration.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

from fastapi import WebSocket
from loguru import logger

from domains.sources.collections import SYNC_RUNS
from utils.dt import utc_now

from .dto import PhaseProgress, SyncCounts, SyncProgressMessage, SyncRunResponse
from .phases import (
    AgentsPhaseRunner,
    AppsPhaseRunner,
    GroupsPhaseRunner,
    SitesPhaseRunner,
    TagsPhaseRunner,
)

# CrowdStrike phase runners (lazy import to avoid hard dependency on falconpy)
def _cs_runners_available() -> bool:
    """Check if the CrowdStrike adapter package is importable."""
    try:
        import domains.sources.crowdstrike.sync_groups  # noqa: F401
        return True
    except ImportError:
        return False


class SyncManager:
    """WebSocket hub + convenience wrappers around independent phase runners."""

    # S1 phases — the original set
    S1_PHASES = ["sites", "groups", "agents", "apps", "tags"]
    # CrowdStrike phases — added dynamically if falconpy is available
    CS_PHASES = ["cs_groups", "cs_agents", "cs_apps"]
    ALL_PHASES = S1_PHASES  # Updated in __init__ if CS is available

    _PHASE_COUNT_FIELDS = {
        "sites": ("sites_synced", "sites_total"),
        "groups": ("groups_synced", "groups_total"),
        "agents": ("agents_synced", "agents_total"),
        "apps": ("apps_synced", "apps_total"),
        "tags": ("tags_synced", "tags_total"),
        # CS phases map to the same count fields (aggregated per source)
        "cs_groups": ("groups_synced", "groups_total"),
        "cs_agents": ("agents_synced", "agents_total"),
        "cs_apps": ("apps_synced", "apps_total"),
    }

    _PUBSUB_CHANNEL = "sync_progress"

    def __init__(self) -> None:
        self._current_run: SyncRunResponse | None = None
        self._last_completed: SyncRunResponse | None = None
        self._history: list[SyncRunResponse] = []
        self._clients: set[WebSocket] = set()
        self._broadcast_lock = asyncio.Lock()
        self._pubsub: Any = None  # PubSub instance, set in init()
        self._pubsub_task: asyncio.Task | None = None  # type: ignore[type-arg]

        # Phase runners — each is fully independent
        self.sites = SitesPhaseRunner(broadcast=self._phase_broadcast)
        self.groups = GroupsPhaseRunner(broadcast=self._phase_broadcast)
        self.agents = AgentsPhaseRunner(broadcast=self._phase_broadcast)
        self.apps = AppsPhaseRunner(broadcast=self._phase_broadcast)
        self.tags = TagsPhaseRunner(broadcast=self._phase_broadcast)

        self._runners: dict[str, Any] = {
            "sites": self.sites,
            "groups": self.groups,
            "agents": self.agents,
            "apps": self.apps,
            "tags": self.tags,
        }

        # Register CrowdStrike phase runners if the adapter is available
        if _cs_runners_available():
            from domains.sources.crowdstrike.sync_agents import CSAgentsPhaseRunner
            from domains.sources.crowdstrike.sync_apps import CSAppsPhaseRunner
            from domains.sources.crowdstrike.sync_groups import CSGroupsPhaseRunner

            self.cs_groups = CSGroupsPhaseRunner(broadcast=self._phase_broadcast)
            self.cs_agents = CSAgentsPhaseRunner(broadcast=self._phase_broadcast)
            self.cs_apps = CSAppsPhaseRunner(broadcast=self._phase_broadcast)
            self._runners["cs_groups"] = self.cs_groups
            self._runners["cs_agents"] = self.cs_agents
            self._runners["cs_apps"] = self.cs_apps
            SyncManager.ALL_PHASES = self.S1_PHASES + self.CS_PHASES
            logger.info("SyncManager — CrowdStrike phases registered")

    def get_runner(self, phase: str) -> Any:  # noqa: ANN401
        return self._runners.get(phase)

    async def init(self) -> None:
        """Load run history from MongoDB and start cross-worker PubSub relay."""
        try:
            from database import get_db

            db = get_db()
            cursor = db[SYNC_RUNS].find({}, {"_id": 0}).sort("started_at", -1).limit(100)
            docs = [doc async for doc in cursor]
            self._history = [SyncRunResponse(**doc) for doc in reversed(docs)]
            for run in reversed(self._history):
                if run.status in ("completed", "failed"):
                    self._last_completed = run
                    break
            logger.info(
                "SyncManager loaded {} runs (last completed: {})",
                len(self._history),
                self._last_completed.id[:8] if self._last_completed else "none",
            )
        except Exception as exc:
            logger.warning("SyncManager — could not load history: {}", exc)

        # Start cross-worker PubSub relay so all workers can push WS updates
        try:
            from database import get_db
            from utils.pubsub import PubSub

            self._pubsub = PubSub(get_db())
            self._pubsub_task = await self._pubsub.subscribe(
                self._PUBSUB_CHANNEL,
                self._on_pubsub_message,
            )
            logger.info("SyncManager — PubSub relay started on channel '{}'", self._PUBSUB_CHANNEL)
        except Exception as exc:
            logger.warning("SyncManager — PubSub relay failed to start: {}", exc)

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def current_run(self) -> SyncRunResponse | None:
        return self._current_run

    @property
    def last_completed_run(self) -> SyncRunResponse | None:
        return self._last_completed

    @property
    def history(self) -> list[SyncRunResponse]:
        return list(reversed(self._history))

    # ── WebSocket client management ─────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a WebSocket client, sending the current run snapshot."""
        await ws.accept()
        await self._register_and_snapshot(ws)

    async def connect_accepted(self, ws: WebSocket) -> None:
        """Register an already-accepted WebSocket client, sending the current run snapshot.

        Use this when the connection has been accepted by an upstream
        authentication handler (e.g. ``authenticate_websocket``).

        Args:
            ws: The already-accepted WebSocket connection.
        """
        await self._register_and_snapshot(ws)

    async def _register_and_snapshot(self, ws: WebSocket) -> None:
        """Register a client and send the current run state if one is active."""
        self._clients.add(ws)
        if self._current_run:
            phase_details, counts = self._snapshot()
            await self._send_to(
                ws,
                SyncProgressMessage(
                    type="progress",
                    run_id=self._current_run.id,
                    status=self._current_run.status,
                    phase=self._current_run.phase,
                    counts=counts,
                    message=self._current_run.message,
                    phase_details=phase_details,
                ),
            )

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _send_to(self, ws: WebSocket, msg: SyncProgressMessage) -> None:
        try:
            await ws.send_text(msg.model_dump_json())
        except Exception:
            self._clients.discard(ws)

    async def _broadcast(self, msg: SyncProgressMessage) -> None:
        """Send to local WS clients and publish to PubSub for other workers."""
        payload = msg.model_dump_json()
        # Local clients
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead
        # Cross-worker relay via PubSub (fire-and-forget)
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.publish(self._PUBSUB_CHANNEL, payload)

    async def _on_pubsub_message(self, payload: str) -> None:
        """Relay a message received from PubSub to local WS clients.

        Only relays messages that originated from a *different* worker.
        We detect this by checking whether the message is for the current
        in-memory run — if it is, we already broadcast it locally.
        """
        import json

        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return
        # Skip messages that originated on this worker (we already broadcast locally)
        local_run_id = self._current_run.id if self._current_run else None
        if local_run_id and data.get("run_id") == local_run_id:
            return
        # Relay to local WS clients
        dead: set[WebSocket] = set()
        for ws in list(self._clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ── State snapshot ──────────────────────────────────────────────────────

    def _snapshot(self) -> tuple[dict[str, PhaseProgress], SyncCounts]:
        """Single pass over runners → (phase_details, counts).

        Only includes counts from non-idle runners to prevent stale values
        from a previous run leaking into the broadcast.
        """
        details: dict[str, PhaseProgress] = {}
        counts = SyncCounts()
        for name, runner in self._runners.items():
            status = runner.status or "idle"
            details[name] = PhaseProgress(
                status=status,
                synced=runner._synced,
                total=runner._total,
                message=runner._message,
            )
            if status != "idle":
                sf, tf = self._PHASE_COUNT_FIELDS[name]
                setattr(counts, sf, runner._synced)
                setattr(counts, tf, runner._total)
        return details, counts

    def _any_phase_running(self) -> bool:
        return any(r.is_running for r in self._runners.values())

    async def _phase_broadcast(self, data: dict[str, Any]) -> None:
        """Callback from phase runners → snapshot state → broadcast to WS."""
        async with self._broadcast_lock:
            await self._phase_broadcast_inner(data)

    async def _phase_broadcast_inner(self, data: dict[str, Any]) -> None:
        phase = data.get("phase", "")
        run = self._current_run

        # Create a run object so the frontend knows something is happening
        if not run and self._any_phase_running():
            run = SyncRunResponse(
                id=data.get("run_id") or str(uuid.uuid4()),
                started_at=utc_now().isoformat(),
                status="running",
                trigger=data.get("trigger", "phase"),
                mode=data.get("mode", "auto"),
                phase=phase,
                message=data.get("message"),
            )
            self._current_run = run

        if run and run.status == "running":
            run.phase = phase
            run.message = data.get("message")

        phase_details, counts = self._snapshot()
        if run:
            run.counts = counts

        # Determine WS message type
        msg_type = data.get("type", "progress")
        ws_type: str = "progress"
        ws_status = run.status if run else "running"

        # Apps phase completed → rebuild app summaries cache immediately
        # (don't wait for other phases — stats cache only depends on app data)
        if msg_type == "phase_completed" and phase == "apps":
            asyncio.create_task(self._rebuild_app_cache())

        # Terminal event — check if ALL phases are done
        if msg_type in (  # noqa: SIM102
            "phase_completed",
            "phase_failed",
            "phase_cancelled",
        ):
            if run and not self._any_phase_running():
                any_failed = any(r.status == "failed" for r in self._runners.values())
                ws_type = "failed" if any_failed else "completed"
                ws_status = "failed" if any_failed else "completed"
                run.status = ws_status
                run.completed_at = utc_now().isoformat()
                run.phase = "done"
                run.message = "Sync completed" if ws_status == "completed" else "Sync failed"
                self._last_completed = run
                self._history.append(run)
                self._history = self._history[-100:]
                await self._persist_run(run)
                self._current_run = None

                # Reset finished runners to idle so stale counts from this
                # run don't leak into a future single-phase trigger.
                for r in self._runners.values():
                    if r.status in ("completed", "failed", "cancelled"):
                        r._status = "idle"

                # Post-sync tasks
                asyncio.create_task(self._post_sync_tasks(run))

        await self._broadcast(
            SyncProgressMessage(
                type=ws_type,
                run_id=run.id if run else data.get("run_id", ""),
                status=ws_status,
                phase=phase,
                counts=counts,
                message=data.get("message"),
                phase_details=phase_details,
            )
        )

    # ── Trigger / cancel ────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._any_phase_running()

    async def trigger_all(
        self,
        mode: str = "auto",
        phases: list[str] | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Trigger phases independently in parallel.

        Creates shared API clients per source so all phases of the same
        source share one rate limiter.  Each phase handles its own mode
        detection and timestamps.

        Args:
            mode: Sync mode (``"full"``, ``"incremental"``, ``"auto"``).
            phases: Optional list of phase names to trigger (default: all).
            source: Optional source filter — ``"sentinelone"``, ``"crowdstrike"``,
                    or ``None`` for all sources.
        """
        # Determine target phases
        if source == "sentinelone":
            available = self.S1_PHASES
        elif source == "crowdstrike":
            available = self.CS_PHASES
        else:
            available = self.ALL_PHASES
        target = [p for p in available if p in (phases or available)]

        # Split targets by source for separate shared clients
        s1_targets = [p for p in target if not p.startswith("cs_")]
        cs_targets = [p for p in target if p.startswith("cs_")]

        started: list[str] = []

        # S1 phases — shared S1 client
        if s1_targets:
            from .phase_runner import PhaseRunner

            shared_s1 = await PhaseRunner._create_s1_client()
            s1_started: list[str] = []
            for phase_name in s1_targets:
                runner = self._runners[phase_name]
                if runner.is_running:
                    continue
                result = await runner.trigger(mode=mode, s1_client=shared_s1)
                if result is not None:
                    s1_started.append(phase_name)
            if not s1_started:
                await shared_s1.close()
            else:
                asyncio.create_task(self._close_client_when_done(shared_s1, s1_started))
            started.extend(s1_started)

        # CS phases — shared CS client
        if cs_targets:
            try:
                from domains.sources.crowdstrike.sync_groups import CSGroupsPhaseRunner

                shared_cs = await CSGroupsPhaseRunner._create_cs_client()
                cs_started: list[str] = []
                for phase_name in cs_targets:
                    runner = self._runners[phase_name]
                    if runner.is_running:
                        continue
                    result = await runner.trigger(mode=mode, cs_client=shared_cs)
                    if result is not None:
                        cs_started.append(phase_name)
                if not cs_started:
                    await shared_cs.close()
                else:
                    asyncio.create_task(self._close_client_when_done(shared_cs, cs_started))
                started.extend(cs_started)
            except Exception as exc:
                logger.warning("Could not create CrowdStrike client: {}", exc)

        return {"mode": mode, "phases_started": started}

    async def _close_client_when_done(self, client: Any, phase_names: list[str]) -> None:  # noqa: ANN401
        """Wait for all named phases to finish, then close the shared S1 client."""
        try:
            while any(self._runners[n].is_running for n in phase_names):
                await asyncio.sleep(5)
        finally:
            await client.close()

    async def cancel(self) -> bool:
        """Cancel all running phases."""
        cancelled_any = False
        for runner in self._runners.values():
            if runner.is_running:
                await runner.cancel()
                cancelled_any = True
        return cancelled_any

    async def resume_all(self) -> dict[str, Any]:
        """Resume any phases that have checkpoints."""
        resumed: list[str] = []
        for name, runner in self._runners.items():
            if runner.is_running:
                continue
            cp = await runner.load_checkpoint()
            if cp and cp.get("status") != "completed":
                result = await runner.resume()
                if result is not None:
                    resumed.append(name)
        return {"phases_resumed": resumed}

    # ── Per-phase control ───────────────────────────────────────────────────

    async def trigger_phase(self, phase: str, mode: str = "auto") -> dict[str, Any] | None:
        runner = self._runners.get(phase)
        if not runner:
            return None
        return await runner.trigger(mode=mode)

    async def resume_phase(self, phase: str) -> dict[str, Any] | None:
        runner = self._runners.get(phase)
        if not runner:
            return None
        return await runner.resume()

    async def cancel_phase(self, phase: str) -> bool:
        runner = self._runners.get(phase)
        if not runner:
            return False
        return await runner.cancel()

    def phase_status(self) -> dict[str, dict[str, Any]]:
        return {name: runner.progress for name, runner in self._runners.items()}

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _persist_run(self, run: SyncRunResponse) -> None:
        try:
            from database import get_db

            db = get_db()
            doc = run.model_dump()
            doc["_id"] = run.id
            await db[SYNC_RUNS].replace_one({"_id": run.id}, doc, upsert=True)
        except Exception as exc:
            logger.warning("Sync {} — failed to persist run: {}", run.id, exc)

    async def _rebuild_app_cache(self) -> None:
        """Rebuild app_summaries after the apps phase completes.

        Runs as a fire-and-forget task so the sync progress broadcast
        is not blocked by the rebuild.
        """
        try:
            from domains.agents.app_cache import rebuild_app_summaries

            await rebuild_app_summaries()
        except Exception as exc:
            logger.warning("App summaries rebuild failed: {}", exc)

    async def _post_sync_tasks(self, run: SyncRunResponse) -> None:
        """Run after all phases complete — audit, webhooks, EOL, dashboard.

        Independent tasks run in parallel for faster completion:
        - audit log + webhooks (no data dependencies)
        - fleet + fingerprinting dashboard stats (only need agents/groups)
        - EOL matching → apps dashboard stats (must wait for app_summaries)
        """
        from database import get_db

        db = get_db()

        await asyncio.gather(
            self._audit_and_webhook(db, run),
            self._refresh_fleet_and_fingerprinting(db),
            self._eol_and_apps_dashboard(db),
        )

    async def _audit_and_webhook(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        run: SyncRunResponse,
    ) -> None:
        """Audit log entry + webhook dispatch."""
        try:
            from audit.log import audit

            event = "sync.completed" if run.status == "completed" else "sync.failed"
            await audit(
                db,
                domain="sync",
                action=event,
                actor="system",
                status="success" if run.status == "completed" else "failure",
                summary=(
                    f"Sync {run.status} — "
                    f"{run.counts.agents_synced} agents, "
                    f"{run.counts.apps_synced} apps"
                ),
                details=run.counts.model_dump(),
            )
            try:
                from domains.webhooks.service import dispatch_event

                await dispatch_event(db, event, run.counts.model_dump())
            except Exception as exc:
                logger.warning("Webhook dispatch failed: {}", exc)
        except Exception as exc:
            logger.warning("Audit/webhook post-sync tasks failed: {}", exc)

    @staticmethod
    async def _refresh_fleet_and_fingerprinting(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Refresh fleet + fingerprinting dashboard stats (no app data dependency)."""
        try:
            from domains.dashboard.cache import compute_fingerprinting, compute_fleet

            fleet_data, fp_data = await asyncio.gather(
                compute_fleet(db), compute_fingerprinting(db)
            )
            now = utc_now().isoformat()
            await asyncio.gather(
                db["dashboard_stats"].replace_one(
                    {"_id": "fleet"},
                    {"_id": "fleet", "data": fleet_data, "computed_at": now},
                    upsert=True,
                ),
                db["dashboard_stats"].replace_one(
                    {"_id": "fingerprinting"},
                    {"_id": "fingerprinting", "data": fp_data, "computed_at": now},
                    upsert=True,
                ),
            )
        except Exception as exc:
            logger.warning("Fleet/fingerprinting dashboard refresh failed: {}", exc)

    @staticmethod
    async def _eol_and_apps_dashboard(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Wait for app_summaries rebuild → EOL matching → apps dashboard stats.

        This chain depends on ``app_summaries`` being fresh, so it waits
        for the rebuild lock (populated by ``_rebuild_app_cache`` which
        fires when the apps phase completes).
        """
        # Wait for any in-progress app_summaries rebuild to finish
        try:
            from domains.agents.app_cache import _rebuild_lock

            async with _rebuild_lock:
                pass
        except Exception as exc:
            logger.warning("Failed waiting for app_summaries rebuild: {}", exc)

        # EOL matching (reads from app_summaries, writes eol_match back)
        try:
            from domains.eol.service import run_eol_matching_for_apps

            await run_eol_matching_for_apps(db)
        except Exception as exc:
            logger.warning("EOL matching after sync failed: {}", exc)

        # Apps dashboard stats (reads from app_summaries — fast after H1 optimization)
        try:
            from domains.dashboard.cache import compute_apps

            apps_data = await compute_apps(db)
            await db["dashboard_stats"].replace_one(
                {"_id": "apps"},
                {"_id": "apps", "data": apps_data, "computed_at": utc_now().isoformat()},
                upsert=True,
            )
        except Exception as exc:
            logger.warning("Apps dashboard refresh failed: {}", exc)


# Module-level singleton
sync_manager = SyncManager()
