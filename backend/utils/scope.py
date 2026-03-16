"""Shared scope filter builder for agent queries.

Used by both the compliance and enforcement domains to build MongoDB
filters that restrict agent queries to specific S1 groups and/or tags.
"""

from __future__ import annotations

from typing import Any


def build_agent_scope_filter(
    scope_tags: list[str] | None = None,
    scope_groups: list[str] | None = None,
) -> dict[str, Any]:
    """Build a MongoDB query filter for scoped agent lookups.

    Combines tag and group conditions with ``$and`` when both are
    present.  Returns an empty dict when neither is specified (matches
    all agents).

    ``scope_groups`` filters on the ``group_name`` field and
    ``scope_tags`` filters on the ``tags`` array field of the
    ``s1_agents`` collection.

    Args:
        scope_tags: SentinelOne tags to filter agents by.
        scope_groups: SentinelOne group names to filter agents by.

    Returns:
        A MongoDB query filter dict.
    """
    conditions: list[dict[str, Any]] = []
    if scope_tags:
        conditions.append({"tags": {"$in": scope_tags}})
    if scope_groups:
        conditions.append({"group_name": {"$in": scope_groups}})

    if not conditions:
        return {}
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}
