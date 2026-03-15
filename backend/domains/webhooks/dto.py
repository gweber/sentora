"""Webhooks domain DTOs — request and response models for the HTTP boundary."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Request DTOs ──────────────────────────────────────────────────────────────


class _UrlSsrfMixin:
    @field_validator("url")
    @classmethod
    def validate_url_not_internal(cls, v: str) -> str:
        """Validate that webhook URL does not target internal hosts.

        Performs synchronous checks (scheme, hostname blocklist, IP literal
        ranges).  Full async DNS-based SSRF validation is done in the service
        layer at delivery time.
        """
        from utils.ssrf import BLOCKED_HOSTS, is_private_ip

        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Webhook URL must use http or https scheme")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Webhook URL must have a hostname")
        if hostname.lower() in BLOCKED_HOSTS:
            raise ValueError("Webhook URL must not target internal hosts")
        # Check if hostname is an IP literal pointing to a private/reserved range.
        # Full DNS-based SSRF validation is done async in the service layer.
        if is_private_ip(hostname):
            raise ValueError(f"Webhook URL must not target internal IP ({hostname})")
        return v


class WebhookCreateRequest(_UrlSsrfMixin, BaseModel):
    model_config = ConfigDict(strict=True)

    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048)
    events: list[str] = Field(min_length=1)
    secret: str = ""  # auto-generated if empty


class WebhookUpdateRequest(_UrlSsrfMixin, BaseModel):
    model_config = ConfigDict(strict=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    events: list[str] | None = Field(default=None, min_length=1)
    enabled: bool | None = None


# ── Response DTOs ─────────────────────────────────────────────────────────────


class WebhookResponse(BaseModel):
    """Webhook data returned by the API."""

    id: str
    name: str
    url: str
    events: list[str]
    enabled: bool
    created_at: str
    last_triggered_at: str | None
    failure_count: int
    last_error: str | None = None


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int | None = None
    response_time_ms: float
