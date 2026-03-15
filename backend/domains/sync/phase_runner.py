"""Base class for independent sync phase runners.

Each phase (sites, groups, agents, apps, tags) extends PhaseRunner and can
be triggered, resumed, and cancelled independently.  Checkpoints are stored
per-phase in ``s1_sync_checkpoint`` (keyed ``phase:<name>``).

All phases run in parallel with no dependency ordering.  The SyncManager
is just a WebSocket hub and convenience wrapper — each runner is self-contained.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from utils.dt import utc_now

# Type alias for the broadcast callback supplied by SyncManager
BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]


class PhaseRunner:
    """Abstract base for a single sync phase.

    Subclasses must implement ``_execute()`` which does the actual API fetching
    and DB writing.  The base class handles:
    - checkpoint load / save / clear
    - distributed locking (per-phase)
    - cancellation checks
    - progress broadcasting
    - run lifecycle (start → running → completed | failed)
    """

    phase_name: str = ""  # override in subclass
    lock_name: str = ""  # override or auto-derived from phase_name

    def __init__(self, broadcast: BroadcastFn | None = None) -> None:
        self._broadcast_fn = broadcast
        self._lock = asyncio.Lock()
        self._cancelled = False
        self._dist_lock: object | None = None
        self._status: str = "idle"  # idle | running | completed | failed
        self._run_id: str | None = None
        self._synced: int = 0
        self._total: int = 0
        self._message: str | None = None
        self._error: str | None = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status == "running"

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def progress(self) -> dict[str, Any]:
        return {
            "phase": self.phase_name,
            "status": self._status,
            "run_id": self._run_id,
            "synced": self._synced,
            "total": self._total,
            "message": self._message,
            "error": self._error,
        }

    # ── Checkpoint helpers ──────────────────────────────────────────────────

    @staticmethod
    async def _get_db() -> Any:  # noqa: ANN401
        from database import get_db

        return get_db()

    async def load_checkpoint(self) -> dict[str, Any] | None:
        db = await self._get_db()
        return await db["s1_sync_checkpoint"].find_one({"_id": f"phase:{self.phase_name}"})

    async def save_checkpoint(self, data: dict[str, Any]) -> None:
        db = await self._get_db()
        data["_id"] = f"phase:{self.phase_name}"
        data["updated_at"] = utc_now().isoformat()
        await db["s1_sync_checkpoint"].replace_one(
            {"_id": f"phase:{self.phase_name}"},
            data,
            upsert=True,
        )

    async def clear_checkpoint(self) -> None:
        db = await self._get_db()
        await db["s1_sync_checkpoint"].delete_one({"_id": f"phase:{self.phase_name}"})

    # ── Cancellation ────────────────────────────────────────────────────────

    def check_cancelled(self) -> None:
        if self._cancelled:
            raise asyncio.CancelledError(f"{self.phase_name} cancelled")
        # Also abort if the distributed lock was stolen by another worker
        if self._dist_lock is not None and not getattr(self._dist_lock, "_acquired", True):
            raise asyncio.CancelledError(
                f"{self.phase_name} aborted: distributed lock lost to another worker"
            )

    async def cancel(self) -> bool:
        if not self.is_running:
            return False
        self._cancelled = True
        return True

    # ── Progress broadcasting ───────────────────────────────────────────────

    async def _broadcast(self, **overrides: Any) -> None:  # noqa: ANN401
        if not self._broadcast_fn:
            return
        msg = {
            "type": "progress",
            "phase": self.phase_name,
            "run_id": self._run_id or "",
            "status": self._status,
            "synced": self._synced,
            "total": self._total,
            "message": self._message,
            **overrides,
        }
        await self._broadcast_fn(msg)

    async def _update(
        self,
        *,
        message: str | None = None,
        synced: int | None = None,
        total: int | None = None,
    ) -> None:
        if message is not None:
            self._message = message
        if synced is not None:
            self._synced = synced
        if total is not None:
            self._total = total
        await self._broadcast()

    # ── Distributed locking ─────────────────────────────────────────────────

    async def _acquire_dist_lock(self) -> bool:
        from config import get_settings

        if not get_settings().enable_distributed_locks:
            return True
        try:
            db = await self._get_db()
            from utils.distributed_lock import DistributedLock

            name = self.lock_name or f"sync_phase_{self.phase_name}"
            dist_lock = DistributedLock(db, name, ttl_seconds=3600)
            if not await dist_lock.acquire():
                logger.warning("{} distributed lock held — rejecting", self.phase_name)
                return False
            dist_lock._heartbeat_task = asyncio.create_task(dist_lock._heartbeat())
            self._dist_lock = dist_lock
            return True
        except Exception as exc:
            logger.error("{} lock acquisition failed: {}", self.phase_name, exc)
            return False

    async def _release_dist_lock(self) -> None:
        if self._dist_lock is not None:
            try:
                from utils.distributed_lock import DistributedLock

                if isinstance(self._dist_lock, DistributedLock):
                    # Cancel heartbeat task before releasing
                    ht = getattr(self._dist_lock, "_heartbeat_task", None)
                    if ht and not ht.done():
                        ht.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await ht
                    await self._dist_lock.release()
            except Exception as exc:
                logger.warning("{} lock release failed: {}", self.phase_name, exc)
            finally:
                self._dist_lock = None

    # ── Trigger / Resume / Run lifecycle ────────────────────────────────────

    async def trigger(
        self,
        *,
        mode: str = "auto",
        run_id: str | None = None,
        s1_client: Any = None,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any] | None:
        """Start a phase run, auto-resuming from checkpoint if one exists.

        If a checkpoint from a previous interrupted run is found, the phase
        resumes from where it left off rather than starting from scratch.
        This ensures that a 9M-app full sync that was interrupted at 5M
        continues from 5M — regardless of whether the trigger came from the
        scheduler, the UI, or a process restart.

        Returns progress dict or None if busy/locked.
        """
        # Check for an existing checkpoint — resume instead of starting fresh
        checkpoint = await self.load_checkpoint()
        if checkpoint and checkpoint.get("status") != "completed":
            logger.info("{} — checkpoint found, resuming instead of fresh trigger", self.phase_name)
            return await self.resume(s1_client=s1_client, **kwargs)

        async with self._lock:
            if self.is_running:
                return None
            if not await self._acquire_dist_lock():
                return None
            self._cancelled = False
            self._run_id = run_id or str(uuid.uuid4())
            self._status = "running"
            self._synced = 0
            self._total = 0
            self._error = None
            self._message = f"Starting {self.phase_name}…"

        asyncio.create_task(
            self._safe_run(mode=mode, s1_client=s1_client, is_resume=False, **kwargs)
        )
        return self.progress

    async def resume(
        self,
        *,
        s1_client: Any = None,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any] | None:
        """Resume from checkpoint.  Returns progress dict or None if busy/nothing to resume."""
        checkpoint = await self.load_checkpoint()
        if not checkpoint:
            return None
        if checkpoint.get("status") == "completed":
            await self.clear_checkpoint()
            return None

        async with self._lock:
            if self.is_running:
                return None
            if not await self._acquire_dist_lock():
                return None
            self._cancelled = False
            self._run_id = checkpoint.get("run_id", str(uuid.uuid4()))
            self._status = "running"
            self._synced = checkpoint.get("synced", 0)
            self._total = checkpoint.get("total", 0)
            self._error = None
            self._message = f"Resuming {self.phase_name} ({self._synced} already synced)…"

        mode = checkpoint.get("mode", "full")
        asyncio.create_task(
            self._safe_run(
                mode=mode, s1_client=s1_client, is_resume=True, checkpoint=checkpoint, **kwargs
            )
        )
        return self.progress

    async def _safe_run(self, **kwargs: Any) -> None:  # noqa: ANN401
        """Wrapper that catches exceptions and sets status."""
        try:
            await self._broadcast()
            await self._execute(**kwargs)
            self._status = "completed"
            self._message = f"{self.phase_name} completed ({self._synced} synced)"
            await self.clear_checkpoint()
            await self._broadcast(type="phase_completed")
            logger.info("{} completed — {} synced", self.phase_name, self._synced)
        except asyncio.CancelledError:
            self._status = "cancelled"
            self._message = f"{self.phase_name} cancelled"
            await self._broadcast(type="phase_cancelled")
            logger.info("{} cancelled", self.phase_name)
        except Exception as exc:
            self._status = "failed"
            self._error = str(exc)
            self._message = f"{self.phase_name} failed: {exc}"
            await self._broadcast(type="phase_failed")
            logger.error("{} failed: {}", self.phase_name, exc)
        finally:
            await self._release_dist_lock()

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        """Override in subclass.  Do the actual sync work here.

        Available kwargs:
        - mode: "full" | "incremental"
        - s1_client: S1Client instance (or None to create one)
        - is_resume: bool
        - checkpoint: dict (when resuming)
        - Any extra kwargs passed from trigger/resume
        """
        raise NotImplementedError

    # ── S1 client helper ────────────────────────────────────────────────────

    @staticmethod
    async def _create_s1_client() -> Any:  # noqa: ANN401
        """Create a new S1Client from the current application settings."""
        from config import get_settings

        from .s1_client import S1Client

        settings = get_settings()
        return S1Client(
            settings.s1_base_url,
            settings.s1_api_token,
            settings.s1_rate_limit_per_minute,
        )

    async def _load_page_size(self, db: Any, field: str = "page_size_agents") -> int:  # noqa: ANN401
        """Load the page size from persisted config, falling back to 500.

        Args:
            db: Motor database handle.
            field: AppConfig attribute name (e.g. ``"page_size_agents"`` or ``"page_size_apps"``).

        Returns:
            Page size integer.
        """
        try:
            from domains.config import repository as config_repo

            cfg = await config_repo.get(db)
            return getattr(cfg, field, 500)
        except Exception as exc:
            logger.warning(
                "{} — failed to load page_size, using default 500: {}", self.phase_name, exc
            )
            return 500
