"""CrowdStrike applications phase runner — Falcon Discover API with cursor resume."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from domains.sources.collections import AGENTS, INSTALLED_APPS, SYNC_META
from domains.sync.phase_runner import PhaseRunner


class CSAppsPhaseRunner(PhaseRunner):
    """Sync CrowdStrike applications into the canonical ``installed_apps`` collection.

    Uses the Falcon Discover ``query_combined_applications`` endpoint with
    cursor-based pagination.  Supports checkpoint resume via the persisted
    cursor value.

    The default sync strategy is **hybrid**: on incremental syncs, only
    applications for hosts modified since the last sync are fetched.
    Full syncs page through all applications.
    """

    phase_name = "cs_apps"

    async def _execute(self, **kwargs: Any) -> None:  # noqa: ANN401
        mode: str = kwargs.get("mode", "full")
        cs_client = kwargs.get("cs_client")
        is_resume: bool = kwargs.get("is_resume", False)
        checkpoint: dict[str, Any] | None = kwargs.get("checkpoint")

        if not cs_client:
            from .sync_groups import CSGroupsPhaseRunner

            cs_client = await CSGroupsPhaseRunner._create_cs_client()

        await self._sync_apps(cs_client, mode, is_resume, checkpoint)

    async def _sync_apps(
        self,
        client: Any,  # noqa: ANN401
        mode: str,
        is_resume: bool,
        checkpoint: dict[str, Any] | None,
    ) -> None:
        from pymongo import UpdateOne

        from utils.dt import utc_now

        from .errors import CSDiscoverNotLicensedError
        from .normalizer import normalize_application

        db = await self._get_db()
        sync_started_at = utc_now().isoformat()

        # Resolve mode
        meta = await db[SYNC_META].find_one({"_id": "crowdstrike"})
        last_sync_at = meta.get("apps_synced_at") if meta else None

        if mode == "auto":
            is_full = last_sync_at is None
            mode = "full" if is_full else "incremental"
        else:
            is_full = mode == "full"

        # Check checkpoint mode match
        if is_resume and checkpoint:
            cp_mode = checkpoint.get("mode")
            if cp_mode and cp_mode != mode:
                logger.warning("CS Apps — discarding checkpoint (mode {} != {})", cp_mode, mode)
                await self.clear_checkpoint()
                checkpoint = None
                is_resume = False

        apps_synced = checkpoint.get("synced", 0) if checkpoint else 0
        apps_total = checkpoint.get("total", 0) if checkpoint else 0

        # Build FQL filter for incremental (hybrid strategy)
        filter_fql = ""
        if not is_full and last_sync_at:
            filter_fql = f"last_updated_timestamp:>'{last_sync_at}'"

        resume_msg = (
            f"Resuming CrowdStrike apps ({apps_synced} already synced)…"
            if is_resume and checkpoint
            else (
                "Fetching new CrowdStrike apps…"
                if not is_full
                else "Fetching all CrowdStrike applications…"
            )
        )
        await self._update(message=resume_msg, synced=apps_synced, total=apps_total)

        buf: list[Any] = []
        BATCH = 500

        from .errors import CSApiError, CSRateLimitError

        MAX_RETRIES = 3
        RATE_LIMIT_BACKOFF = 60
        API_ERROR_BACKOFF = 30

        for attempt in range(MAX_RETRIES + 1):
            try:
                async for page_total, raw_app in client.scroll_all_applications(
                    filter_fql=filter_fql,
                ):
                    self.check_cancelled()

                    if page_total > 0 and apps_total == 0:
                        apps_total = page_total
                        await self._update(total=apps_total)

                    app_doc = normalize_application(raw_app, sync_started_at)
                    buf.append(
                        UpdateOne(
                            {"_id": app_doc["_id"]},
                            {"$set": app_doc},
                            upsert=True,
                        )
                    )

                    if len(buf) >= BATCH:
                        await db[INSTALLED_APPS].bulk_write(buf, ordered=False)
                        apps_synced += len(buf)
                        buf.clear()
                        await self.save_checkpoint(
                            {
                                "synced": apps_synced,
                                "total": apps_total,
                                "mode": mode,
                                "run_id": self._run_id,
                            }
                        )
                        await self._update(
                            message=f"Syncing CrowdStrike apps ({apps_synced}"
                            f"{f' / {apps_total}' if apps_total else ''})…",
                            synced=apps_synced,
                        )
                break  # pagination completed

            except CSDiscoverNotLicensedError:
                logger.warning("CS Apps — Falcon Discover not licensed, skipping app sync")
                await self._update(
                    message="Falcon Discover not licensed — app sync skipped",
                )
                self._synced = 0
                self._total = 0
                return

            except CSRateLimitError:
                buf.clear()
                if attempt < MAX_RETRIES:
                    backoff = RATE_LIMIT_BACKOFF * (2**attempt)
                    logger.warning(
                        "CS Apps — rate limited, retry {}/{} in {}s",
                        attempt + 1,
                        MAX_RETRIES,
                        backoff,
                    )
                    await self._update(
                        message=f"Rate limited — retrying in {backoff}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})\u2026",
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise

            except CSApiError as exc:
                buf.clear()
                if attempt < MAX_RETRIES:
                    backoff = min(API_ERROR_BACKOFF * (2**attempt), 120)
                    logger.warning(
                        "CS Apps — API error ({}), retry {}/{} in {}s",
                        exc,
                        attempt + 1,
                        MAX_RETRIES,
                        backoff,
                    )
                    await self._update(
                        message=f"API error — retrying in {backoff}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})\u2026",
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise

        # Flush remaining buffer
        if buf:
            await db[INSTALLED_APPS].bulk_write(buf, ordered=False)
            apps_synced += len(buf)

        # Full sync: soft-delete stale records from this source
        if is_full:
            stale = await db[INSTALLED_APPS].update_many(
                {
                    "source": "crowdstrike",
                    "last_synced_at": {"$lt": sync_started_at},
                    "active": {"$ne": False},
                },
                {"$set": {"active": False}},
            )
            logger.info("CS Apps — soft-deleted {} stale records", stale.modified_count)
            reactivated = await db[INSTALLED_APPS].update_many(
                {
                    "source": "crowdstrike",
                    "last_synced_at": {"$gte": sync_started_at},
                    "active": False,
                },
                {"$set": {"active": True}},
            )
            if reactivated.modified_count:
                logger.info("CS Apps — reactivated {} records", reactivated.modified_count)

        # Persist timestamp
        await db[SYNC_META].update_one(
            {"_id": "crowdstrike"},
            {"$set": {"apps_synced_at": sync_started_at}},
            upsert=True,
        )

        # Denormalize app names onto CrowdStrike agents
        if apps_synced > 0 or is_full:
            await self._denorm_agent_apps(db)

        self._synced = apps_synced
        self._total = apps_total
        await self._update(
            message=f"Synced {apps_synced} CrowdStrike app records "
            f"({'full' if is_full else 'incremental'})",
            synced=apps_synced,
            total=apps_total,
        )
        logger.info("CS Apps phase — {} app records synced", apps_synced)

    @staticmethod
    async def _denorm_agent_apps(db: Any) -> None:  # noqa: ANN401
        """Rebuild ``installed_app_names`` on CrowdStrike agent documents."""
        try:
            from pymongo import UpdateOne

            from domains.sync.app_filters import active_match_stage

            match = active_match_stage()
            # Scope to CrowdStrike apps only
            pipeline = [
                {"$match": {"source": "crowdstrike", **match["$match"]}},
                {"$group": {"_id": "$agent_id", "names": {"$addToSet": "$normalized_name"}}},
            ]
            ops: list[Any] = []
            async for grp in db[INSTALLED_APPS].aggregate(pipeline, allowDiskUse=True):
                if not grp.get("_id"):
                    continue
                ops.append(
                    UpdateOne(
                        {"source": "crowdstrike", "source_id": grp["_id"]},
                        {"$set": {"installed_app_names": [n for n in grp["names"] if n]}},
                    )
                )
                if len(ops) >= 1000:
                    await db[AGENTS].bulk_write(ops, ordered=False)
                    ops.clear()
            if ops:
                await db[AGENTS].bulk_write(ops, ordered=False)
            logger.info("CS Apps — denormalization done")
        except Exception as exc:
            logger.warning("CS Apps — denormalization failed (non-fatal): {}", exc)
