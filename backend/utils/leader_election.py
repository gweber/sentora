"""MongoDB-based leader election for multi-worker deployments.

Only one worker at a time holds leadership for a given election name.
The leader maintains its claim via periodic heartbeats. If a leader
crashes (misses heartbeats), its claim expires and another worker
can take over.

Timestamps are stored as native BSON ``datetime`` objects so MongoDB
can compare them correctly (no ISO-string lexicographic fragility).
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from utils.dt import utc_now

_COLLECTION = "leader_election"


class LeaderElection:
    """MongoDB-based leader election with automatic TTL expiry.

    Attributes:
        db: The MongoDB database handle.
        name: Unique name identifying the election (e.g. ``"sync_scheduler"``).
        ttl_seconds: Time-to-live in seconds — leadership expires if not refreshed.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        name: str,
        ttl_seconds: int = 60,
    ) -> None:
        self.db = db
        self.name = name
        self.ttl_seconds = ttl_seconds
        self._worker_id: str = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

    async def try_become_leader(self) -> bool:
        """Attempt to become the leader for this election.

        Uses an atomic upsert: try to insert a new claim or update an
        existing one whose TTL has expired.

        Returns:
            True if this worker is now the leader, False otherwise.
        """
        now = utc_now()
        expires_at = now + timedelta(seconds=self.ttl_seconds)

        # Try to insert a fresh leadership claim
        try:
            await self.db[_COLLECTION].insert_one(
                {
                    "_id": self.name,
                    "worker_id": self._worker_id,
                    "acquired_at": now,
                    "expires_at": expires_at,
                }
            )
            logger.info(
                "Leader election '{}' — this worker ({}) is now leader",
                self.name,
                self._worker_id,
            )
            return True
        except DuplicateKeyError:
            pass

        # Document exists — check if this worker already holds it
        result = await self.db[_COLLECTION].update_one(
            {"_id": self.name, "worker_id": self._worker_id},
            {"$set": {"expires_at": expires_at}},
        )
        if result.modified_count > 0:
            logger.debug(
                "Leader election '{}' — refreshed (already leader)",
                self.name,
            )
            return True

        # Check if the current leader's claim has expired (native datetime comparison)
        result = await self.db[_COLLECTION].update_one(
            {"_id": self.name, "expires_at": {"$lt": now}},
            {
                "$set": {
                    "worker_id": self._worker_id,
                    "acquired_at": now,
                    "expires_at": expires_at,
                }
            },
        )
        if result.modified_count > 0:
            logger.info(
                "Leader election '{}' — this worker ({}) took over from expired leader",
                self.name,
                self._worker_id,
            )
            return True

        logger.debug(
            "Leader election '{}' — another worker holds leadership",
            self.name,
        )
        return False

    async def heartbeat(self) -> None:
        """Refresh the leadership TTL.

        No-op if this worker is not the current leader.
        """
        expires_at = utc_now() + timedelta(seconds=self.ttl_seconds)
        result = await self.db[_COLLECTION].update_one(
            {"_id": self.name, "worker_id": self._worker_id},
            {"$set": {"expires_at": expires_at}},
        )
        if result.modified_count > 0:
            logger.trace("Leader election '{}' — heartbeat sent", self.name)

    async def resign(self) -> None:
        """Voluntarily give up leadership.

        Only deletes the claim if this worker currently holds it.
        """
        result = await self.db[_COLLECTION].delete_one(
            {"_id": self.name, "worker_id": self._worker_id},
        )
        if result.deleted_count > 0:
            logger.info(
                "Leader election '{}' — worker {} resigned",
                self.name,
                self._worker_id,
            )
