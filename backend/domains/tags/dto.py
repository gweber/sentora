"""Tags domain DTOs — request and response models for the HTTP boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Request DTOs ──────────────────────────────────────────────────────────────


class TagRuleCreateRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    tag_name: str = Field(min_length=1, max_length=100)
    description: str = ""


class TagRuleUpdateRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    tag_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class TagPatternCreateRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    pattern: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=200)
    category: str = "name_pattern"
    source: Literal["manual", "seed"] = "manual"


# ── Response DTOs ─────────────────────────────────────────────────────────────


class TagRulePatternResponse(BaseModel):
    id: str
    pattern: str
    display_name: str
    category: str
    source: str
    added_at: str
    added_by: str


class TagRuleResponse(BaseModel):
    id: str
    tag_name: str
    description: str
    patterns: list[TagRulePatternResponse]
    apply_status: str
    last_applied_at: str | None
    last_applied_count: int
    created_at: str
    updated_at: str
    created_by: str


class TagPreviewAgent(BaseModel):
    s1_agent_id: str
    hostname: str
    group_name: str
    site_name: str
    os_type: str
    matched_patterns: list[str]
    existing_tags: list[str] = []


class TagPreviewResponse(BaseModel):
    rule_id: str
    tag_name: str
    matched_count: int
    preview_capped: bool
    agents: list[TagPreviewAgent]


class TagApplyResponse(BaseModel):
    status: Literal["started", "already_running"]
    rule_id: str
