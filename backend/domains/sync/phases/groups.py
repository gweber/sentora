"""Groups phase runner — fetches and upserts groups."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.collections import GROUPS, SITES, SYNC_META

from ..phase_runner import PhaseRunner


class GroupsPhaseRunner(PhaseRunner):
    phase_name = "groups"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        mode: str = kwargs.get("mode", "full")
        s1_client = kwargs.get("s1_client")
        own_client = False

        if not s1_client:
            s1_client = await self._create_s1_client()
            own_client = True

        try:
            await self._sync_groups(s1_client, mode)
        finally:
            if own_client:
                await s1_client.close()

    async def _sync_groups(self, client: Any, mode: str) -> None:  # noqa: ANN401
        from utils.dt import utc_now

        from ..normalizer import normalize_group

        db = await self._get_db()

        # Read own timestamp once, then decide mode
        meta = await db[SYNC_META].find_one({"_id": "global"})
        last_sync_at = meta.get("groups_synced_at") if meta else None
        if mode == "auto":
            is_full = last_sync_at is None
            mode = "full" if is_full else "incremental"
        else:
            is_full = mode == "full"

        sync_started_at = utc_now().isoformat()
        await self._update(message="Fetching groups…")

        # Load site_name_map from DB (soft dependency — for denormalization)
        site_name_map: dict[str, str] = {}
        async for doc in db[SITES].find({}, {"source_id": 1, "name": 1}):
            site_name_map[doc["source_id"]] = doc["name"]

        updated_since = None if is_full else last_sync_at

        from pymongo import ReplaceOne

        groups_docs: list[dict] = []
        async for raw_group in client.get_groups(updated_since=updated_since):
            self.check_cancelled()
            doc = normalize_group(raw_group, site_name_map)
            groups_docs.append(doc)

        if groups_docs:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in groups_docs]
            await db[GROUPS].bulk_write(ops, ordered=False)

        if is_full:
            current_ids = [d["_id"] for d in groups_docs]
            if current_ids:
                await db[GROUPS].delete_many({"_id": {"$nin": current_ids}})

        # Record own timestamp
        await db[SYNC_META].update_one(
            {"_id": "global"},
            {"$set": {"groups_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = len(groups_docs)
        self._total = len(groups_docs)
        await self._update(message=f"Synced {self._synced} groups ({mode})")
        logger.info("Groups phase — {} groups synced ({})", self._synced, mode)
