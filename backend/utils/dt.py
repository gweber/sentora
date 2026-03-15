"""Datetime utilities.

Always use ``utc_now()`` from this module instead of ``datetime.utcnow()``
or ``datetime.now()``. This ensures consistent timezone-aware UTC datetimes
throughout the application and makes time mockable in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Returns:
        Current datetime with UTC timezone (tzinfo=UTC).
    """
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware UTC.

    MongoDB stores datetimes as UTC but returns them without tzinfo
    (timezone-naive). This helper normalises both naive and aware
    datetimes to UTC for safe comparisons with ``utc_now()``.

    Args:
        dt: A datetime that may or may not have tzinfo.

    Returns:
        The same instant as a timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
