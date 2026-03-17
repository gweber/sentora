"""EOL domain entities.

Pure domain objects for End-of-Life software lifecycle tracking.
No infrastructure dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class EOLCycle:
    """A single release cycle of a product tracked by endoflife.date.

    Attributes:
        cycle: Version identifier (e.g. ``3.12``, ``11``, ``2021``).
        release_date: When this cycle was first released.
        support_end: When active support/bugfixes end.
        eol_date: When security support ends — the key lifecycle date.
        lts: Whether this is a Long-Term Support release.
        latest_version: Latest patch release in this cycle.
        latest_version_date: Release date of the latest patch.
        is_eol: Computed — ``eol_date < today``.
        is_security_only: Computed — ``support_end < today AND eol_date >= today``.
    """

    cycle: str
    release_date: date | None = None
    support_end: date | None = None
    eol_date: date | None = None
    lts: bool = False
    latest_version: str | None = None
    latest_version_date: date | None = None
    is_eol: bool = False
    is_security_only: bool = False


@dataclass(frozen=True, slots=True)
class EOLProduct:
    """A product tracked by endoflife.date with its lifecycle data.

    Attributes:
        product_id: endoflife.date product slug (e.g. ``python``, ``windows``).
        name: Human-readable product name.
        cycles: All known release cycles.
        last_synced: When this product was last fetched from the API.
    """

    product_id: str
    name: str
    cycles: list[EOLCycle] = field(default_factory=list)
    last_synced: datetime | None = None


MatchSource = Literal["cpe", "fuzzy", "manual"]


@dataclass(frozen=True, slots=True)
class EOLMatch:
    """EOL lifecycle match for an installed application.

    Persisted on app summary documents so compliance checks can read
    pre-computed match data without re-running the matching engine.

    Attributes:
        eol_product_id: endoflife.date product slug.
        matched_cycle: Which release cycle matched (e.g. ``3.8``).
        match_source: How the match was made (``cpe``, ``fuzzy``, ``manual``).
        match_confidence: Confidence score from 0.0 to 1.0.
        is_eol: Whether this cycle is past its EOL date.
        eol_date: When security support ends/ended.
        is_security_only: In security-only support phase.
        support_end: When active support ended.
    """

    eol_product_id: str
    matched_cycle: str
    match_source: MatchSource
    match_confidence: float
    is_eol: bool
    eol_date: date | None = None
    is_security_only: bool = False
    support_end: date | None = None
