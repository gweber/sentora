"""Sites phase runner — fetches and upserts all sites."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.collections import SITES, SYNC_META

from ..phase_runner import PhaseRunner


class SitesPhaseRunner(PhaseRunner):
    phase_name = "sites"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        s1_client = kwargs.get("s1_client")
        own_client = False

        if not s1_client:
            s1_client = await self._create_s1_client()
            own_client = True

        try:
            await self._sync_sites(s1_client)
        finally:
            if own_client:
                await s1_client.close()

    async def _sync_sites(self, client: Any) -> None:  # noqa: ANN401
        """Sites always fetches all — no incremental mode."""
        from utils.dt import utc_now

        from ..normalizer import normalize_site

        db = await self._get_db()
        sync_started_at = utc_now().isoformat()

        await self._update(message="Fetching sites…")

        from pymongo import ReplaceOne

        sites_docs: list[dict] = []
        async for raw_site in client.get_sites():
            self.check_cancelled()
            doc = normalize_site(raw_site)
            sites_docs.append(doc)

        if sites_docs:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in sites_docs]
            await db[SITES].bulk_write(ops, ordered=False)

        if sites_docs:
            current_ids = [d["_id"] for d in sites_docs]
            await db[SITES].delete_many({"_id": {"$nin": current_ids}})
        else:
            logger.warning("Sites — source returned 0 sites, skipping stale cleanup")

        await db[SYNC_META].update_one(
            {"_id": "global"},
            {"$set": {"sites_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = len(sites_docs)
        self._total = len(sites_docs)
        await self._update(message=f"Synced {self._synced} sites")
        logger.info("Sites phase — {} sites synced", self._synced)
