"""MongoDB-based distributed advisory locks.

Provides cross-process mutual exclusion for multi-worker deployments.
Uses a ``distributed_locks`` collection with a TTL index so stale locks
are automatically cleaned up if the holder crashes without releasing.

Usage::

    from utils.distributed_lock import DistributedLock

    async with DistributedLock(db, "sync_pipeline", ttl_seconds=300):
        # Only one worker runs this block at a time
        await run_sync()
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from types import TracebackType

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from utils.dt import utc_now

_COLLECTION = "distributed_locks"


class DistributedLock:
    """MongoDB advisory lock with automatic TTL expiry and heartbeat.

    Attributes:
        db: The MongoDB database handle.
        lock_name: Unique name identifying the lock.
        ttl_seconds: Time-to-live in seconds — the lock auto-expires if not refreshed.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        lock_name: str,
        ttl_seconds: int = 300,
    ) -> None:
        self.db = db
        self.lock_name = lock_name
        self.ttl_seconds = ttl_seconds
        self._owner_id: str = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._heartbeat_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._acquired = False
        self.lost: asyncio.Event = asyncio.Event()

    async def acquire(self) -> bool:
        """Try to acquire the lock.

        Uses an atomic upsert with a condition that either the lock does not
        exist or its TTL has expired.

        Returns:
            True if the lock was acquired, False if another holder owns it.
        """
        from datetime import timedelta

        now = utc_now()
        expires_at = now + timedelta(seconds=self.ttl_seconds)

        try:
            # Try to insert a new lock document
            await self.db[_COLLECTION].insert_one(
                {
                    "_id": self.lock_name,
                    "owner_id": self._owner_id,
                    "acquired_at": now,
                    "expires_at": expires_at,
                }
            )
            self._acquired = True
            logger.debug("Distributed lock '{}' acquired", self.lock_name)
            return True
        except DuplicateKeyError:
            pass

        # Lock document exists — check if it has expired
        result = await self.db[_COLLECTION].update_one(
            {"_id": self.lock_name, "expires_at": {"$lt": now}},
            {"$set": {"owner_id": self._owner_id, "acquired_at": now, "expires_at": expires_at}},
        )
        if result.modified_count > 0:
            self._acquired = True
            logger.debug("Distributed lock '{}' acquired (expired previous holder)", self.lock_name)
            return True

        logger.debug("Distributed lock '{}' is held by another process", self.lock_name)
        return False

    async def release(self) -> None:
        """Release the lock by deleting the lock document."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        if self._acquired:
            await self.db[_COLLECTION].delete_one(
                {"_id": self.lock_name, "owner_id": self._owner_id}
            )
            self._acquired = False
            logger.debug("Distributed lock '{}' released", self.lock_name)

    async def _heartbeat(self) -> None:
        """Periodically refresh the lock TTL while held.

        Runs as a background task, refreshing at half the TTL interval
        to provide a safety margin.  Filters on owner_id to avoid
        extending another worker's lock if ours expired and was stolen.
        """
        from datetime import timedelta

        interval = max(1, self.ttl_seconds // 2)
        try:
            while True:
                await asyncio.sleep(interval)
                new_expires = utc_now() + timedelta(seconds=self.ttl_seconds)
                result = await self.db[_COLLECTION].update_one(
                    {"_id": self.lock_name, "owner_id": self._owner_id},
                    {"$set": {"expires_at": new_expires}},
                )
                if result.matched_count > 0:
                    logger.trace("Distributed lock '{}' heartbeat — TTL refreshed", self.lock_name)
                else:
                    # Lock was lost (expired and taken by another worker)
                    logger.warning(
                        "Distributed lock '{}' lost — another worker acquired it", self.lock_name
                    )
                    self._acquired = False
                    self.lost.set()
                    break
        except asyncio.CancelledError:
            pass

    async def __aenter__(self) -> DistributedLock:
        """Acquire the lock as an async context manager.

        Raises:
            RuntimeError: If the lock could not be acquired.
        """
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Could not acquire distributed lock '{self.lock_name}'")
        # Start heartbeat to keep the lock alive
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Release the lock when exiting the context manager."""
        await self.release()
