"""MongoDB-based pub/sub for cross-worker message passing.

Uses a capped collection for message storage with tailable cursor
polling for delivery. Falls back to periodic polling when change
streams are unavailable (standalone MongoDB without replica set).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING
from pymongo.errors import CollectionInvalid

from utils.dt import utc_now

_COLLECTION = "_pubsub_messages"
_CAPPED_SIZE = 10 * 1024 * 1024  # 10 MB
_CAPPED_MAX = 10_000
_POLL_INTERVAL = 0.5  # seconds


class PubSub:
    """MongoDB capped-collection pub/sub for cross-worker messaging.

    Publishes messages to a capped collection and subscribes via
    tailable cursor polling. Each subscriber receives messages
    published after it starts listening.

    Attributes:
        db: The MongoDB database handle.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        self.db = db
        self._initialized = False

    async def ensure_collection(self) -> None:
        """Create the capped collection if it does not already exist.

        Safe to call multiple times — silently ignores if the collection
        already exists.
        """
        if self._initialized:
            return

        try:
            await self.db.create_collection(
                _COLLECTION,
                capped=True,
                size=_CAPPED_SIZE,
                max=_CAPPED_MAX,
            )
            logger.info(
                "Created capped collection '{}' (size={}MB, max={})",
                _COLLECTION,
                _CAPPED_SIZE // (1024 * 1024),
                _CAPPED_MAX,
            )
        except CollectionInvalid:
            # Collection already exists
            pass

        self._initialized = True

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to the given channel.

        Args:
            channel: Channel name (e.g. ``"sync_events"``).
            message: Payload string to deliver to subscribers.
        """
        await self.ensure_collection()
        await self.db[_COLLECTION].insert_one(
            {
                "channel": channel,
                "payload": message,
                "created_at": utc_now(),
            }
        )
        logger.trace("PubSub — published to '{}': {}", channel, message[:80])

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str], Any],
    ) -> asyncio.Task:  # type: ignore[type-arg]
        """Subscribe to a channel and invoke *callback* for each new message.

        Starts a background ``asyncio.Task`` that uses a tailable cursor on
        the capped collection, falling back to periodic polling if the
        tailable cursor is not supported.

        Args:
            channel: Channel name to listen on.
            callback: Async or sync callable receiving the message payload string.

        Returns:
            The background task — cancel it to stop listening.
        """
        await self.ensure_collection()

        # Seed the collection with a dummy document if empty (tailable cursors
        # require at least one document to exist).
        count = await self.db[_COLLECTION].count_documents({})
        if count == 0:
            await self.db[_COLLECTION].insert_one(
                {
                    "channel": "__init__",
                    "payload": "",
                    "created_at": utc_now(),
                }
            )

        task = asyncio.create_task(self._poll_loop(channel, callback))
        return task

    async def _poll_loop(
        self,
        channel: str,
        callback: Callable[[str], Any],
    ) -> None:
        """Internal polling loop using a tailable cursor.

        Falls back to simple periodic queries if the tailable cursor
        fails (e.g. on standalone MongoDB without oplog).
        """
        try:
            await self._tailable_loop(channel, callback)
        except Exception as exc:
            logger.debug(
                "PubSub — tailable cursor failed for '{}', falling back to polling: {}",
                channel,
                exc,
            )
            await self._polling_fallback(channel, callback)

    async def _tailable_loop(
        self,
        channel: str,
        callback: Callable[[str], Any],
    ) -> None:
        """Read messages using a tailable await cursor on the capped collection."""
        # Find the last existing document ID so we only see new messages
        last_doc = await self.db[_COLLECTION].find_one(
            {"channel": channel},
            sort=[("$natural", -1)],
        )
        query: dict[str, Any] = {"channel": channel}
        if last_doc:
            query["_id"] = {"$gt": last_doc["_id"]}

        cursor = (
            self.db[_COLLECTION]
            .find(
                query,
                cursor_type=2,  # TAILABLE_AWAIT
            )
            .sort("$natural", ASCENDING)
        )

        try:
            while True:
                if not cursor.alive:  # type: ignore[truthy-function]
                    break
                try:
                    doc = await asyncio.wait_for(cursor.next(), timeout=_POLL_INTERVAL)
                    await self._dispatch(callback, doc["payload"])
                except (TimeoutError, StopAsyncIteration):
                    await asyncio.sleep(_POLL_INTERVAL)
        except asyncio.CancelledError:
            logger.debug("PubSub — tailable subscriber for '{}' cancelled", channel)
            raise

    async def _polling_fallback(
        self,
        channel: str,
        callback: Callable[[str], Any],
    ) -> None:
        """Simple polling fallback when tailable cursors are unavailable."""
        last_seen = utc_now()
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)
                cursor = (
                    self.db[_COLLECTION]
                    .find(
                        {
                            "channel": channel,
                            "created_at": {"$gt": last_seen},
                        }
                    )
                    .sort("created_at", ASCENDING)
                )

                async for doc in cursor:
                    await self._dispatch(callback, doc["payload"])
                    last_seen = doc["created_at"]
        except asyncio.CancelledError:
            logger.debug("PubSub — polling subscriber for '{}' cancelled", channel)
            raise

    @staticmethod
    async def _dispatch(callback: Callable[[str], Any], payload: str) -> None:
        """Invoke the subscriber callback, handling both sync and async callables."""
        try:
            result = callback(payload)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.error("PubSub — subscriber callback error: {}", exc)
