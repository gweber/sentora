"""Taxonomy domain DTOs (Data Transfer Objects).

DTOs are the API contract — never expose domain entities directly. All
request validation and response shaping happens here. Pydantic strict mode
is used on request DTOs to reject unexpected fields.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ── Request DTOs ──────────────────────────────────────────────────────────────


class SoftwareEntryCreateRequest(BaseModel):
    """Payload for adding a new software entry to the taxonomy.

    Attributes:
        name: Display name for the software.
        patterns: One or more glob patterns to match against normalized app names.
        publisher: Optional vendor / publisher name.
        category: Category key (must match an existing category or create a new one).
        category_display: Human-readable label for the category.
        subcategory: Optional sub-grouping within the category.
        industry: Industry tags.
        description: Optional free-text description.
        is_universal: If True, excluded from fingerprint suggestions by default.
    """

    model_config = ConfigDict(strict=True)

    name: str = Field(min_length=1, max_length=200)
    patterns: list[str] = Field(min_length=1)
    publisher: str | None = None
    category: str = Field(min_length=1, max_length=100)
    category_display: str = ""
    subcategory: str | None = None
    industry: list[str] = Field(default_factory=list)
    description: str | None = None
    is_universal: bool = False


class SoftwareEntryUpdateRequest(BaseModel):
    """Payload for partially updating a software taxonomy entry.

    All fields are optional — only provided fields are updated.

    Attributes:
        name: New display name.
        patterns: Replacement pattern list.
        publisher: New publisher name (None clears it).
        category: New category key.
        category_display: New human-readable category label.
        subcategory: New subcategory (None clears it).
        industry: Replacement industry tag list.
        description: New description (None clears it).
        is_universal: Toggle universal exclusion flag.
    """

    model_config = ConfigDict(strict=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    patterns: list[str] | None = Field(default=None, min_length=1)
    publisher: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    category_display: str | None = None
    subcategory: str | None = None
    industry: list[str] | None = None
    description: str | None = None
    is_universal: bool | None = None


class PatternPreviewRequest(BaseModel):
    """Payload for previewing which agents/apps would match glob patterns.

    Supports both single-pattern (``pattern``) and multi-pattern (``patterns``)
    modes. If ``patterns`` is provided, ``pattern`` is ignored.

    Attributes:
        pattern: A single glob pattern to test (e.g. "wincc*").
        patterns: Multiple glob patterns to test at once (OR-combined).
        group_id: Optional SentinelOne group ID to restrict results to.
    """

    model_config = ConfigDict(strict=True)

    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    patterns: list[str] | None = Field(default=None, min_length=1)


# ── Response DTOs ─────────────────────────────────────────────────────────────


class SoftwareEntryResponse(BaseModel):
    """Response shape for a single software taxonomy entry.

    Attributes:
        id: String ObjectId of the entry.
        name: Display name.
        patterns: Glob patterns.
        publisher: Vendor name or None.
        category: Category key.
        category_display: Human-readable category label.
        subcategory: Sub-grouping or None.
        industry: Industry tags.
        description: Description or None.
        is_universal: Whether excluded from fingerprinting by default.
        user_added: False for seed data, True for user-created entries.
        created_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 last-updated timestamp.
    """

    id: str
    name: str
    patterns: list[str]
    publisher: str | None
    category: str
    category_display: str
    subcategory: str | None
    industry: list[str]
    description: str | None
    is_universal: bool
    user_added: bool
    created_at: str
    updated_at: str


class CategorySummary(BaseModel):
    """Summary of a taxonomy category for the category list endpoint.

    Attributes:
        key: Internal category key (e.g. "scada_hmi").
        display: Human-readable label (e.g. "SCADA / HMI / Process Control").
        entry_count: Number of software entries in this category.
    """

    key: str
    display: str
    entry_count: int


class CategoryCreateRequest(BaseModel):
    """Payload for creating a new taxonomy category.

    Attributes:
        key: Unique category key (e.g. "scada_hmi").
        display: Human-readable label (e.g. "SCADA / HMI / Process Control").
    """

    model_config = ConfigDict(strict=True)

    key: str = Field(min_length=1, max_length=100)
    display: str = Field(min_length=1, max_length=200)


class CategoryUpdateRequest(BaseModel):
    """Payload for renaming a category (key and/or display label).

    Attributes:
        key: New category key. Omit to keep the existing key.
        display: New human-readable label. Omit to keep the existing label.
    """

    model_config = ConfigDict(strict=True)

    key: str | None = Field(default=None, min_length=1, max_length=100)
    display: str | None = Field(default=None, min_length=1, max_length=200)


class CategoryUpdateResponse(BaseModel):
    """Response after a category rename operation.

    Attributes:
        old_key: Category key before the rename.
        new_key: Category key after the rename.
        display: Updated display label.
        entries_updated: Number of entries that were modified.
    """

    old_key: str
    new_key: str
    display: str
    entries_updated: int


class CategoryDeleteResponse(BaseModel):
    """Response after deleting a category.

    Attributes:
        key: The category key that was deleted.
        entries_deleted: Number of entries that were removed.
    """

    key: str
    entries_deleted: int


class CategoryListResponse(BaseModel):
    """Response for the list-categories endpoint.

    Attributes:
        categories: All categories with their entry counts.
        total: Total number of categories.
    """

    categories: list[CategorySummary]
    total: int


class SoftwareEntryListResponse(BaseModel):
    """Paginated list of software entries.

    Attributes:
        entries: The current page of software entries.
        total: Total number of matching entries.
    """

    entries: list[SoftwareEntryResponse]
    total: int


class AppMatch(BaseModel):
    """A distinct app name matched by a pattern preview."""

    normalized_name: str
    display_name: str
    publisher: str | None
    agent_count: int


class GroupCount(BaseModel):
    """Agent count per group in a pattern preview."""

    group_name: str
    agent_count: int


class PatternPreviewResponse(BaseModel):
    """Response for the pattern preview endpoint.

    Attributes:
        patterns: The patterns that were tested.
        total_apps: Number of distinct app names matched.
        total_agents: Number of agents that have at least one matching app.
        app_matches: Top matched apps sorted by agent_count desc (up to 50).
        group_counts: Agent count per group (up to 20 groups).
    """

    patterns: list[str]
    total_apps: int
    total_agents: int
    app_matches: list[AppMatch]
    group_counts: list[GroupCount]
