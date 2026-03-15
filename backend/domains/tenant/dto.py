"""Tenant domain DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TenantCreateRequest(BaseModel):
    """Request body for creating a new tenant."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
    plan: str = Field(default="standard", pattern=r"^(standard|enterprise)$")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is URL-safe and doesn't conflict with reserved names."""
        reserved = {"admin", "api", "health", "metrics", "auth", "www", "app", "master", "default"}
        if v.lower() in reserved:
            msg = f"Slug '{v}' is reserved"
            raise ValueError(msg)
        return v.lower()


class TenantUpdateRequest(BaseModel):
    """Partial update for a tenant."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    disabled: bool | None = None
    plan: str | None = Field(default=None, pattern=r"^(standard|enterprise)$")


class TenantResponse(BaseModel):
    """Tenant information returned by the API."""

    id: str
    name: str
    slug: str
    database_name: str
    created_at: str
    disabled: bool
    plan: str


class TenantListResponse(BaseModel):
    """Paginated list of tenants."""

    tenants: list[TenantResponse]
    total: int
