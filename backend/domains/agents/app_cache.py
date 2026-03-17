"""Materialized app summary cache.

Pre-computes and stores a ``app_summaries`` collection containing one document
per distinct ``normalized_name`` with agent count, display name, publisher, and
resolved taxonomy category.  The list endpoint reads directly from this
lightweight collection instead of running a heavy aggregation on
``installed_apps`` on every request.

Rebuild is triggered:
- After each sync run completes (apps phase)
- After any taxonomy mutation (add/edit/delete entry, rename/delete category)

The rebuild is fast (~seconds even for large fleets) because it uses a single
MongoDB aggregation pipeline + a bulk Python taxonomy-match pass.
"""

from __future__ import annotations

import asyncio
import fnmatch
import re
import time

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_db
from domains.sources.collections import AGENTS, INSTALLED_APPS

COLLECTION = "app_summaries"

_GLOB_CHARS = frozenset("*?[")

# ── In-memory taxonomy matcher (shared with detail endpoint) ──────────────────


class TaxonomyMatcher:
    """Pre-compiled taxonomy pattern matcher.

    Separates exact-match patterns (O(1) dict lookup) from glob patterns
    (pre-compiled regex).  Built once per rebuild cycle.
    """

    __slots__ = ("_exact", "_globs", "_built_at")

    def __init__(self, entries: list[dict]) -> None:
        self._exact: dict[str, tuple[str, str]] = {}
        self._globs: list[tuple[re.Pattern[str], str, str]] = []
        self._built_at = time.monotonic()

        for entry in entries:
            cat = entry.get("category", "")
            cat_display = entry.get("category_display", cat)
            for p in entry.get("patterns", []):
                key = p.lower()
                if _GLOB_CHARS.intersection(key):
                    compiled = re.compile(fnmatch.translate(key))
                    self._globs.append((compiled, cat, cat_display))
                else:
                    self._exact[key] = (cat, cat_display)

    def match(self, normalized_name: str) -> tuple[str | None, str | None]:
        """Return (category, category_display) if any pattern matches."""
        hit = self._exact.get(normalized_name)
        if hit:
            return hit
        for compiled, cat, cat_display in self._globs:
            if compiled.match(normalized_name):
                return cat, cat_display
        return None, None


class DetailTaxonomyMatcher:
    """Pre-compiled matcher that returns full entry data for detail endpoint."""

    __slots__ = ("_exact", "_globs", "_built_at")

    def __init__(self, entries: list[dict]) -> None:
        self._exact: dict[str, dict] = {}
        self._globs: list[tuple[re.Pattern[str], dict]] = []
        self._built_at = time.monotonic()

        for entry in entries:
            for p in entry.get("patterns", []):
                key = p.lower()
                if _GLOB_CHARS.intersection(key):
                    compiled = re.compile(fnmatch.translate(key))
                    self._globs.append((compiled, entry))
                else:
                    self._exact[key] = entry

    def match(self, normalized_name: str) -> dict | None:
        """Return the matching taxonomy entry dict, or None."""
        hit = self._exact.get(normalized_name)
        if hit:
            return hit
        for compiled, entry in self._globs:
            if compiled.match(normalized_name):
                return entry
        return None


# ── Per-database cache (multi-tenant safe) ───────────────────────────────────

_taxonomy_matchers: dict[str, TaxonomyMatcher] = {}
_detail_matchers: dict[str, DetailTaxonomyMatcher] = {}
_rebuild_lock = asyncio.Lock()
_matcher_lock = asyncio.Lock()


async def _load_taxonomy_entries(db: AsyncIOMotorDatabase) -> list[dict]:  # type: ignore[type-arg]
    """Load taxonomy entries with patterns from MongoDB."""
    entries: list[dict] = []
    async for entry in db["taxonomy_entries"].find(
        {"patterns": {"$exists": True, "$ne": []}},
        {
            "_id": 0,
            "name": 1,
            "category": 1,
            "category_display": 1,
            "subcategory": 1,
            "publisher": 1,
            "patterns": 1,
            "is_universal": 1,
        },
    ):
        entries.append(entry)
    return entries


