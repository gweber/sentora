"""CrowdStrike integration request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .entities import APP_SYNC_STRATEGIES, REGION_URLS


class CSConnectionTestRequest(BaseModel):
    """Request body for testing CrowdStrike API connectivity."""

    client_id: str = Field(min_length=1, description="CrowdStrike OAuth2 Client ID")
    client_secret: str = Field(min_length=1, description="CrowdStrike OAuth2 Client Secret")
    base_url: str = Field(
        default="auto",
        description="API region: auto, us-1, us-2, eu-1, us-gov-1",
    )
    member_cid: str = Field(
        default="",
        description="MSSP child CID (optional, for managed service providers)",
    )

    def validate_region(self) -> str:
        """Return the resolved base URL for the region.

        Returns:
            The region URL or ``"auto"`` for auto-discovery.

        Raises:
            ValueError: If the region key is not recognized.
        """
        if self.base_url in REGION_URLS:
            return REGION_URLS[self.base_url]
        raise ValueError(f"Unknown region: {self.base_url}. Valid: {', '.join(REGION_URLS)}")


class CSConnectionTestResponse(BaseModel):
    """Response from a CrowdStrike connection test."""

    success: bool
    message: str
    hosts_readable: bool = False
    discover_readable: bool = False
    host_groups_readable: bool = False
    host_count: int = 0
    latency_ms: int = 0


class CSIntegrationConfig(BaseModel):
    """Persisted CrowdStrike integration configuration."""

    source: str = "crowdstrike"
    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)
    base_url: str = Field(default="auto")
    member_cid: str = Field(default="")
    sync_interval_hours: int = Field(default=4, ge=1, le=168)
    app_sync_strategy: str = Field(default="hybrid")
    sync_apps: bool = Field(default=True)
    enabled: bool = Field(default=True)
    last_tested_at: str | None = None
    last_test_result: str | None = None

    def validate_app_sync_strategy(self) -> None:
        """Ensure app_sync_strategy is valid.

        Raises:
            ValueError: If the strategy is not recognized.
        """
        if self.app_sync_strategy not in APP_SYNC_STRATEGIES:
            raise ValueError(
                f"Unknown app_sync_strategy: {self.app_sync_strategy}. "
                f"Valid: {', '.join(APP_SYNC_STRATEGIES)}"
            )
