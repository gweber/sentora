"""API Keys domain DTOs — request/response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreateRequest(BaseModel):
    """POST /api-keys — create a new API key."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    scopes: list[str] = Field(..., min_length=1)
    rate_limit_per_minute: int = Field(60, ge=1, le=10000)
    rate_limit_per_hour: int = Field(1000, ge=1, le=100000)
    expires_at: datetime | None = None


class APIKeyUpdateRequest(BaseModel):
    """PUT /api-keys/{id} — update an API key (not the key itself)."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    scopes: list[str] | None = Field(None, min_length=1)
    rate_limit_per_minute: int | None = Field(None, ge=1, le=10000)
    rate_limit_per_hour: int | None = Field(None, ge=1, le=100000)
    expires_at: datetime | None = None


class APIKeyResponse(BaseModel):
    """API key metadata (never includes the full key)."""

    id: str
    tenant_id: str
    name: str
    description: str | None = None
    key_prefix: str
    scopes: list[str]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    created_at: datetime
    created_by: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    is_active: bool
    revoked_at: datetime | None = None
    revoked_by: str | None = None


class APIKeyCreateResponse(BaseModel):
    """Returned once on creation — contains the full key."""

    key: APIKeyResponse
    full_key: str = Field(
        ...,
        description="The full API key. This is shown ONCE and cannot be retrieved again.",
    )


class APIKeyRotateResponse(BaseModel):
    """Returned on rotation — contains the new full key."""

    key: APIKeyResponse
    full_key: str = Field(
        ...,
        description="The new API key. The old key remains valid for 5 minutes.",
    )


class APIKeyCurrentResponse(BaseModel):
    """GET /api-keys/current — self-info for an authenticated API key."""

    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    last_used_at: datetime | None = None
