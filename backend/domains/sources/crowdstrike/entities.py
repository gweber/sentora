"""CrowdStrike-specific domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field

# ── API region constants ──────────────────────────────────────────────────────

REGION_URLS: dict[str, str] = {
    "auto": "auto",
    "us-1": "https://api.crowdstrike.com",
    "us-2": "https://api.us-2.crowdstrike.com",
    "eu-1": "https://api.eu-1.crowdstrike.com",
    "us-gov-1": "https://api.laggar.gcw.crowdstrike.com",
}

APP_SYNC_STRATEGIES = ("hybrid", "per_host", "bulk")


@dataclass(frozen=True, slots=True)
class CrowdStrikeConfig:
    """Connection and sync configuration for a CrowdStrike Falcon tenant.

    Attributes:
        client_id: OAuth2 API client ID from the CrowdStrike console.
        client_secret: OAuth2 API client secret (stored encrypted).
        base_url: Region URL or ``"auto"`` for auto-discovery.
        member_cid: MSSP child customer ID (optional, for managed service providers).
        sync_interval_hours: Hours between automatic scheduled syncs.
        app_sync_strategy: Application sync approach — ``"hybrid"`` (default),
            ``"per_host"``, or ``"bulk"``.
        sync_apps: Whether to sync applications via Falcon Discover.
        enabled: Whether this integration is active.
    """

    client_id: str
    client_secret: str
    base_url: str = "auto"
    member_cid: str | None = None
    sync_interval_hours: int = 4
    app_sync_strategy: str = "hybrid"
    sync_apps: bool = True
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ConnectionTestDetail:
    """Detailed results from a CrowdStrike connection test.

    Attributes:
        hosts_readable: Whether the ``Hosts: READ`` scope is available.
        discover_readable: Whether the ``Falcon Discover: READ`` scope is available.
        host_groups_readable: Whether the ``Host Groups: READ`` scope is available.
        host_count: Number of hosts found (from first Hosts API page).
        region_detected: Resolved API region (from FalconPy auto-discovery).
        latency_ms: Round-trip latency for the test request.
    """

    hosts_readable: bool = False
    discover_readable: bool = False
    host_groups_readable: bool = False
    host_count: int = 0
    region_detected: str = ""
    latency_ms: int = 0


@dataclass(slots=True)
class ScrollResult:
    """Result from a CrowdStrike scroll-based host query.

    Attributes:
        aids: List of Agent IDs (device_id) returned in this page.
        next_offset: Cursor for the next page (empty string if done).
        total: Total number of matching hosts (from first page only).
    """

    aids: list[str] = field(default_factory=list)
    next_offset: str = ""
    total: int = 0


@dataclass(slots=True)
class AppPageResult:
    """Result from a CrowdStrike Discover applications query.

    Attributes:
        applications: List of application dicts returned in this page.
        after: Cursor for the next page (empty string if done).
        total: Total number of matching applications (from first page only).
    """

    applications: list[dict] = field(default_factory=list)
    after: str = ""
    total: int = 0
