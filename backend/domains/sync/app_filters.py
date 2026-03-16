"""Installed-apps query helpers.

Provides reusable MongoDB filter/match-stage constructors that exclude
soft-deleted (``active: False``) app records.  Using ``$ne: False`` (rather
than ``== True``) ensures that legacy documents without an ``active`` field
are included.

Usage in aggregation pipelines::

    from domains.sync.app_filters import active_match_stage

    pipeline = [active_match_stage(agent_id=some_id), {"$group": ...}]

Usage in find queries::

    from domains.sync.app_filters import active_filter

    cursor = db["s1_installed_apps"].find(active_filter(agent_id=some_id))
"""

from __future__ import annotations

from typing import Any

# Base filter — excludes soft-deleted records while including legacy docs
# that don't have the ``active`` field at all.
_ACTIVE_BASE: dict[str, Any] = {"active": {"$ne": False}}


def active_filter(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Return a MongoDB query filter that excludes soft-deleted apps.

    Args:
        **extra: Additional filter fields merged into the result.

    Returns:
        Dict suitable for ``find()`` / ``count_documents()`` / ``update_many()``.
    """
    return {**_ACTIVE_BASE, **extra}


def active_match_stage(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    """Return a ``$match`` pipeline stage that excludes soft-deleted apps.

    Args:
        **extra: Additional match conditions merged into the ``$match`` body.

    Returns:
        ``{"$match": {...}}`` dict for use in aggregation pipelines.
    """
    return {"$match": active_filter(**extra)}
