"""CrowdStrike groups phase runner — fetches host groups and builds ID→name map."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.collections import GROUPS, SYNC_META
from domains.sync.phase_runner import PhaseRunner


class CSGroupsPhaseRunner(PhaseRunner):
    """Sync CrowdStrike host groups into the canonical ``groups`` collection."""

    phase_name = "cs_groups"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        cs_client = kwargs.get("cs_client")
        if not cs_client:
            cs_client = await self._create_cs_client()
        await self._sync_groups(cs_client)

    async def _sync_groups(self, client: Any) -> None:  # noqa: ANN401
        from pymongo import ReplaceOne

        from utils.dt import utc_now

        from .normalizer import normalize_group

        db = await self._get_db()
        sync_started_at = utc_now().isoformat()
        await self._update(message="Fetching CrowdStrike host groups…")

        group_map = await client.get_host_groups()
        logger.info("CS Groups — fetched {} host groups", len(group_map))

        # Build full group documents by re-querying combined endpoint
        # for richer metadata (assignment_rule, created_timestamp, etc.)
        from .client import CrowdStrikeClient

        if isinstance(client, CrowdStrikeClient):
            resp = await client._call(
                client._host_groups.query_combined_host_groups,
                limit=500,
            )
            body = resp.get("body", {})
            raw_groups = body.get("resources", [])
        else:
            # Mock/test path — build minimal group dicts from the map
            raw_groups = [{"id": gid, "name": gname} for gid, gname in group_map.items()]

        docs: list[dict] = []
        for raw_group in raw_groups:
            self.check_cancelled()
            doc = normalize_group(raw_group)
            docs.append(doc)

        if docs:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
            await db[GROUPS].bulk_write(ops, ordered=False)

        # Delete groups from this source that no longer exist
        current_ids = [d["_id"] for d in docs]
        if current_ids:
            await db[GROUPS].delete_many(
                {
                    "source": "crowdstrike",
                    "_id": {"$nin": current_ids},
                }
            )

        await db[SYNC_META].update_one(
            {"_id": "crowdstrike"},
            {"$set": {"groups_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = len(docs)
        self._total = len(docs)
        await self._update(message=f"Synced {self._synced} CrowdStrike groups")
        logger.info("CS Groups phase — {} groups synced", self._synced)

    @staticmethod
    async def _create_cs_client() -> Any:  # noqa: ANN401
        """Create a CrowdStrikeClient from application settings."""
        from config import get_settings

        from .client import CrowdStrikeClient

        settings = get_settings()
        return CrowdStrikeClient(
            client_id=settings.cs_client_id,
            client_secret=settings.cs_client_secret,
            base_url=settings.cs_base_url,
            member_cid=settings.cs_member_cid or None,
        )
