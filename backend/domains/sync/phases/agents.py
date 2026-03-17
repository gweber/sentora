"""Agents phase runner — fetches agents (full or incremental) with checkpoint resume."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.collections import AGENTS, GROUPS, INSTALLED_APPS, SYNC_META

from ..phase_runner import PhaseRunner


class AgentsPhaseRunner(PhaseRunner):
    phase_name = "agents"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        mode: str = kwargs.get("mode", "full")
        s1_client = kwargs.get("s1_client")
        is_resume: bool = kwargs.get("is_resume", False)
        checkpoint: dict[str, Any] | None = kwargs.get("checkpoint")
        own_client = False

        if not s1_client:
            s1_client = await self._create_s1_client()
            own_client = True

        try:
            await self._sync_agents(s1_client, mode, is_resume, checkpoint)
        finally:
            if own_client:
                await s1_client.close()

    async def _sync_agents(
        self,
        client: Any,  # noqa: ANN401
        mode: str,
        is_resume: bool,
        checkpoint: dict[str, Any] | None,
    ) -> None:
        from pymongo import ReplaceOne

        from utils.dt import utc_now

        from ..normalizer import normalize_agent
        from ..s1_client import make_agent_cursor

        db = await self._get_db()
        sync_started_at = utc_now().isoformat()

        page_size = await self._load_page_size(db, "page_size_agents")

        # Load group_name_map from DB (soft dependency — for denormalization)
        group_name_map: dict[str, str] = {}
        async for doc in db[GROUPS].find({}, {"source_id": 1, "name": 1}):
            group_name_map[doc["source_id"]] = doc["name"]

        # Resolve mode and last_sync_at from own timestamp
        meta = await db[SYNC_META].find_one({"_id": "global"})
        last_sync_at = meta.get("agents_synced_at") if meta else None
        if mode == "auto":
            is_full = last_sync_at is None
            mode = "full" if is_full else "incremental"
        else:
            is_full = mode == "full"

        # Check checkpoint mode match
        if is_resume and checkpoint:
            cp_mode = checkpoint.get("mode")
            if cp_mode and cp_mode != mode:
                logger.warning("Agents — discarding checkpoint (mode {} != {})", cp_mode, mode)
                await self.clear_checkpoint()
                checkpoint = None
                is_resume = False

        agents_synced = checkpoint.get("synced", 0) if checkpoint else 0
        agents_total = checkpoint.get("total", 0) if checkpoint else 0
        full_sync_buffer: list[dict] = []

        resume_cursor = None
        if checkpoint and checkpoint.get("last_id"):
            resume_cursor = make_agent_cursor(int(checkpoint["last_id"]))
            logger.info(
                "Agents — resuming from id {} ({} already synced)",
                checkpoint["last_id"],
                agents_synced,
            )
            await self._update(
                message=f"Resuming agents ({agents_synced} already synced)…",
                synced=agents_synced,
                total=agents_total,
            )
        elif is_full:
            await self._update(message="Full sync — fetching all agents…")
        else:
            await self._update(message="Refreshing agents…")

        async for page_total, _page_cursor, raw_agent in client.get_agents(
            updated_since=last_sync_at if not is_full else None,
            page_size=page_size,
            resume_cursor=resume_cursor,
        ):
            self.check_cancelled()

            if page_total is not None:
                agents_total = page_total

            doc = normalize_agent(raw_agent, group_name_map)
            doc["synced_at"] = sync_started_at
            aid = doc["source_id"]

            full_sync_buffer.append(doc)
            # Flush buffer periodically to avoid OOM on large tenants
            if len(full_sync_buffer) >= 500:
                ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in full_sync_buffer]
                await db[AGENTS].bulk_write(ops, ordered=False)
                full_sync_buffer.clear()

            agents_synced += 1
            if agents_synced % 100 == 0:
                await self.save_checkpoint(
                    {
                        "last_id": aid,
                        "synced": agents_synced,
                        "total": agents_total,
                        "mode": mode,
                        "run_id": self._run_id,
                    }
                )
                await self._update(
                    message=(
                        f"{'Refreshing' if not is_full else 'Syncing'}"
                        f" agents ({agents_synced}"
                        f"{f' / {agents_total}' if agents_total else ''})"
                        "\u2026"
                    ),
                    synced=agents_synced,
                    total=agents_total,
                )

        # Flush remaining buffer
        if full_sync_buffer:
            ops = [ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in full_sync_buffer]
            await db[AGENTS].bulk_write(ops, ordered=False)
            full_sync_buffer.clear()

        if is_full:
            # Delete agents not touched in this sync — uses synced_at timestamp
            # instead of tracking 150k+ IDs in memory
            stale = await db[AGENTS].delete_many(
                {"synced_at": {"$ne": sync_started_at}},
            )
            if stale.deleted_count:
                logger.info("Agents — removed {} stale agents", stale.deleted_count)

        # Handle decommissioned agents (incremental only)
        if not is_full and last_sync_at:
            decom_ids = await client.get_decommissioned_agent_ids(
                updated_since=last_sync_at,
            )
            if decom_ids:
                await db[AGENTS].delete_many({"source_id": {"$in": decom_ids}})
                await db[INSTALLED_APPS].delete_many({"agent_id": {"$in": decom_ids}})
                logger.info("Agents — removed {} decommissioned", len(decom_ids))

        # Record agents-specific timestamp
        await db[SYNC_META].update_one(
            {"_id": "global"},
            {"$set": {"agents_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = agents_synced
        self._total = agents_total
        await self._update(
            message=f"{'Refreshed' if not is_full else 'Synced'} {agents_synced} agents",
            synced=agents_synced,
            total=agents_total,
        )
        logger.info("Agents phase — {} agents synced", agents_synced)
