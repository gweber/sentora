"""Base class for independent library source ingestion runners.

Each source (nist_cpe, mitre, chocolatey, homebrew) gets its own
SourceRunner instance that can be triggered, resumed, and cancelled
independently.  Checkpoints are stored per-source in
``library_ingestion_checkpoint`` (keyed ``source:<name>``).

Mirrors the sync domain's ``PhaseRunner`` pattern but adapted for
library ingestion: uses the shared library DB, processes RawEntry
objects through SourceAdapters, and upserts into library_entries.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from domains.library import repository
from domains.library.adapters.base import SourceAdapter
from domains.library.entities import IngestionRun, LibraryMarker
from utils.dt import utc_now

# Type alias for the broadcast callback supplied by IngestionManager.
BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]

CHECKPOINT_COLLECTION = "library_ingestion_checkpoint"

# Save checkpoint every N processed entries.
_CHECKPOINT_INTERVAL = 100
# Broadcast progress every N processed entries.
_BROADCAST_INTERVAL = 50


class SourceRunner:
    """Runs a single library source ingestion with checkpoint-based resume.

    Each runner is self-contained — the IngestionManager is just a
    WebSocket hub and convenience wrapper.

    Attributes:
        source_name: Adapter key (e.g. ``nist_cpe``, ``mitre``).
    """

    def __init__(
        self,
        source_name: str,
        adapter: SourceAdapter,
        broadcast: BroadcastFn | None = None,
    ) -> None:
        """Initialise a runner for a single library source.

        Args:
            source_name: Adapter key (e.g. ``nist_cpe``).
            adapter: Source adapter that provides ``fetch()`` and
                ``get_resume_state()``.
            broadcast: Async callback for progress messages.
        """
        self.source_name = source_name
        self._adapter = adapter
        self._broadcast_fn = broadcast
        self._lock = asyncio.Lock()
        self._cancelled = False
        self._dist_lock: object | None = None
        self._status: str = "idle"
        self._run_id: str | None = None
        self._synced: int = 0
        self._total: int = 0
        self._message: str | None = None
        self._error: str | None = None

    # ── Public properties ──────────────────────────────────────────────────

    @property
    def status(self) -> str:
        """Current lifecycle status: idle, running, completed, failed, or cancelled."""
        return self._status

    @property
    def is_running(self) -> bool:
        """Whether this runner is currently executing."""
        return self._status == "running"

    @property
    def run_id(self) -> str | None:
        """UUID of the current or last run."""
        return self._run_id

    @property
    def synced(self) -> int:
        """Number of entries processed so far."""
        return self._synced

    @property
    def total(self) -> int:
        """Estimated total entries (may be zero if unknown)."""
        return self._total

    @property
    def message(self) -> str | None:
        """Human-readable status message."""
        return self._message

    @property
    def progress(self) -> dict[str, Any]:
        """Snapshot of runner state for API responses."""
        return {
            "source": self.source_name,
            "status": self._status,
            "run_id": self._run_id,
            "synced": self._synced,
            "total": self._total,
            "message": self._message,
            "error": self._error,
        }

    def reset_to_idle(self) -> None:
        """Reset runner to idle after a terminal event.

        Called by the manager once all sources finish so stale counts
        don't leak into subsequent progress snapshots.
        """
        if self._status in ("completed", "failed", "cancelled"):
            self._status = "idle"

    # ── DB access ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_library_db() -> Any:  # noqa: ANN401
        """Return the shared library database handle."""
        from database import get_library_db

        return get_library_db()

    # ── Checkpoint helpers ─────────────────────────────────────────────────

    async def load_checkpoint(self) -> dict[str, Any] | None:
        """Load persisted checkpoint from ``library_ingestion_checkpoint``.

        Returns:
            Checkpoint dict, or ``None`` if no checkpoint exists.
        """
        db = self._get_library_db()
        return await db[CHECKPOINT_COLLECTION].find_one({"_id": f"source:{self.source_name}"})

    async def save_checkpoint(self, data: dict[str, Any]) -> None:
        """Persist checkpoint to ``library_ingestion_checkpoint``.

        Args:
            data: Checkpoint payload (synced count, adapter state, etc.).
        """
        db = self._get_library_db()
        data["_id"] = f"source:{self.source_name}"
        data["updated_at"] = utc_now().isoformat()
        await db[CHECKPOINT_COLLECTION].replace_one(
            {"_id": f"source:{self.source_name}"},
            data,
            upsert=True,
        )

    async def clear_checkpoint(self) -> None:
        """Remove checkpoint from ``library_ingestion_checkpoint``."""
        db = self._get_library_db()
        await db[CHECKPOINT_COLLECTION].delete_one({"_id": f"source:{self.source_name}"})

    # ── Cancellation ───────────────────────────────────────────────────────

    def check_cancelled(self) -> None:
        """Raise ``CancelledError`` if cancellation was requested or lock lost."""
        if self._cancelled:
            raise asyncio.CancelledError(f"{self.source_name} cancelled")
        if self._dist_lock is not None and not getattr(self._dist_lock, "_acquired", True):
            raise asyncio.CancelledError(f"{self.source_name} aborted: distributed lock lost")

    async def cancel(self) -> bool:
        """Request cooperative cancellation of a running ingestion.

        Returns:
            ``True`` if cancellation was requested, ``False`` if not running.
        """
        if not self.is_running:
            return False
        self._cancelled = True
        return True

    # ── Progress broadcasting ──────────────────────────────────────────────

    async def _broadcast(self, **overrides: Any) -> None:  # noqa: ANN401
        """Send a progress message to the manager's broadcast callback."""
        if not self._broadcast_fn:
            return
        msg = {
            "type": "progress",
            "source": self.source_name,
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
        """Update in-memory state and broadcast to WebSocket clients."""
        if message is not None:
            self._message = message
        if synced is not None:
            self._synced = synced
        if total is not None:
            self._total = total
        await self._broadcast()

    # ── Distributed locking ────────────────────────────────────────────────

    async def _acquire_dist_lock(self) -> bool:
        """Acquire a per-source distributed lock (library DB)."""
        from config import get_settings

        if not get_settings().enable_distributed_locks:
            return True
        try:
            db = self._get_library_db()
            from utils.distributed_lock import DistributedLock

            name = f"library_source_{self.source_name}"
            dist_lock = DistributedLock(db, name, ttl_seconds=3600)
            if not await dist_lock.acquire():
                logger.warning("{} distributed lock held — rejecting", self.source_name)
                return False
            dist_lock._heartbeat_task = asyncio.create_task(dist_lock._heartbeat())
            self._dist_lock = dist_lock
            return True
        except Exception as exc:
            logger.error("{} lock acquisition failed: {}", self.source_name, exc)
            return False

    async def _release_dist_lock(self) -> None:
        """Release the distributed lock, cancelling the heartbeat task."""
        if self._dist_lock is not None:
            try:
                from utils.distributed_lock import DistributedLock

                if isinstance(self._dist_lock, DistributedLock):
                    ht = getattr(self._dist_lock, "_heartbeat_task", None)
                    if ht and not ht.done():
                        ht.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await ht
                    await self._dist_lock.release()
            except Exception as exc:
                logger.warning("{} lock release failed: {}", self.source_name, exc)
            finally:
                self._dist_lock = None

    # ── Trigger / Resume / Run lifecycle ───────────────────────────────────

    async def trigger(
        self,
        *,
        run_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Start a source ingestion, auto-resuming from checkpoint if one exists.

        If a checkpoint from a previous interrupted run is found, the
        ingestion resumes from where it left off.

        Args:
            run_id: Optional run UUID (auto-generated if omitted).
            config: Source-specific configuration passed to the adapter.

        Returns:
            Progress dict, or ``None`` if the runner is busy or locked.
        """
        # Check for an existing checkpoint — resume instead of starting fresh
        checkpoint = await self.load_checkpoint()
        if checkpoint and checkpoint.get("status") != "completed":
            from loguru import logger

            logger.info(
                "{} — checkpoint found, resuming instead of fresh trigger", self.source_name
            )
            # Merge caller-provided config into checkpoint config so new
            # settings (e.g. a freshly added API key) take effect on resume.
            if config:
                cp_config = checkpoint.get("config", {})
                cp_config.update(config)
                checkpoint["config"] = cp_config
                await self.save_checkpoint(checkpoint)
            return await self.resume()

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
            self._message = f"Starting {self.source_name}…"

        asyncio.create_task(self._safe_run(is_resume=False, config=config or {}))
        return self.progress

    async def resume(self) -> dict[str, Any] | None:
        """Resume from checkpoint.

        Returns:
            Progress dict, or ``None`` if busy or no checkpoint to resume.
        """
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
            self._message = f"Resuming {self.source_name} ({self._synced} already processed)…"

        asyncio.create_task(
            self._safe_run(
                is_resume=True,
                checkpoint=checkpoint,
                config=checkpoint.get("config", {}),
            )
        )
        return self.progress

    async def _safe_run(self, **kwargs: Any) -> None:  # noqa: ANN401
        """Wrapper that catches exceptions and sets terminal status."""
        try:
            await self._broadcast()
            await self._execute(**kwargs)
            self._status = "completed"
            self._message = f"{self.source_name} completed ({self._synced} processed)"
            await self.clear_checkpoint()
            await self._broadcast(type="source_completed")
            logger.info("{} completed — {} processed", self.source_name, self._synced)
        except asyncio.CancelledError:
            self._status = "cancelled"
            self._message = f"{self.source_name} cancelled"
            await self._broadcast(type="source_cancelled")
            logger.info("{} cancelled at {} processed", self.source_name, self._synced)
        except Exception as exc:
            self._status = "failed"
            self._error = str(exc)
            self._message = f"{self.source_name} failed: {exc}"
            await self._broadcast(type="source_failed")
            logger.error("{} failed: {}", self.source_name, exc)
        finally:
            await self._release_dist_lock()

    # ── Core execution ─────────────────────────────────────────────────────

    async def _execute(
        self,
        *,
        is_resume: bool = False,
        checkpoint: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Run the adapter fetch → upsert pipeline with periodic checkpointing.

        On resume, restores adapter state from the checkpoint and skips
        already-processed entries.  On cancellation, saves a checkpoint
        so the run can be resumed later.

        Args:
            is_resume: Whether this is a resumed run.
            checkpoint: Checkpoint dict (when resuming).
            config: Source-specific adapter configuration.
        """
        db = self._get_library_db()
        config = config or {}

        resume_state: dict[str, Any] | None = None
        if is_resume and checkpoint:
            resume_state = checkpoint.get("adapter_state")

        # On fresh runs (not resume), clean up stale entries from previous
        # ingestion formats (e.g. version-specific CPE upstream_ids).
        if not is_resume:
            stale = await db["library_entries"].delete_many(
                {
                    "source": self.source_name,
                    "upstream_id": {"$regex": "^cpe:"},  # old CPE-format keys
                }
            )
            if stale.deleted_count:
                logger.info(
                    "{} — cleaned up {} stale version-specific entries",
                    self.source_name,
                    stale.deleted_count,
                )

        run = await self._restore_or_create_run(db, is_resume, checkpoint)
        total_processed = checkpoint.get("synced", 0) if (is_resume and checkpoint) else 0

        await self._update(
            message=f"{'Resuming' if is_resume else 'Starting'} {self.source_name} ingestion…",
            synced=total_processed,
        )

        try:
            async for raw_entry in self._adapter.fetch(config, resume_state=resume_state):
                self.check_cancelled()

                try:
                    markers: list[dict[str, Any]] = []
                    for pattern in raw_entry.patterns:
                        marker = LibraryMarker(
                            pattern=pattern,
                            display_name=raw_entry.name,
                            source_detail=raw_entry.upstream_id,
                            added_by=self.source_name,
                        )
                        markers.append(marker.model_dump(by_alias=True))

                    entry_data: dict[str, Any] = {
                        "name": raw_entry.name,
                        "vendor": raw_entry.vendor,
                        "category": raw_entry.category,
                        "description": raw_entry.description,
                        "tags": raw_entry.tags,
                        "markers": markers,
                        "source": self.source_name,
                        "upstream_id": raw_entry.upstream_id,
                        "upstream_version": raw_entry.version or None,
                        "status": "published",
                        "submitted_by": "system",
                    }

                    # Cross-source dedup: if an entry with the same name
                    # already exists from a different source, merge patterns
                    # into that entry instead of creating a duplicate.
                    existing = await db["library_entries"].find_one(
                        {
                            "name": {"$regex": f"^{raw_entry.name}$", "$options": "i"},
                            "source": {"$ne": self.source_name},
                        }
                    )
                    if existing:
                        # Merge new patterns that don't already exist
                        existing_patterns = {
                            m.get("pattern", "").lower() for m in existing.get("markers", [])
                        }
                        new_markers = [
                            m
                            for m in markers
                            if m.get("pattern", "").lower() not in existing_patterns
                        ]
                        if new_markers:
                            await db["library_entries"].update_one(
                                {"_id": existing["_id"]},
                                {
                                    "$push": {"markers": {"$each": new_markers}},
                                    "$addToSet": {"tags": {"$each": raw_entry.tags}},
                                    "$set": {"updated_at": utc_now()},
                                },
                            )
                        run.entries_updated += 1
                    else:
                        _entry_id, was_created = await repository.upsert_entry_by_upstream(
                            db,
                            self.source_name,
                            raw_entry.upstream_id,
                            entry_data,
                        )
                        if was_created:
                            run.entries_created += 1
                        else:
                            run.entries_updated += 1

                except Exception as exc:
                    run.errors.append(f"{raw_entry.upstream_id}: {exc}")
                    run.entries_skipped += 1
                    if len(run.errors) > 100:
                        run.errors.append("... truncated (>100 errors)")
                        break

                total_processed += 1
                self._synced = total_processed

                if total_processed % _BROADCAST_INTERVAL == 0:
                    await self._update(
                        message=f"Processing {self.source_name} ({total_processed} entries)…",
                        synced=total_processed,
                    )

                if total_processed % _CHECKPOINT_INTERVAL == 0:
                    await self._save_progress_checkpoint(
                        run,
                        total_processed,
                        config,
                        "running",
                    )
                    await repository.update_ingestion_run(
                        db,
                        run.id,
                        {
                            "entries_created": run.entries_created,
                            "entries_updated": run.entries_updated,
                            "entries_skipped": run.entries_skipped,
                            "errors": run.errors,
                        },
                    )

        except asyncio.CancelledError:
            await self._save_progress_checkpoint(run, total_processed, config, "cancelled")
            self._finalize_run(run, "cancelled")
            await self._persist_run(db, run)
            raise

        except Exception as exc:
            logger.error("Ingestion pipeline error for {}: {}", self.source_name, exc)
            run.errors.append(f"Pipeline error: {exc}")
            self._finalize_run(run, "failed")
            await self._persist_run(db, run)
            raise

        self._finalize_run(run, "completed")
        await self._persist_run(db, run)

        logger.info(
            "Ingestion {} completed: created={}, updated={}, skipped={}, errors={}",
            self.source_name,
            run.entries_created,
            run.entries_updated,
            run.entries_skipped,
            len(run.errors),
        )

    # ── Execution helpers ──────────────────────────────────────────────────

    async def _restore_or_create_run(
        self,
        db: Any,  # noqa: ANN401
        is_resume: bool,
        checkpoint: dict[str, Any] | None,
    ) -> IngestionRun:
        """Create a new IngestionRun or restore counters from checkpoint.

        Args:
            db: Library database handle.
            is_resume: Whether this is a resumed run.
            checkpoint: Checkpoint dict (when resuming).

        Returns:
            IngestionRun entity with counters initialised.
        """
        if is_resume and checkpoint:
            run = IngestionRun(
                source=self.source_name,
                entries_created=checkpoint.get("entries_created", 0),
                entries_updated=checkpoint.get("entries_updated", 0),
                entries_skipped=checkpoint.get("entries_skipped", 0),
                errors=checkpoint.get("errors", []),
            )
            ingestion_run_id = checkpoint.get("ingestion_run_id")
            if ingestion_run_id:
                run.id = ingestion_run_id
            else:
                await repository.insert_ingestion_run(db, run)
        else:
            run = IngestionRun(source=self.source_name)
            await repository.insert_ingestion_run(db, run)
        return run

    async def _save_progress_checkpoint(
        self,
        run: IngestionRun,
        total_processed: int,
        config: dict[str, Any],
        status: str,
    ) -> None:
        """Save current progress as a checkpoint for resume.

        Args:
            run: Current ingestion run entity.
            total_processed: Entries processed so far.
            config: Adapter configuration (persisted for resume).
            status: Checkpoint status (``running`` or ``cancelled``).
        """
        adapter_state = self._adapter.get_resume_state()
        await self.save_checkpoint(
            {
                "run_id": self._run_id,
                "ingestion_run_id": run.id,
                "source": self.source_name,
                "synced": total_processed,
                "entries_created": run.entries_created,
                "entries_updated": run.entries_updated,
                "entries_skipped": run.entries_skipped,
                "errors": run.errors[-10:],
                "config": config,
                "adapter_state": adapter_state,
                "status": status,
            }
        )

    @staticmethod
    def _finalize_run(run: IngestionRun, status: str) -> None:
        """Set terminal status and timestamp on the run entity."""
        run.status = status  # type: ignore[assignment]
        run.completed_at = utc_now()

    @staticmethod
    async def _persist_run(db: Any, run: IngestionRun) -> None:  # noqa: ANN401
        """Write final run state to ``library_ingestion_runs``."""
        await repository.update_ingestion_run(
            db,
            run.id,
            {
                "status": run.status,
                "completed_at": run.completed_at,
                "entries_created": run.entries_created,
                "entries_updated": run.entries_updated,
                "entries_skipped": run.entries_skipped,
                "errors": run.errors,
            },
        )
