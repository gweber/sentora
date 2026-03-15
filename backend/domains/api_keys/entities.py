"""API Keys domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ── Scope definitions ────────────────────────────────────────────────────────

AVAILABLE_SCOPES: dict[str, str] = {
    # Read-only scopes
    "agents:read": "List and view agents",
    "apps:read": "List and view installed applications",
    "compliance:read": "View compliance results and violations",
    "enforcement:read": "View enforcement rules and violations",
    "audit:read": "View audit log entries",
    "sync:read": "View sync status and history",
    "taxonomy:read": "View taxonomy categories",
    "fingerprints:read": "View fingerprints",
    "dashboard:read": "View dashboard metrics",
    # Write scopes
    "sync:trigger": "Trigger a manual sync",
    "enforcement:write": "Create and modify enforcement rules",
    "tags:write": "Create and assign tags",
    # Convenience groups
    "read:all": "All read-only scopes",
    "write:all": "All write scopes (implies read:all)",
}

READ_SCOPES: frozenset[str] = frozenset(s for s in AVAILABLE_SCOPES if s.endswith(":read"))

WRITE_SCOPES: frozenset[str] = frozenset(
    s for s in AVAILABLE_SCOPES if s not in READ_SCOPES and s not in {"read:all", "write:all"}
)


def expand_scopes(scopes: list[str]) -> set[str]:
    """Expand convenience groups into individual scopes."""
    result: set[str] = set()
    for scope in scopes:
        if scope == "write:all":
            result |= READ_SCOPES | WRITE_SCOPES
        elif scope == "read:all":
            result |= READ_SCOPES
        else:
            result.add(scope)
    return result


@dataclass
class APIKey:
    """API key entity bound to a tenant for external integrations.

    Attributes:
        id: Internal unique identifier.
        tenant_id: Tenant this key belongs to.
        name: Human-readable label (e.g. "Splunk Integration").
        description: Optional longer description.
        key_prefix: First 20 characters of the key for UI identification.
        key_hash: SHA-256 hash of the full key (only stored form).
        scopes: Granted permission scopes.
        rate_limit_per_minute: Max requests per minute for this key.
        rate_limit_per_hour: Max requests per hour for this key.
        created_at: When the key was created.
        created_by: Username of the creator.
        expires_at: Optional expiration timestamp.
        last_used_at: Most recent usage timestamp.
        last_used_ip: IP of most recent usage.
        is_active: Whether the key is currently usable.
        revoked_at: When the key was revoked.
        revoked_by: Username of the revoker.
    """

    id: str
    tenant_id: str
    name: str
    key_prefix: str
    key_hash: str
    scopes: list[str]
    created_at: datetime
    created_by: str
    description: str | None = None
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    is_active: bool = True
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    # Grace period support for key rotation
    grace_expires_at: datetime | None = None
    rotated_from_id: str | None = field(default=None)
