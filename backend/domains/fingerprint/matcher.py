"""Fingerprint matcher — TF-IDF suggestion computation and scoring logic.

This module implements two distinct capabilities:

1. **Glob scoring** (ADR-0004 / ADR-0012): Convert glob patterns to compiled
   regexes and evaluate a weighted score for a given app name against a
   fingerprint's marker set.

2. **TF-IDF suggestions** (ADR-0003): Given a group ID, query
   ``s1_installed_apps`` and ``s1_agents`` to identify which app names best
   distinguish that group from the rest of the agent population, then return
   the top-ranked suggestions as ``FingerprintSuggestion`` entities.

Scoring thresholds (ADR-0012)
------------------------------
- ``matched``   : score ≥ 0.7
- ``partial``   : 0.4 ≤ score < 0.7
- ``unmatched`` : score < 0.4
"""

from __future__ import annotations

import functools
import re
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.fingerprint.entities import FingerprintSuggestion
from utils.dt import utc_now

# Maximum number of suggestions stored per compute call
_TOP_N: int = 200


@functools.lru_cache(maxsize=4096)
def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob pattern to a compiled case-insensitive regex.

    Supported wildcards:
    - ``*`` — matches any sequence of characters (including empty).
    - ``?`` — matches exactly one character.

    All other regex metacharacters in the pattern are escaped.

    Results are cached (up to 4096 patterns). Call ``clear_pattern_cache()``
    after bulk operations to free memory.

    Args:
        pattern: Glob pattern string (e.g. ``"wincc*"`` or ``"agent?"``).

    Returns:
        Compiled ``re.Pattern`` for case-insensitive matching.

    Examples:
        >>> glob_to_regex("wincc*").match("wincc runtime")
        <re.Match ...>
        >>> glob_to_regex("agent?").match("agents")
        <re.Match ...>
    """
    # Split on '*' first, escape each segment, then rejoin with '.*'.
    # Within each star segment, split on '?' and rejoin with '.' so that
    # '?' matches exactly one character.
    star_parts = pattern.split("*")
    segments: list[str] = []
    for part in star_parts:
        question_parts = part.split("?")
        escaped_q_parts = [re.escape(qp) for qp in question_parts]
        segments.append(".".join(escaped_q_parts))

    regex_str = ".*".join(segments)
    return re.compile(f"^{regex_str}$", re.IGNORECASE)


def clear_pattern_cache() -> None:
    """Clear the compiled glob-to-regex cache to free memory.

    Call this after bulk operations like classification runs or fingerprint
    rebuilds to prevent unbounded memory growth.
    """
    glob_to_regex.cache_clear()


def matches_pattern(pattern: str, text: str) -> bool:
    """Return True if ``text`` matches the glob ``pattern`` (case-insensitive).

    Uses an exact-match fast path for patterns with no wildcards to avoid
    regex compilation overhead.

    Args:
        pattern: Glob pattern with optional ``*`` and ``?`` wildcards.
        text: The string to test (typically a normalised app name).

    Returns:
        True if the full string matches the pattern, False otherwise.
    """
    if "*" not in pattern and "?" not in pattern:
        return pattern.lower() == text.lower()
    return bool(glob_to_regex(pattern).match(text))


async def compute_suggestions(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    group_id: str,
) -> list[FingerprintSuggestion]:
    """Compute TF-IDF suggestions for a group.

    Steps
    -----
    1. Fetch agent IDs belonging to ``group_id`` from ``s1_agents``.
    2. For those agents, count app occurrences per ``normalized_name`` in
       ``s1_installed_apps``.
    3. Count per-app totals across *all* agents in ``s1_installed_apps`` to
       compute document frequency.
    4. Compute TF-IDF:
       - ``tf`` = in_group_count / group_agent_count
       - ``idf`` = log((N + 1) / (df + 1))   where N = total distinct agents
       - ``score`` = tf * idf
    5. Filter out apps already present as a pattern in any of the group's
       fingerprint markers.
    6. Filter out apps with ``score <= 0``.
    7. Return top 200 suggestions sorted by score descending.

    Handles the case where ``s1_agents`` or ``s1_installed_apps`` do not yet
    exist (returns an empty list).

    Args:
        db: Motor database handle.
        group_id: SentinelOne group ID to compute suggestions for.

    Returns:
        List of up to 20 ``FingerprintSuggestion`` entities, or empty list if
        there is insufficient data.
    """
    try:
        # ── Step 1: Get agent IDs in the target group ──────────────────────
        agent_docs: list[dict[str, Any]] = (
            await db["s1_agents"]
            .find({"group_id": group_id}, {"s1_agent_id": 1})
            .to_list(length=None)
        )

        if not agent_docs:
            return []

        group_agent_ids: list[str] = [d["s1_agent_id"] for d in agent_docs if "s1_agent_id" in d]
        group_agent_count: int = len(group_agent_ids)

        if group_agent_count == 0:
            return []

        # ── Step 2: Count in-group app occurrences (agent-deduplicated) ────
        # Each (agent_id, normalized_name) pair is counted once per agent.
        from domains.sync.app_filters import active_match_stage

        in_group_pipeline: list[dict[str, Any]] = [
            active_match_stage(agent_id={"$in": group_agent_ids}),
            {
                "$group": {
                    "_id": "$normalized_name",
                    "agent_ids": {"$addToSet": "$agent_id"},
                    "display_name": {"$first": "$name"},
                }
            },
            {
                "$project": {
                    "normalized_name": "$_id",
                    "agent_count": {"$size": "$agent_ids"},
                    "display_name": 1,
                    "_id": 0,
                }
            },
        ]
        in_group_results: list[dict[str, Any]] = (
            await db["s1_installed_apps"].aggregate(in_group_pipeline).to_list(length=None)
        )

        if not in_group_results:
            return []

        # ── Step 3: Get total unique agents and per-app global counts ──────
        total_agent_count_result = await db["s1_agents"].count_documents({})
        total_agents: int = int(total_agent_count_result)

        # Build set of names we need global counts for
        in_group_names: list[str] = [r["normalized_name"] for r in in_group_results]

        global_pipeline: list[dict[str, Any]] = [
            active_match_stage(normalized_name={"$in": in_group_names}),
            {
                "$group": {
                    "_id": "$normalized_name",
                    "agent_ids": {"$addToSet": "$agent_id"},
                }
            },
            {
                "$project": {
                    "normalized_name": "$_id",
                    "total_agent_count": {"$size": "$agent_ids"},
                    "_id": 0,
                }
            },
        ]
        global_results: list[dict[str, Any]] = (
            await db["s1_installed_apps"].aggregate(global_pipeline).to_list(length=None)
        )

        global_counts: dict[str, int] = {
            r["normalized_name"]: r["total_agent_count"] for r in global_results
        }

        # ── Step 4: Gather existing marker patterns for this group ─────────
        from domains.fingerprint import repository as repo  # avoid circular at module level

        fp = await repo.get_by_group_id(db, group_id)
        existing_patterns: set[str] = set()
        if fp is not None:
            for m in fp.markers:
                existing_patterns.add(m.pattern.lower())

        # ── Step 5: Compute Lift scores ────────────────────────────────────
        # lift = P(app | group) / P(app) = group_coverage / base_rate
        # Capped at 99 to avoid N/group_size artifacts for tiny groups.
        now = utc_now()
        suggestions: list[FingerprintSuggestion] = []

        for row in in_group_results:
            norm_name: str = row["normalized_name"]
            in_group_cnt: int = row["agent_count"]
            display: str = row.get("display_name") or norm_name

            # Skip if the app name is already covered by an existing marker pattern (exact or glob)
            if any(matches_pattern(p, norm_name) for p in existing_patterns):
                continue

            # Document frequency: how many agents globally have this app
            df: int = global_counts.get(norm_name, in_group_cnt)
            # Out-of-group agent count
            out_of_group_cnt: int = max(0, df - in_group_cnt)

            group_coverage: float = in_group_cnt / group_agent_count
            base_rate: float = df / total_agents if total_agents > 0 else 0.0
            score: float = min(group_coverage / base_rate, 99.0) if base_rate > 0 else 0.0

            if score <= 0:
                continue

            outside_agents: int = max(0, total_agents - group_agent_count)
            outside_coverage: float = (
                out_of_group_cnt / outside_agents if outside_agents > 0 else 0.0
            )

            suggestions.append(
                FingerprintSuggestion(
                    group_id=group_id,
                    normalized_name=norm_name,
                    display_name=display,
                    score=round(score, 6),
                    group_coverage=round(group_coverage, 4),
                    outside_coverage=round(outside_coverage, 4),
                    agent_count_in_group=in_group_cnt,
                    agent_count_outside=out_of_group_cnt,
                    status="pending",
                    computed_at=now,
                )
            )

        # ── Step 6: Sort and truncate ──────────────────────────────────────
        suggestions.sort(key=lambda s: s.score, reverse=True)
        return suggestions[:_TOP_N]

    except KeyError as exc:
        # Expected when collections or required fields are missing (e.g.
        # s1_agents/s1_installed_apps not yet populated).
        logger.warning("compute_suggestions failed (missing data): {}", exc)
        return []
