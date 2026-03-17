"""Apps phase runner — fetches installed applications with checkpoint resume and retry."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from domains.sources.collections import AGENTS, INSTALLED_APPS, SYNC_META

from ..phase_runner import PhaseRunner


class AppsPhaseRunner(PhaseRunner):
    phase_name = "apps"

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
            await self._sync_apps(s1_client, mode, is_resume, checkpoint)
        finally:
            if own_client:
                await s1_client.close()

    async def _sync_apps(
        self,
        client: Any,  # noqa: ANN401
        mode: str,
        is_resume: bool,
        checkpoint: dict[str, Any] | None,
    ) -> None:
        from pymongo import UpdateOne

        from utils.dt import utc_now

        from ..normalizer import normalize_app
        from ..s1_client import S1ApiError, S1RateLimitError, make_app_cursor

        db = await self._get_db()
        is_full = mode == "full"
        sync_started_at = utc_now().isoformat()

        page_size = await self._load_page_size(db, "page_size_apps")

        # Determine mode automatically
        if mode == "auto":
            meta = await db[SYNC_META].find_one({"_id": "global"})
            max_app_id = meta.get("max_app_id") if meta else None
            is_full = max_app_id is None
            mode = "full" if is_full else "incremental"

        # Check checkpoint mode match
        if is_resume and checkpoint:
            cp_mode = checkpoint.get("mode")
            if cp_mode and cp_mode != mode:
                logger.warning("Apps — discarding checkpoint (mode {} != {})", cp_mode, mode)
                await self.clear_checkpoint()
                checkpoint = None
                is_resume = False

        apps_synced = 0
        apps_total = 0

        # Determine resume cursor
        resume_cursor: str | None = None
        skip_phase = False

        if checkpoint and checkpoint.get("last_id"):
            resume_cursor = make_app_cursor(int(checkpoint["last_id"]))
            apps_synced = checkpoint.get("synced", 0)
            apps_total = checkpoint.get("total", 0)
            logger.info(
                "Apps — resuming from id {} ({} already synced)", checkpoint["last_id"], apps_synced
            )
        elif not is_full:
            meta_doc = await db[SYNC_META].find_one({"_id": "global"})
            max_app_id = meta_doc.get("max_app_id") if meta_doc else None
            if max_app_id:
                resume_cursor = make_app_cursor(int(max_app_id))
                logger.info("Apps — incremental: starting after max_app_id={}", max_app_id)
            else:
                logger.info("Apps — incremental: no max_app_id, skipping")
                skip_phase = True

        if skip_phase:
            self._synced = 0
            self._total = 0
            return

        resume_msg = (
            f"Resuming apps ({apps_synced} already synced)…"
            if checkpoint and checkpoint.get("last_id")
            else ("Fetching new apps…" if not is_full else "Fetching installed applications…")
        )
        await self._update(message=resume_msg, synced=apps_synced, total=apps_total)

        buf: list = []
        BATCH = page_size
        max_app_id_seen: int = 0

        MAX_RETRIES = 3
        RATE_LIMIT_BACKOFF = 60
        API_ERROR_BACKOFF = 30

        for attempt in range(MAX_RETRIES + 1):
            try:
                async for page_total, page_cursor, raw_app in client.get_installed_applications(
                    page_size=page_size,
                    resume_cursor=resume_cursor,
                    installed_since=None,
                ):
                    self.check_cancelled()

                    if page_total is not None:
                        apps_total = page_total
                        await self._update(total=apps_total)

                    app_id = raw_app.get("id")
                    if not app_id:
                        continue
                    try:
                        if int(app_id) > max_app_id_seen:
                            max_app_id_seen = int(app_id)
                    except (ValueError, TypeError):
                        pass

                    buf.append(
                        UpdateOne(
                            {"_id": app_id},
                            {"$set": normalize_app(raw_app, sync_started_at)},
                            upsert=True,
                        )
                    )

                    if len(buf) >= BATCH:
                        await db[INSTALLED_APPS].bulk_write(buf, ordered=False)
                        apps_synced += len(buf)
                        buf.clear()
                        resume_cursor = (
                            make_app_cursor(max_app_id_seen) if max_app_id_seen else page_cursor
                        )
                        await self.save_checkpoint(
                            {
                                "last_id": str(max_app_id_seen),
                                "synced": apps_synced,
                                "total": apps_total,
                                "mode": mode,
                                "run_id": self._run_id,
                            }
                        )
                        await self._update(
                            message=f"Syncing apps ({apps_synced} / {apps_total})…",
                            synced=apps_synced,
                        )
                break  # pagination completed

            except S1RateLimitError:
                buf.clear()  # discard unflushed items to avoid duplicates on retry
                if attempt < MAX_RETRIES:
                    backoff = RATE_LIMIT_BACKOFF * (2**attempt)
                    logger.warning(
                        "Apps — rate limited, retry {}/{} in {}s", attempt + 1, MAX_RETRIES, backoff
                    )
                    await self._update(
                        message=(
                            f"Rate limited — retrying in {backoff}s "
                            f"(attempt {attempt + 1}/{MAX_RETRIES})\u2026"
                        ),
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise

            except S1ApiError as exc:
                buf.clear()  # discard unflushed items to avoid duplicates on retry
                if attempt < MAX_RETRIES:
                    backoff = min(API_ERROR_BACKOFF * (2**attempt), 120)
                    logger.warning(
                        "Apps — API error ({}), retry {}/{} in {}s",
                        exc,
                        attempt + 1,
                        MAX_RETRIES,
                        backoff,
                    )
                    await self._update(
                        message=(
                            f"API error — retrying in {backoff}s "
                            f"(attempt {attempt + 1}/{MAX_RETRIES})\u2026"
                        ),
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise

        # Flush remaining buffer
        if buf:
            await db[INSTALLED_APPS].bulk_write(buf, ordered=False)
            apps_synced += len(buf)

        # Persist high-water mark and timestamp
        meta_update: dict[str, str] = {"apps_synced_at": sync_started_at}
        if max_app_id_seen:
            meta_update["max_app_id"] = str(max_app_id_seen)
        await db[SYNC_META].update_one(
            {"_id": "global"},
            {"$set": meta_update},
            upsert=True,
        )
        if max_app_id_seen:
            logger.info("Apps — saved max_app_id={}", max_app_id_seen)

        # Full sync: soft-delete stale, reactivate returning
        if is_full:
            stale = await db[INSTALLED_APPS].update_many(
                {"last_synced_at": {"$lt": sync_started_at}, "active": {"$ne": False}},
                {"$set": {"active": False}},
            )
            logger.info("Apps — soft-deleted {} stale records", stale.modified_count)
            reactivated = await db[INSTALLED_APPS].update_many(
                {"last_synced_at": {"$gte": sync_started_at}, "active": False},
                {"$set": {"active": True}},
            )
            if reactivated.modified_count:
                logger.info("Apps — reactivated {} records", reactivated.modified_count)

        # Denormalize app names onto agents (skip if nothing changed)
        if apps_synced > 0 or is_full:
            await self._denorm_agent_apps(db)

        self._synced = apps_synced
        self._total = apps_total
        await self._update(
            message=f"Synced {apps_synced} app records ({'full' if is_full else 'incremental'})",
            synced=apps_synced,
            total=apps_total,
        )
        logger.info("Apps phase — {} app records synced", apps_synced)

    @staticmethod
    async def _denorm_agent_apps(db: Any, agent_ids: list[str] | None = None) -> None:  # noqa: ANN401
        """Rebuild ``installed_app_names`` on agent documents."""
        try:
            from pymongo import UpdateOne

            from ..app_filters import active_match_stage

            match = (
                active_match_stage(agent_id={"$in": agent_ids})
                if agent_ids is not None
                else active_match_stage()
            )
            pipeline = [
                match,
                {"$group": {"_id": "$agent_id", "names": {"$addToSet": "$normalized_name"}}},
            ]
            ops: list = []
            async for grp in db[INSTALLED_APPS].aggregate(pipeline, allowDiskUse=True):
                if not grp.get("_id"):
                    continue
                ops.append(
                    UpdateOne(
                        {"source_id": grp["_id"]},
                        {"$set": {"installed_app_names": [n for n in grp["names"] if n]}},
                    )
                )
                if len(ops) >= 1000:
                    await db[AGENTS].bulk_write(ops, ordered=False)
                    ops.clear()
            if ops:
                await db[AGENTS].bulk_write(ops, ordered=False)
            logger.info(
                "Apps — denorm done for {} agents",
                len(agent_ids) if agent_ids is not None else "all",
            )
        except Exception as exc:
            logger.warning("Apps — denormalization failed (non-fatal): {}", exc)
