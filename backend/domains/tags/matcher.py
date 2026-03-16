"""Tags domain matcher — find agents whose installed apps match a tag rule."""

from __future__ import annotations

import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.fingerprint.matcher import matches_pattern
from domains.tags.dto import TagPreviewAgent
from domains.tags.entities import TagRule

_PREVIEW_CAP = 500

_GLOB_METACHARACTERS = frozenset("*?")


def _is_exact_pattern(pattern: str) -> bool:
    """Return True if the pattern contains no glob metacharacters."""
    return not any(c in pattern for c in _GLOB_METACHARACTERS)


async def find_matching_agents(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    rule: TagRule,
    cap: int | None = _PREVIEW_CAP,
) -> tuple[list[TagPreviewAgent], int]:
    """Find agents whose installed apps match any pattern in the rule.

    Streams agents from MongoDB to avoid loading the entire fleet into memory.
    An agent matches if ANY of its ``installed_app_names`` matches ANY pattern
    in the rule.

    For patterns that are exact strings (no glob metacharacters), a MongoDB
    ``$in`` query is used to pre-filter agents server-side, avoiding a full
    collection scan when possible.

    Args:
        db: Motor database handle.
        rule: The tag rule to evaluate.
        cap: Maximum number of agents to return (``None`` for unlimited, used
             by the apply flow).

    Returns:
        Tuple of (agents, total_matched_count). ``agents`` is sorted by
        hostname and capped at ``cap`` if set; ``total_matched_count`` reflects
        the true total regardless of the cap.
    """
    if not rule.patterns:
        return [], 0

    exact_patterns = [p.pattern for p in rule.patterns if _is_exact_pattern(p.pattern)]
    glob_patterns = [p for p in rule.patterns if not _is_exact_pattern(p.pattern)]

    # Normalize exact patterns to lowercase for case-insensitive matching,
    # consistent with how the fingerprint matcher operates (AUDIT-041).
    exact_patterns_lower = [p.lower() for p in exact_patterns]

    query: dict[str, Any] = {}
    if exact_patterns and not glob_patterns:
        # All patterns are exact — use case-insensitive $regex matching.
        # Build an $or array of regex conditions for each lowered pattern.
        query["$or"] = [
            {"installed_app_names": {"$regex": f"^{re.escape(p)}$", "$options": "i"}}
            for p in exact_patterns_lower
        ]
    elif exact_patterns and glob_patterns:
        # Mixed: need to check both exact AND glob, so query for agents
        # that have ANY of the exact names OR have installed apps at all
        # (glob patterns require Python-side evaluation on all agents).
        # At minimum, skip agents with no installed apps.
        query = {"installed_app_names": {"$exists": True, "$ne": []}}
    elif glob_patterns:
        # Only globs — need agents for Python-side matching.
        # Skip agents with no installed apps (they can't match any pattern).
        query = {"installed_app_names": {"$exists": True, "$ne": []}}

    projection = {
        "s1_agent_id": 1,
        "hostname": 1,
        "group_name": 1,
        "site_name": 1,
        "os_type": 1,
        "installed_app_names": 1,
        "tags": 1,
    }

    results: list[TagPreviewAgent] = []
    total_matched = 0

    cursor = db["s1_agents"].find(query, projection)

    async for doc in cursor:
        agent_apps: list[str] = doc.get("installed_app_names") or []
        agent_app_set_lower: set[str] = {a.lower() for a in agent_apps}
        matched_patterns: list[str] = []

        if exact_patterns and not glob_patterns:
            # All patterns are exact — case-insensitive comparison
            for ep, ep_lower in zip(exact_patterns, exact_patterns_lower, strict=True):
                if ep_lower in agent_app_set_lower:
                    matched_patterns.append(ep)
        else:
            for p in rule.patterns:
                if _is_exact_pattern(p.pattern):
                    if p.pattern.lower() in agent_app_set_lower:
                        matched_patterns.append(p.pattern)
                else:
                    for app_name in agent_apps:
                        if matches_pattern(p.pattern, app_name):
                            matched_patterns.append(p.pattern)
                            break  # this pattern matched — don't double-count it

        if matched_patterns:
            total_matched += 1
            if cap is None or len(results) < cap:
                results.append(
                    TagPreviewAgent(
                        s1_agent_id=doc.get("s1_agent_id", ""),
                        hostname=doc.get("hostname", ""),
                        group_name=doc.get("group_name", ""),
                        site_name=doc.get("site_name", ""),
                        os_type=doc.get("os_type", ""),
                        matched_patterns=matched_patterns,
                        existing_tags=doc.get("tags") or [],
                    )
                )

    results.sort(key=lambda a: a.hostname)
    return results, total_matched