async def get_taxonomy_matcher(db: AsyncIOMotorDatabase) -> TaxonomyMatcher:  # type: ignore[type-arg]
    """Return the cached TaxonomyMatcher, loading on first call per database.

    Uses an asyncio lock to prevent concurrent requests from both triggering
    expensive regex compilation of the full taxonomy catalog.
    """
    db_name = db.name
    if db_name in _taxonomy_matchers:
        return _taxonomy_matchers[db_name]
    async with _matcher_lock:
        # Double-check after acquiring lock
        if db_name in _taxonomy_matchers:
            return _taxonomy_matchers[db_name]
        entries = await _load_taxonomy_entries(db)
        _taxonomy_matchers[db_name] = TaxonomyMatcher(entries)
        return _taxonomy_matchers[db_name]


async def get_detail_matcher(db: AsyncIOMotorDatabase) -> DetailTaxonomyMatcher:  # type: ignore[type-arg]
    """Return the cached DetailTaxonomyMatcher, loading on first call per database.

    Uses an asyncio lock to prevent duplicate loading.
    """
    db_name = db.name
    if db_name in _detail_matchers:
        return _detail_matchers[db_name]
    async with _matcher_lock:
        if db_name in _detail_matchers:
            return _detail_matchers[db_name]
        entries = await _load_taxonomy_entries(db)
        _detail_matchers[db_name] = DetailTaxonomyMatcher(entries)
        return _detail_matchers[db_name]


async def invalidate_taxonomy_cache() -> None:
    """Clear cached matchers for all databases. Call after any taxonomy mutation.

    Acquires ``_matcher_lock`` to ensure no concurrent ``get_taxonomy_matcher``
    or ``get_detail_matcher`` call observes a partially-rebuilt cache state
    (AUDIT domain-1).
    """
    async with _matcher_lock:
        _taxonomy_matchers.clear()
        _detail_matchers.clear()
    # Also clear the fingerprint matcher's compiled-regex cache since taxonomy
    # patterns may have changed.
    from domains.fingerprint.matcher import clear_pattern_cache

    clear_pattern_cache()
    logger.debug("Taxonomy matcher cache invalidated")


