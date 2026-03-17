"""CrowdStrike Falcon source adapter.

Implements the ``SourceAdapter`` interface for CrowdStrike Falcon.  The adapter
coordinates the CrowdStrike-specific phase runners and delegates actual API
interaction to the ``CrowdStrikeClient``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from domains.sources.base import ConnectionTestResult, SourceAdapter, SyncProgress, SyncResult

from .client import CrowdStrikeClient
from .sync_agents import CSAgentsPhaseRunner
from .sync_apps import CSAppsPhaseRunner
from .sync_groups import CSGroupsPhaseRunner


class CrowdStrikeAdapter(SourceAdapter):
    """CrowdStrike Falcon source adapter.

    Manages the lifecycle of CrowdStrike-specific sync phase runners and
    provides connection testing.
    """

    source_name = "crowdstrike"

    def __init__(self) -> None:
        self._groups_runner = CSGroupsPhaseRunner()
        self._agents_runner = CSAgentsPhaseRunner()
        self._apps_runner = CSAppsPhaseRunner()

    async def sync_agents(self, *, full: bool = False) -> SyncResult:
        """Sync CrowdStrike hosts into the canonical agents collection.

        Args:
            full: If True, perform a full sync (delete stale agents).

        Returns:
            SyncResult with counts.
        """
        mode = "full" if full else "auto"
        await self._agents_runner.trigger(mode=mode)
        return SyncResult(agents_synced=self._agents_runner._synced)

    async def sync_apps(self) -> SyncResult:
        """Sync CrowdStrike Discover applications.

        Returns:
            SyncResult with counts.
        """
        await self._apps_runner.trigger(mode="auto")
        return SyncResult(apps_synced=self._apps_runner._synced)

    async def test_connection(self, config: dict[str, object]) -> ConnectionTestResult:
        """Test CrowdStrike API connectivity and scope availability.

        Args:
            config: Dict with ``client_id``, ``client_secret``, ``base_url``,
                    and optionally ``member_cid``.

        Returns:
            ConnectionTestResult with scope details.
        """
        client = CrowdStrikeClient(
            client_id=str(config.get("client_id", "")),
            client_secret=str(config.get("client_secret", "")),
            base_url=str(config.get("base_url", "auto")),
            member_cid=str(config.get("member_cid", "")) or None,
        )
        try:
            detail = await client.test_connection()
            if not detail.hosts_readable:
                return ConnectionTestResult(
                    success=False,
                    message="Authentication failed or Hosts:READ scope missing",
                    details=_detail_to_dict(detail),
                )
            warnings: list[str] = []
            if not detail.discover_readable:
                warnings.append("Falcon Discover not licensed — app inventory unavailable")
            if not detail.host_groups_readable:
                warnings.append("Host Groups:READ scope missing — group names unavailable")
            message = f"Connected — {detail.host_count} hosts found ({detail.latency_ms}ms latency)"
            if warnings:
                message += " | " + "; ".join(warnings)
            return ConnectionTestResult(
                success=True,
                message=message,
                details=_detail_to_dict(detail),
            )
        except Exception as exc:
            logger.warning("CS connection test failed: {}", exc)
            return ConnectionTestResult(
                success=False,
                message=f"Connection failed: {exc}",
            )
        finally:
            await client.close()

    async def get_sync_progress(self) -> SyncProgress | None:
        """Get current CrowdStrike sync progress.

        Returns:
            SyncProgress or None if no sync is running.
        """
        for runner in (self._groups_runner, self._agents_runner, self._apps_runner):
            if runner.is_running:
                return SyncProgress(
                    phase=runner.phase_name,
                    synced=runner._synced,
                    total=runner._total,
                    message=runner._message or "",
                )
        return None

    async def cancel_sync(self) -> None:
        """Cancel all running CrowdStrike sync phases."""
        for runner in (self._groups_runner, self._agents_runner, self._apps_runner):
            if runner.is_running:
                await runner.cancel()


def _detail_to_dict(detail: Any) -> dict[str, object]:  # noqa: ANN401
    """Convert ConnectionTestDetail dataclass to a dict for serialization."""
    return {
        "hosts_readable": detail.hosts_readable,
        "discover_readable": detail.discover_readable,
        "host_groups_readable": detail.host_groups_readable,
        "host_count": detail.host_count,
        "region_detected": detail.region_detected,
        "latency_ms": detail.latency_ms,
    }
