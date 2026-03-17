"""Deterministic UUID generation for canonical documents.

Every document in the canonical collections uses a deterministic UUID as
its ``_id``.  The UUID is derived from ``(source, source_id)`` using
UUID5 so that:

- The same source entity always produces the same ``_id``
- Upserts can match on ``_id`` directly (no compound index needed)
- IDs are portable across databases and not MongoDB-specific
"""

from __future__ import annotations

import uuid

# Fixed namespace UUID for Sentora canonical document IDs.
# Generated once, never changes.  All canonical UUIDs are derived from this.
_SENTORA_NS = uuid.UUID("a3f1b2c4-d5e6-7890-abcd-ef1234567890")


def canonical_id(source: str, source_id: str) -> str:
    """Generate a deterministic UUID for a canonical document.

    Args:
        source: Source adapter name (e.g. ``"sentinelone"``).
        source_id: Entity ID in the source system.

    Returns:
        UUID5 string derived from source + source_id.
    """
    return str(uuid.uuid5(_SENTORA_NS, f"{source}:{source_id}"))