async def rebuild_app_summaries(db: AsyncIOMotorDatabase | None = None) -> int:  # type: ignore[type-arg]
    """Rebuild the ``app_summaries`` materialized collection.

    1. Aggregate ``installed_apps`` → one doc per normalized_name with
       version distribution, risk distribution, and agent IDs
    2. Look up agent group/site from ``agents`` for breakdown counts
    3. Match each against taxonomy patterns
    4. Bulk-write into ``app_summaries`` (drop + insert for atomicity)

    The detail stats (versions, risk, group/site breakdowns) are pre-computed
    here so the ``/stats/`` endpoint can serve them from a single
    ``find_one()`` instead of running expensive aggregation pipelines.

    Returns the number of distinct apps written.
    """
    async with _rebuild_lock:
        if db is None:
            db = get_db()

        t0 = time.monotonic()

        # Step 1: aggregate distinct apps with version + risk distributions.
        # Two-stage $group: first per (agent, app) to get per-agent version/risk,
        # then per app to count agents and collect distributions.
        from domains.sync.app_filters import active_match_stage

        pipeline: list[dict] = [
            active_match_stage(),
            # Stage 1: deduplicate (agent_id, normalized_name) pairs
            {
                "$group": {
                    "_id": {"n": "$normalized_name", "a": "$agent_id"},
                    "display_name": {"$first": "$name"},
                    "publisher": {"$first": "$publisher"},
                    "version": {"$first": "$version"},
                    "risk_level": {"$first": "$risk_level"},
                }
            },
            # Stage 2: count distinct agents, collect version/risk per app
            {
                "$group": {
                    "_id": "$_id.n",
                    "display_name": {"$first": "$display_name"},
                    "publisher": {"$first": "$publisher"},
                    "agent_count": {"$sum": 1},
                    "agent_ids": {"$push": "$_id.a"},
                    "agent_versions": {"$push": "$version"},
                    "agent_risks": {"$push": "$risk_level"},
                }
            },
        ]
        rows = [doc async for doc in db[INSTALLED_APPS].aggregate(pipeline, allowDiskUse=True)]

        if not rows:
            logger.info("App summaries rebuild: no apps found")
            return 0

        # Step 2: build agent_id → (group, site) lookup for breakdown
        # Pre-load all agents referenced in results (single query).
        all_agent_ids: set[str] = set()
        for r in rows:
            all_agent_ids.update(r.get("agent_ids", []))

        agent_lookup: dict[str, dict] = {}
        if all_agent_ids:
            async for agent in db[AGENTS].find(
                {"source_id": {"$in": list(all_agent_ids)}},
                {
                    "_id": 0,
                    "source_id": 1,
                    "group_id": 1,
                    "group_name": 1,
                    "site_id": 1,
                    "site_name": 1,
                },
            ):
                agent_lookup[agent["source_id"]] = agent

        # Step 3: load taxonomy matcher
        entries = await _load_taxonomy_entries(db)
        matcher = TaxonomyMatcher(entries)

        # Refresh the per-database caches
        db_name = db.name
        _taxonomy_matchers[db_name] = matcher
        _detail_matchers.pop(db_name, None)  # force re-load on next detail request

        # Step 4: build summary docs with pre-computed detail stats
        docs = []
        for r in rows:
            nname = r["_id"]
            cat, cat_display = matcher.match(nname)

            # Version distribution (top 50)
            version_counts: dict[str, int] = {}
            for v in r.get("agent_versions", []):
                key = v or "unknown"
                version_counts[key] = version_counts.get(key, 0) + 1
            versions_sorted = sorted(version_counts.items(), key=lambda x: x[1], reverse=True)[:50]

            # Risk distribution
            risk_counts: dict[str, int] = {}
            for rl in r.get("agent_risks", []):
                key = rl or "unknown"
                risk_counts[key] = risk_counts.get(key, 0) + 1
            top_risk = max(risk_counts, key=risk_counts.get, default=None) if risk_counts else None  # type: ignore[arg-type]

            # Group/site breakdowns
            group_counts: dict[str, dict] = {}  # group_id → {name, count}
            site_counts: dict[str, dict] = {}  # site_id → {name, count}
            for aid in r.get("agent_ids", []):
                ag = agent_lookup.get(aid)
                if not ag:
                    continue
                gid = ag.get("group_id")
                if gid:
                    if gid not in group_counts:
                        group_counts[gid] = {
                            "name": ag.get("group_name") or gid,
                            "count": 0,
                        }
                    group_counts[gid]["count"] += 1
                sid = ag.get("site_id")
                if sid:
                    if sid not in site_counts:
                        site_counts[sid] = {
                            "name": ag.get("site_name") or sid,
                            "count": 0,
                        }
                    site_counts[sid]["count"] += 1
            groups_sorted = sorted(group_counts.values(), key=lambda x: x["count"], reverse=True)
            sites_sorted = sorted(site_counts.values(), key=lambda x: x["count"], reverse=True)

            docs.append(
                {
                    "normalized_name": nname,
                    "display_name": r.get("display_name") or nname,
                    "publisher": r.get("publisher"),
                    "agent_count": r["agent_count"],
                    "category": cat,
                    "category_display": cat_display,
                    # Pre-computed detail stats
                    "risk_level": top_risk,
                    "versions": [{"version": v, "count": c} for v, c in versions_sorted],
                    "risk_distribution": risk_counts,
                    "group_breakdown": [
                        {"name": g["name"], "count": g["count"]} for g in groups_sorted
                    ],
                    "site_breakdown": [
                        {"name": s["name"], "count": s["count"]} for s in sites_sorted
                    ],
                    "group_count": len(groups_sorted),
                    "site_count": len(sites_sorted),
                }
            )

        # Step 5: atomic swap — write to temp, then rename
        tmp = f"{COLLECTION}_tmp"
        await db[tmp].drop()
        await db[tmp].insert_many(docs, ordered=False)

        # Create indexes on temp before swap
        await db[tmp].create_index("normalized_name", unique=True, background=True)
        await db[tmp].create_index("agent_count", background=True)
        await db[tmp].create_index("category", background=True)

        # Rename replaces the target atomically
        await db[tmp].rename(COLLECTION, dropTarget=True)

        elapsed = time.monotonic() - t0
        logger.info("App summaries rebuilt: {} apps in {:.2f}s", len(docs), elapsed)
        return len(docs)


async def ensure_app_summaries_exist(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """If ``app_summaries`` is empty, trigger a rebuild.

    Called at startup so the first request doesn't hit the slow aggregation.
    """
    count = await db[COLLECTION].estimated_document_count()
    if count == 0:
        # Check if there are any apps to summarize
        app_count = await db[INSTALLED_APPS].estimated_document_count()
        if app_count > 0:
            logger.info("App summaries collection empty, triggering rebuild")
            await rebuild_app_summaries(db)
