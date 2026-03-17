"""CrowdStrike agents phase runner — scroll-based sync with checkpoint resume."""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.collections import AGENTS, GROUPS, INSTALLED_APPS, SYNC_META
from domains.sync.phase_runner import PhaseRunner


class CSAgentsPhaseRunner(PhaseRunner):
    """Sync CrowdStrike hosts into the canonical ``agents`` collection.

    Uses ``QueryDevicesByFilterScroll`` (cursor-based, no maximum) to page
    through all hosts.  Since scroll cursors expire after ~2 minutes, resume
    after interruption uses a ``modified_timestamp`` FQL filter instead of
    persisting the expired cursor.
    """

    phase_name = "cs_agents"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        mode: str = kwargs.get("mode", "full")
        cs_client = kwargs.get("cs_client")
        is_resume: bool = kwargs.get("is_resume", False)
        checkpoint: dict[str, Any] | None = kwargs.get("checkpoint")

        if not cs_client:
            from .sync_groups import CSGroupsPhaseRunner

            cs_client = await CSGroupsPhaseRunner._create_cs_client()

        await self._sync_agents(cs_client, mode, is_resume, checkpoint)

    async def _sync_agents(
        self,
        client: Any,  # noqa: ANN401
        mode: str,
        is_resume: bool,
        checkpoint: dict[str, Any] | None,
    ) -> None:
        from pymongo import ReplaceOne

        from utils.dt import utc_now

        from .normalizer import normalize_host

        db = await self._get_db()
        sync_started_at = utc_now().isoformat()

        # Load group_name_map from DB for denormalization
        group_name_map: dict[str, str] = {}
        async for doc in db[GROUPS].find({"source": "crowdstrike"}, {"source_id": 1, "name": 1}):
            group_name_map[doc["source_id"]] = doc["name"]

        # Resolve mode
        meta = await db[SYNC_META].find_one({"_id": "crowdstrike"})
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
                logger.warning("CS Agents — discarding checkpoint (mode {} != {})", cp_mode, mode)
                await self.clear_checkpoint()
                checkpoint = None
                is_resume = False

        agents_synced = checkpoint.get("synced", 0) if checkpoint else 0
        agents_total = checkpoint.get("total", 0) if checkpoint else 0

        # Build FQL filter
        filter_fql = ""
        if is_resume and checkpoint and checkpoint.get("resume_timestamp"):
            # Resume after interruption: fetch hosts modified since last successful batch
            filter_fql = f"modified_timestamp:>'{checkpoint['resume_timestamp']}'"
            logger.info(
                "CS Agents — resuming from modified_timestamp > {} ({} already synced)",
                checkpoint["resume_timestamp"],
                agents_synced,
            )
            await self._update(
                message=f"Resuming CrowdStrike agents ({agents_synced} already synced)…",
                synced=agents_synced,
                total=agents_total,
            )
        elif not is_full and last_sync_at:
            # Incremental: only hosts modified since last successful sync
            filter_fql = f"modified_timestamp:>'{last_sync_at}'"
            await self._update(message="Refreshing CrowdStrike agents…")
        else:
            await self._update(message="Full sync — fetching all CrowdStrike hosts…")

        buffer: list[dict] = []
        last_batch_at = sync_started_at

        async for batch_total, host_details in client.scroll_all_hosts(
            filter_fql=filter_fql,
        ):
            self.check_cancelled()

            if batch_total > 0 and agents_total == 0:
                agents_total = batch_total

            for cs_host in host_details:
                doc = normalize_host(cs_host, group_name_map)
                doc["synced_at"] = sync_started_at
                buffer.append(doc)

            # Flush buffer
            if len(buffer) >= 500:
                ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in buffer]
                await db[AGENTS].bulk_write(ops, ordered=False)
                agents_synced += len(buffer)
                last_batch_at = utc_now().isoformat()
                buffer.clear()

                await self.save_checkpoint(
                    {
                        "synced": agents_synced,
                        "total": agents_total,
                        "mode": mode,
                        "run_id": self._run_id,
                        "resume_timestamp": last_batch_at,
                    }
                )
                await self._update(
                    message=(
                        f"{'Refreshing' if not is_full else 'Syncing'}"
                        f" CrowdStrike agents ({agents_synced}"
                        f"{f' / {agents_total}' if agents_total else ''})"
                        "\u2026"
                    ),
                    synced=agents_synced,
                    total=agents_total,
                )

        # Flush remaining buffer
        if buffer:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in buffer]
            await db[AGENTS].bulk_write(ops, ordered=False)
            agents_synced += len(buffer)
            buffer.clear()

        # Full sync: delete stale agents from this source
        if is_full:
            stale = await db[AGENTS].delete_many(
                {"source": "crowdstrike", "synced_at": {"$ne": sync_started_at}},
            )
            if stale.deleted_count:
                logger.info("CS Agents — removed {} stale agents", stale.deleted_count)
                # Also remove installed_apps for stale agents
                await db[INSTALLED_APPS].delete_many(
                    {"source": "crowdstrike", "synced_at": {"$ne": sync_started_at}},
                )

        # Record CS-specific timestamp
        await db[SYNC_META].update_one(
            {"_id": "crowdstrike"},
            {"$set": {"agents_synced_at": sync_started_at}},
            upsert=True,
        )

        self._synced = agents_synced
        self._total = agents_total
        await self._update(
            message=(
                f"{'Refreshed' if not is_full else 'Synced'} {agents_synced} CrowdStrike agents"
            ),
            synced=agents_synced,
            total=agents_total,
        )
        logger.info("CS Agents phase — {} agents synced", agents_synced)
