"""Tags phase runner — fetches and upserts all source tags."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.collections import SOURCE_TAGS, SYNC_META

from ..phase_runner import PhaseRunner


class TagsPhaseRunner(PhaseRunner):
    phase_name = "tags"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        s1_client = kwargs.get("s1_client")
        own_client = False

        if not s1_client:
            s1_client = await self._create_s1_client()
            own_client = True

        try:
            await self._sync_tags(s1_client)
        finally:
            if own_client:
                await s1_client.close()

    async def _sync_tags(self, client: Any) -> None:  # noqa: ANN401
        from utils.dt import utc_now

        from ..normalizer import normalize_tag

        db = await self._get_db()
        sync_started_at = utc_now().isoformat()

        await self._update(message="Fetching source tags…")

        from pymongo import ReplaceOne

        tags_docs: list[dict] = []
        async for raw_tag in client.get_tags():
            self.check_cancelled()
            doc = normalize_tag(raw_tag, sync_started_at)
            tags_docs.append(doc)

        if tags_docs:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in tags_docs]
            await db[SOURCE_TAGS].bulk_write(ops, ordered=False)

        # Only clean up stale tags if we actually received data.
        # An empty response likely means an API error — never wipe the collection.
        if tags_docs:
            current_ids = [d["_id"] for d in tags_docs]
            await db[SOURCE_TAGS].delete_many({"_id": {"$nin": current_ids}})
        else:
            logger.warning("Tags — source returned 0 tags, skipping stale cleanup")

        await db[SYNC_META].update_one(
            {"_id": "global"},
            {"$set": {"tags_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = len(tags_docs)
        self._total = len(tags_docs)
        await self._update(message=f"Synced {self._synced} tags")
        logger.info("Tags phase — {} tags synced", self._synced)
