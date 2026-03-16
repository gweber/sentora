"""Tags phase runner — fetches and upserts all S1 tags."""

from __future__ import annotations

from typing import Any

from loguru import logger

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

        await self._update(message="Fetching S1 tags…")

        from pymongo import ReplaceOne

        tags_docs: list[dict] = []
        async for raw_tag in client.get_tags():
            self.check_cancelled()
            doc = normalize_tag(raw_tag, sync_started_at)
            tags_docs.append(doc)

        if tags_docs:
            ops = [ReplaceOne({"s1_tag_id": d["s1_tag_id"]}, d, upsert=True) for d in tags_docs]
            await db["s1_tags"].bulk_write(ops, ordered=False)

        # Only clean up stale tags if we actually received data.
        # An empty response likely means an API error — never wipe the collection.
        if tags_docs:
            current_ids = [d["s1_tag_id"] for d in tags_docs]
            await db["s1_tags"].delete_many({"s1_tag_id": {"$nin": current_ids}})
        else:
            logger.warning("Tags — S1 returned 0 tags, skipping stale cleanup")

        await db["s1_sync_meta"].update_one(
            {"_id": "global"},
            {"$set": {"tags_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = len(tags_docs)
        self._total = len(tags_docs)
        await self._update(message=f"Synced {self._synced} tags")
        logger.info("Tags phase — {} tags synced", self._synced)
