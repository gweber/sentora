"""Taxonomy domain entities.

A SoftwareEntry represents a known application in the software catalog.
Entries are either seeded from the bundled YAML (``user_added=False``) or
added by users at runtime (``user_added=True``).

No cross-domain imports — this module must not import from sync, fingerprint,
or classification.
"""

from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from utils.dt import utc_now


class SoftwareEntry(BaseModel):
    """A single entry in the software taxonomy catalog.

    Attributes:
        id: MongoDB ObjectId (string representation).
        name: Human-readable display name (e.g. "Siemens WinCC").
        patterns: Glob patterns matched against ``normalized_name`` fields in
            ``s1_installed_apps``. Patterns are OR-combined.
        publisher: Optional software publisher / vendor name.
        category: Primary category key (matches the top-level YAML key, e.g. "scada_hmi").
        category_display: Human-readable category label (e.g. "SCADA / HMI / Process Control").
        subcategory: Optional finer-grained sub-grouping within the category.
        industry: Industry tags (e.g. ["manufacturing", "water_treatment"]).
        description: Optional free-text description of the software.
        is_universal: When True the entry is excluded from fingerprinting suggestions
            by default (e.g. browsers, runtimes). Users can override per-entry.
        user_added: False for seed data; True for entries created via the UI or API.
        created_at: Timestamp when the entry was first inserted.
        updated_at: Timestamp of the most recent update.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    name: str
    patterns: list[str]
    publisher: str | None = None
    category: str
    category_display: str = ""
    subcategory: str | None = None
    industry: list[str] = Field(default_factory=list)
    description: str | None = None
    is_universal: bool = False
    user_added: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
