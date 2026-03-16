"""Deterministic SHA-256 hash computation for audit chain entries.

This module is the single source of truth for hash computation. It is
intentionally free of framework dependencies (no Motor, no FastAPI, no
Pydantic) so that it can be embedded verbatim in the air-gapped CLI
verification tool.

The canonical serialisation uses ``json.dumps`` with ``sort_keys=True``
and ``ensure_ascii=True`` to guarantee deterministic, reproducible output
across Python versions and platforms.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Sentinel value used as ``previous_hash`` for the genesis entry.
GENESIS_SENTINEL = "GENESIS"

#: Hash algorithm identifier stored in chain metadata.
CHAIN_ALGORITHM = "SHA-256"


def compute_entry_hash(entry: dict[str, Any], previous_hash: str | None) -> str:
    """Compute the SHA-256 hash of an audit log entry.

    The hash covers all content-bearing fields plus the previous entry's
    hash (chain link).  Fields that are DB-internal (``_id``) or set
    retroactively (``is_epoch_end``) are excluded.

    Args:
        entry: Dict containing at minimum ``sequence``, ``epoch``,
            ``timestamp``, ``event_type`` (or ``action``), ``domain``,
            ``actor``, ``status``, ``summary``, ``details``, and
            optionally ``tenant_id``.
        previous_hash: Hash of the preceding entry, or ``None`` for the
            genesis entry (substituted with ``"GENESIS"``).

    Returns:
        Lowercase hex-encoded SHA-256 digest.
    """
    hashable = _build_hashable(entry, previous_hash)
    canonical = json.dumps(hashable, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_export_hash(entries: list[dict[str, Any]]) -> str:
    """Compute the SHA-256 integrity hash over an entire export payload.

    Each entry is canonically serialised and concatenated before hashing.
    This binds the export metadata to the entries — altering any single
    entry invalidates the export hash.

    Args:
        entries: Ordered list of audit entry dicts (as stored in the
            export JSON ``entries`` array).

    Returns:
        Lowercase hex-encoded SHA-256 digest.
    """
    hasher = hashlib.sha256()
    for entry in entries:
        canonical = json.dumps(entry, sort_keys=True, ensure_ascii=True, default=str)
        hasher.update(canonical.encode("utf-8"))
    return hasher.hexdigest()


def _normalize_timestamp(ts: Any) -> str:  # noqa: ANN401
    """Normalise a timestamp to a canonical string for hashing.

    MongoDB stores BSON datetime with millisecond precision and returns
    naive datetimes.  Python ``datetime.isoformat()`` output varies
    depending on timezone awareness and microsecond precision.

    This function produces a fixed-format string that is identical
    regardless of whether the input is a timezone-aware datetime, a
    naive datetime, or an ISO-format string.

    Format: ``YYYY-MM-DDTHH:MM:SS.fffZ`` (UTC, millisecond precision,
    trailing ``Z``).

    Args:
        ts: datetime object or ISO-format string.

    Returns:
        Canonical timestamp string.
    """
    if hasattr(ts, "strftime"):
        # Truncate to millisecond precision (MongoDB drops sub-ms)
        truncated = ts.replace(microsecond=(ts.microsecond // 1000) * 1000)
        return truncated.strftime("%Y-%m-%dT%H:%M:%S.") + f"{truncated.microsecond // 1000:03d}Z"
    # String input — parse, normalise, re-format
    s = str(ts)
    # Handle common ISO suffixes: +00:00, Z, or no suffix
    from datetime import datetime

    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return _normalize_timestamp(dt)
        except ValueError:
            continue
    # Fallback — return as-is (should not happen with well-formed data)
    return s


def _build_hashable(entry: dict[str, Any], previous_hash: str | None) -> dict[str, Any]:
    """Build the canonical dict used as hash input.

    The field set is fixed and order-independent (``sort_keys=True``
    handles ordering).  Only content-bearing fields are included.

    Args:
        entry: Raw audit entry dict.
        previous_hash: Previous entry hash or ``None``.

    Returns:
        Canonical dict ready for JSON serialisation.
    """
    timestamp = _normalize_timestamp(entry.get("timestamp"))

    return {
        "sequence": entry["sequence"],
        "epoch": entry["epoch"],
        "timestamp": timestamp,
        "domain": entry.get("domain", ""),
        "action": entry.get("action", ""),
        "actor": entry.get("actor", ""),
        "status": entry.get("status", ""),
        "summary": entry.get("summary", ""),
        "details": entry.get("details"),
        "tenant_id": entry.get("tenant_id"),
        "previous_hash": previous_hash or GENESIS_SENTINEL,
    }
