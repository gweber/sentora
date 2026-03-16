"""Classification engine.

This module implements the core classification pipeline:

1. ``classify_single_agent`` — pure function that scores one agent against all
   loaded fingerprints and returns a ``ClassificationResult``.
2. ``ClassificationManager`` — async manager that runs the full pipeline
   (load agents → classify → bulk-upsert) in a background task, with a lock
   to prevent concurrent runs.
3. ``classification_manager`` — module-level singleton for use by the service.

Scoring thresholds (ADR-0012)
------------------------------
- ``best.score >= 0.7`` AND ``gap >= 0.15`` → clear winner → correct / misclassified
- ``best.score >= 0.4``                      → some match  → ambiguous
- ``best.score < 0.4``                        → nothing fits → unclassifiable
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.classification.entities import (
    ClassificationResult,
    ClassificationRun,
    GroupMatchScore,
)
from domains.classification.repository import (
    bulk_upsert_results,
    save_run,
    update_run,
)
from domains.config.entities import AppConfig
from domains.fingerprint.entities import Fingerprint
from domains.fingerprint.matcher import matches_pattern
from domains.fingerprint.repository import list_all as list_all_fingerprints
from utils.dt import utc_now

# Fallback verdict thresholds (used when app_config is unavailable)
_SCORE_CLEAR: float = 0.7
_SCORE_PARTIAL: float = 0.4
_GAP_CLEAR: float = 0.15

# Processing batch size for agent pagination
_BATCH_SIZE: int = 500

# Maximum top match scores to retain per agent
_TOP_N_SCORES: int = 5


# ── Single-agent classification ───────────────────────────────────────────────


async def classify_single_agent(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    agent_doc: dict[str, Any],
    fingerprints: list[Fingerprint],
    cfg: AppConfig | None = None,
) -> ClassificationResult:
    """Classify a single agent against all fingerprints.

    Steps
    -----
    1. Read the agent's ``installed_app_names`` field (denormalized by the sync
       pipeline — a compact list of distinct normalised app names).  Falls back
       to a live ``s1_installed_apps`` query for agents synced before
       denormalization was introduced.
    2. For each fingerprint, compute a weighted match score across all markers.
    3. Sort scores descending and keep the top 5.
    4. Apply verdict logic (correct / misclassified / ambiguous / unclassifiable).

    Args:
        db: Motor database handle (fallback only — not used when the agent doc
            already carries ``installed_app_names``).
        agent_doc: Raw ``s1_agents`` document dict.
        fingerprints: All fingerprints pre-loaded by the caller.
        cfg: Optional persisted app config for threshold overrides.

    Returns:
        A fully populated ``ClassificationResult`` entity.
    """
    agent_id: str = agent_doc.get("s1_agent_id", "")
    hostname: str = agent_doc.get("hostname", "")
    current_group_id: str = agent_doc.get("group_id", "")
    current_group_name: str = agent_doc.get("group_name", "")

    # Placeholder run_id — will be set by the caller (classification manager)
    run_id: str = agent_doc.get("_run_id", "")

    # ── Step 1: Resolve installed app names ───────────────────────────────────
    # Fast path: denormalized array written by sync (introduced with the
    # 9M-app optimisation).  Fallback: live aggregation query for agents that
    # pre-date denormalization (e.g. test fixtures or partial syncs).
    installed_apps_raw: list[str] = agent_doc.get("installed_app_names") or []
    if not installed_apps_raw:
        try:
            from domains.sync.app_filters import active_match_stage

            pipeline: list[dict[str, Any]] = [
                active_match_stage(agent_id=agent_id),
                {"$group": {"_id": "$normalized_name"}},
            ]
            app_docs = await db["s1_installed_apps"].aggregate(pipeline).to_list(length=None)
            installed_apps_raw = [d["_id"] for d in app_docs if d.get("_id")]
        except Exception as exc:
            logger.warning("Failed to load apps for agent {}: {}", agent_id, exc)

    installed_apps: list[str] = installed_apps_raw
    # Lowercase frozenset for O(1) exact-match lookup in the inner scoring loop
    installed_apps_lower: frozenset[str] = frozenset(a.lower() for a in installed_apps)

    # ── Step 2: Score each fingerprint ───────────────────────────────────────
    match_scores: list[GroupMatchScore] = []

    for fp in fingerprints:
        if not fp.markers:
            score_val = 0.0
            matched: list[str] = []
            missing: list[str] = []  # No markers defined — nothing to match against
        else:
            total_weight: float = sum(m.weight for m in fp.markers)
            if total_weight == 0.0:
                score_val = 0.0
                matched = []
                missing = [m.display_name for m in fp.markers]
            else:
                matched = []
                missing = []
                matched_weight: float = 0.0

                for marker in fp.markers:
                    # Fast path: exact patterns (no wildcards) → frozenset O(1)
                    if "*" not in marker.pattern and "?" not in marker.pattern:
                        marker_matched = marker.pattern.lower() in installed_apps_lower
                    else:
                        marker_matched = any(
                            matches_pattern(marker.pattern, app_name) for app_name in installed_apps
                        )
                    if marker_matched:
                        matched.append(marker.display_name)
                        matched_weight += marker.weight
                    else:
                        missing.append(marker.display_name)

                score_val = matched_weight / total_weight

        match_scores.append(
            GroupMatchScore(
                group_id=fp.group_id,
                group_name=fp.group_name,
                score=round(score_val, 6),
                matched_markers=matched,
                missing_markers=missing,
            )
        )

    # ── Step 3: Sort and trim to top 5 ───────────────────────────────────────
    match_scores.sort(key=lambda s: s.score, reverse=True)
    top_scores = match_scores[:_TOP_N_SCORES]

    # ── Resolve thresholds from persisted config (fallback to module defaults) ─
    score_clear = cfg.classification_threshold if cfg else _SCORE_CLEAR
    score_partial = cfg.partial_threshold if cfg else _SCORE_PARTIAL
    gap_clear = cfg.ambiguity_gap if cfg else _GAP_CLEAR

    # ── Step 4: Verdict logic ─────────────────────────────────────────────────
    anomaly_reasons: list[str] = []
    classification: str
    suggested_group_id: str | None = None
    suggested_group_name: str | None = None

    if not fingerprints or not top_scores or top_scores[0].score < score_partial:
        classification = "unclassifiable"
        if not fingerprints:
            anomaly_reasons.append("No fingerprints have been defined yet.")
        else:
            anomaly_reasons.append(
                f"Best match score {top_scores[0].score:.2f} is below the minimum "
                f"threshold of {score_partial:.2f}."
                if top_scores
                else "No match scores could be computed."
            )
    else:
        best = top_scores[0]
        gap: float = best.score - top_scores[1].score if len(top_scores) > 1 else best.score

        if best.score >= score_clear and gap >= gap_clear:
            # Clear winner
            if best.group_id == current_group_id:
                classification = "correct"
            else:
                classification = "misclassified"
                suggested_group_id = best.group_id
                suggested_group_name = best.group_name
                anomaly_reasons.append(
                    f"Agent is in group '{current_group_name}' but best fingerprint "
                    f"match is '{best.group_name}' (score {best.score:.2f})."
                )
        else:
            # Score is in the partial–clear range or gap is too small
            classification = "ambiguous"
            if best.score < score_clear:
                anomaly_reasons.append(
                    f"Best match score {best.score:.2f} is below the confident "
                    f"threshold of {score_clear:.2f}."
                )
            if gap < gap_clear and len(top_scores) > 1:
                anomaly_reasons.append(
                    f"Gap between top two scores is {gap:.2f}, below the minimum "
                    f"gap of {gap_clear:.2f} required for a confident verdict."
                )

    return ClassificationResult(
        run_id=run_id,
        agent_id=agent_id,
        hostname=hostname,
        current_group_id=current_group_id,
        current_group_name=current_group_name,
        match_scores=top_scores,
        classification=classification,  # type: ignore[arg-type]
        suggested_group_id=suggested_group_id,
        suggested_group_name=suggested_group_name,
        anomaly_reasons=anomaly_reasons,
        computed_at=utc_now(),
        acknowledged=False,
    )


# ── Classification manager ────────────────────────────────────────────────────


class ClassificationManager:
    """Manages the lifecycle of classification pipeline runs.

    Ensures only one run executes at a time via an ``asyncio.Lock``. Runs are
    executed as a background task so the HTTP trigger endpoint returns
    immediately.

    Attributes:
        _lock: Lock preventing concurrent runs.
        _current_run_id: ID of the currently active run (or None).
    """

    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()
        self._current_run_id: str | None = None
        self._dist_lock: object | None = None  # DistributedLock instance when held

    async def trigger(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        trigger: str = "manual",
    ) -> ClassificationRun | None:
        """Trigger a new classification run as a background task.

        Returns ``None`` (and logs a warning) if a run is already in progress.
        The caller should translate a ``None`` return into a 409 response.

        Args:
            db: Motor database handle.
            trigger: Label for how the run was initiated.

        Returns:
            The new ``ClassificationRun`` entity if started, otherwise None.
        """
        # Distributed lock — prevents concurrent classification across workers
        if not await self._acquire_dist_lock(db):
            logger.warning("Classification distributed lock held by another worker")
            return None

        run = ClassificationRun(trigger=trigger, status="running")
        self._current_run_id = run.id

        # Persist the run record immediately so the caller can reference it
        await save_run(db, run)
        logger.info("Classification run {} triggered (trigger={})", run.id, trigger)

        # Fire-and-forget background task
        asyncio.create_task(self._run_classification(db, run.id))

        return run

    async def _run_classification(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        run_id: str,
    ) -> None:
        """Main classification pipeline executed as a background task.

        Processes all agents in ``s1_agents`` in batches of ``_BATCH_SIZE``.
        Results are bulk-upserted after each batch. Updates the run record
        on completion or failure.

        Args:
            db: Motor database handle.
            run_id: ID of the ClassificationRun document to update.
        """
        async with self._lock:
            agents_classified = 0
            errors = 0
            error_log: list[str] = []

            try:
                # ── Load persisted config (thresholds) ─────────────────────
                from domains.config import repository as config_repo

                try:
                    cfg = await config_repo.get(db)
                except Exception:
                    cfg = None

                # ── Load all fingerprints once ──────────────────────────────
                fingerprints: list[Fingerprint] = []
                try:
                    fingerprints = await list_all_fingerprints(db, skip=0, limit=0)
                    logger.info(
                        "Classification run {}: loaded {} fingerprints.",
                        run_id,
                        len(fingerprints),
                    )
                except Exception as exc:
                    logger.warning(
                        "Classification run {}: could not load fingerprints: {}",
                        run_id,
                        exc,
                    )

                # ── Count total agents ──────────────────────────────────────
                try:
                    total_agents: int = await db["s1_agents"].count_documents({})
                except Exception:
                    total_agents = 0

                if total_agents == 0:
                    logger.info(
                        "Classification run {}: no agents found in s1_agents, run complete.",
                        run_id,
                    )
                    await update_run(
                        db,
                        run_id,
                        {
                            "status": "completed",
                            "completed_at": utc_now(),
                            "agents_classified": 0,
                            "errors": 0,
                            "error_log": [],
                        },
                    )
                    return

                # ── Process agents in batches ───────────────────────────────
                # App names are read from agent_doc["installed_app_names"] —
                # a denormalized array written by sync. No cross-collection
                # lookup needed during classification.
                skip = 0
                processed = 0

                while True:
                    try:
                        batch_docs: list[dict[str, Any]] = (
                            await db["s1_agents"]
                            .find({}, skip=skip, limit=_BATCH_SIZE)
                            .to_list(length=_BATCH_SIZE)
                        )
                    except Exception as exc:
                        msg = f"Failed to fetch agent batch (skip={skip}): {exc}"
                        logger.error("Classification run {}: {}", run_id, msg)
                        error_log.append(msg)
                        errors += 1
                        break

                    if not batch_docs:
                        break

                    batch_results: list[ClassificationResult] = []

                    for agent_doc in batch_docs:
                        processed += 1
                        # Inject the run_id so classify_single_agent can embed it
                        agent_doc["_run_id"] = run_id

                        try:
                            result = await classify_single_agent(db, agent_doc, fingerprints, cfg)
                            batch_results.append(result)
                            agents_classified += 1
                        except Exception as exc:
                            agent_id = agent_doc.get("s1_agent_id", "unknown")
                            msg = f"Error classifying agent {agent_id}: {exc}"
                            logger.error("Classification run {}: {}", run_id, msg)
                            error_log.append(msg)
                            errors += 1

                    logger.info(
                        "Classification run {}: batch done — {}/{} agents processed",
                        run_id,
                        processed,
                        total_agents,
                    )

                    # Bulk-upsert the batch
                    if batch_results:
                        try:
                            written = await bulk_upsert_results(db, batch_results)
                            # bulk_upsert_results handles BulkWriteError internally
                            # and returns the count of successful ops. Reconcile
                            # agents_classified to reflect actual writes.
                            failed = len(batch_results) - written
                            if failed > 0:
                                msg = (
                                    f"Batch at skip={skip}: {failed}/{len(batch_results)} "
                                    f"documents failed to upsert — {written} written successfully."
                                )
                                logger.warning("Classification run {}: {}", run_id, msg)
                                error_log.append(msg)
                                errors += failed
                                agents_classified -= failed
                        except Exception as exc:
                            # Unexpected error (e.g. network failure) — entire batch lost.
                            msg = f"Bulk upsert failed for batch starting at skip={skip}: {exc}"
                            logger.error("Classification run {}: {}", run_id, msg)
                            error_log.append(msg)
                            errors += len(batch_results)
                            agents_classified -= len(batch_results)

                    skip += _BATCH_SIZE

                    if len(batch_docs) < _BATCH_SIZE:
                        # Last batch
                        break

                # ── Mark run completed ──────────────────────────────────────
                logger.info(
                    "Classification run {} complete: {} classified, {} errors.",
                    run_id,
                    agents_classified,
                    errors,
                )
                await update_run(
                    db,
                    run_id,
                    {
                        "status": "completed",
                        "completed_at": utc_now(),
                        "agents_classified": agents_classified,
                        "errors": errors,
                        "error_log": error_log,
                    },
                )

            except Exception as exc:
                logger.exception(
                    "Classification run {} failed with unhandled exception: {}", run_id, exc
                )
                await update_run(
                    db,
                    run_id,
                    {
                        "status": "failed",
                        "completed_at": utc_now(),
                        "agents_classified": agents_classified,
                        "errors": errors + 1,
                        "error_log": error_log + [str(exc)],
                    },
                )
            finally:
                self._current_run_id = None
                await self._release_dist_lock()

    async def _acquire_dist_lock(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> bool:
        """Try to acquire the distributed classification lock (if enabled).

        Returns True if the lock was acquired (or distributed locks are disabled).
        Returns False if another worker holds the lock.
        """
        from config import get_settings

        if not get_settings().enable_distributed_locks:
            return True

        try:
            from utils.distributed_lock import DistributedLock

            dist_lock = DistributedLock(db, "classification_pipeline", ttl_seconds=3600)
            if not await dist_lock.acquire():
                return False
            # Start heartbeat to keep the lock alive during long classification runs
            dist_lock._heartbeat_task = asyncio.create_task(dist_lock._heartbeat())
            self._dist_lock = dist_lock
            return True
        except Exception as exc:
            logger.error("Distributed lock acquisition failed: {}", exc)
            return False

    async def _release_dist_lock(self) -> None:
        """Release the distributed classification lock if one is held."""
        if self._dist_lock is not None:
            try:
                from utils.distributed_lock import DistributedLock

                if isinstance(self._dist_lock, DistributedLock):
                    # Cancel heartbeat task before releasing
                    ht = getattr(self._dist_lock, "_heartbeat_task", None)
                    if ht and not ht.done():
                        ht.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await ht
                    await self._dist_lock.release()
            except Exception as exc:
                logger.warning("Failed to release distributed classification lock: {}", exc)
            finally:
                self._dist_lock = None


# Module-level singleton
classification_manager = ClassificationManager()
