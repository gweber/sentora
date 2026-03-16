"""Tags domain entities.

Tag rules define which S1 tag to apply to agents whose installed-app names
match a set of glob patterns. Matching is binary (any match = tagged) — no
weighted scoring. Tags are applied additively back to S1 via the manage-tags
action endpoint.

MongoDB storage notes
---------------------
- Tag rules are stored in the ``tag_rules`` collection, one document per rule.
- ``tag_name`` is unique — it maps directly to the S1 tag key.
- ``patterns`` are embedded in the rule document.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from utils.dt import utc_now


class TagRulePattern(BaseModel):
    """A single glob pattern within a tag rule.

    Attributes:
        id: Unique pattern identifier (string ObjectId).
        pattern: Glob matched against ``installed_app_names`` on agents.
        display_name: Human-readable label shown in the UI.
        category: Pattern category key (e.g. ``"name_pattern"``).
        source: How the pattern was created — ``"manual"`` or ``"seed"``.
        added_at: Timestamp when the pattern was added.
        added_by: Identifier of the user or system that added it.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    pattern: str
    display_name: str
    category: str = "name_pattern"
    source: Literal["manual", "seed"] = "manual"
    added_at: datetime = Field(default_factory=utc_now)
    added_by: str = "system"


class TagRule(BaseModel):
    """A named tag rule that matches agents via glob patterns.

    Attributes:
        id: MongoDB document identifier (string ObjectId).
        tag_name: The S1 tag key to apply (unique, maps to S1 ``manage-tags``).
        description: Optional free-text description.
        patterns: Ordered list of glob patterns; an agent matches if any
            of its installed app names matches any pattern.
        apply_status: Current lifecycle state of the last apply operation.
        last_applied_at: Timestamp of the last successful apply.
        last_applied_count: Number of agents tagged in the last apply run.
        created_at: Timestamp of creation.
        updated_at: Timestamp of the most recent update.
        created_by: Identifier of the creator.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tag_name: str
    description: str = ""
    patterns: list[TagRulePattern] = Field(default_factory=list)
    apply_status: Literal["idle", "running", "done", "failed"] = "idle"
    last_applied_at: datetime | None = None
    last_applied_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: str = "system"
