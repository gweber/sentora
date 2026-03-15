"""Background scheduler for automated MongoDB backups.

Runs as an asyncio task alongside the main application. Uses ``croniter``
to parse the configured cron expression and sleeps until the next run.
Re-reads ``backup_enabled`` from settings each cycle so it can be toggled
without a restart.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from config import get_settings
from database import get_db
from utils.backup import BackupManager
from utils.dt import utc_now


async def backup_scheduler() -> None:
    """Long-running background task that creates backups on a cron schedule.

    Reads ``backup_schedule_cron`` from settings, calculates the next run
    time, and sleeps until then. After each backup, runs retention enforcement
    to delete old backups exceeding the configured count.

    Handles ``CancelledError`` for graceful shutdown.
    """
    try:
        from croniter import croniter  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "croniter is not installed but BACKUP_ENABLED=True — backup scheduler "
            "cannot start. Install with: pip install croniter"
        )
        raise RuntimeError(
            "BACKUP_ENABLED is True but croniter is not installed. "
            "Either install croniter or set BACKUP_ENABLED=False."
        ) from None

    # Brief delay to let startup complete
    await asyncio.sleep(10)
    logger.info("Backup scheduler started")

    try:
        while True:
            settings = get_settings()

            if not settings.backup_enabled:
                # Backup disabled — re-check every 60 seconds
                await asyncio.sleep(60)
                continue

            cron = croniter(settings.backup_schedule_cron, utc_now())
            next_run = cron.get_next(float)
            wait_seconds = max(0, next_run - utc_now().timestamp())

            logger.info(
                "Backup scheduler — next run in {:.0f}s (cron: {})",
                wait_seconds,
                settings.backup_schedule_cron,
            )

            # Sleep in 30s chunks so we can pick up config changes
            remaining = wait_seconds
            while remaining > 0:
                chunk = min(30, remaining)
                await asyncio.sleep(chunk)
                remaining -= chunk
                # Re-check if backups were disabled
                if not get_settings().backup_enabled:
                    break

            if not get_settings().backup_enabled:
                continue

            # Run the backup
            try:
                db = get_db()
                record = await BackupManager.create_backup(db, triggered_by="scheduler")
                logger.info(
                    "Scheduled backup {} — status: {}",
                    record.id,
                    record.status,
                )
                # Enforce retention
                deleted = await BackupManager.enforce_retention(db)
                if deleted:
                    logger.info("Retention enforcement removed {} backup(s)", deleted)
            except Exception as exc:
                logger.error("Scheduled backup failed: {}", exc)

    except asyncio.CancelledError:
        logger.info("Backup scheduler stopped")
        raise
