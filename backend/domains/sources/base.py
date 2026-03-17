"""Abstract base class for source adapters.

Every EDR integration (SentinelOne, CrowdStrike, Defender, CSV import)
implements this interface.  The sync orchestrator calls these methods
without knowing which source is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome of a sync operation.

    Attributes:
        agents_synced: Number of agents written.
        apps_synced: Number of installed apps written.
        groups_synced: Number of groups written.
        sites_synced: Number of sites written.
        tags_synced: Number of source tags written.
        errors: Number of errors encountered.
        duration_ms: Wall-clock duration in milliseconds.
    """

    agents_synced: int = 0
    apps_synced: int = 0
    groups_synced: int = 0
    sites_synced: int = 0
    tags_synced: int = 0
    errors: int = 0
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    """Outcome of a source connection test.

    Attributes:
        success: Whether the connection succeeded.
        message: Human-readable status message.
        details: Additional diagnostic info.
    """

    success: bool
    message: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SyncProgress:
    """Current progress of a running sync.

    Attributes:
        phase: Current phase name.
        synced: Items processed so far.
        total: Expected total items (0 if unknown).
        message: Human-readable status.
    """

    phase: str
    synced: int
    total: int
    message: str


class SourceAdapter(ABC):
    """Base class for all data source adapters.

    Subclasses MUST set ``source_name`` to a unique, lowercase identifier
    (e.g. ``"sentinelone"``, ``"crowdstrike"``).

    Adapters are responsible for:
    - Fetching data from the external source API
    - Normalizing field names and values to the canonical schema
    - Setting ``source`` and ``source_id`` on every document
    - Writing to the canonical collections via upsert
    """

    source_name: str

    @abstractmethod
    async def sync_agents(self, *, full: bool = False) -> SyncResult:
        """Sync agent data from source into canonical ``agents`` collection.

        Args:
            full: If True, perform a full sync (delete stale agents).
                  If False, perform an incremental sync.

        Returns:
            SyncResult with counts of synced entities.
        """

    @abstractmethod
    async def sync_apps(self) -> SyncResult:
        """Sync installed apps from source into canonical ``installed_apps`` collection.

        Returns:
            SyncResult with counts of synced apps.
        """

    @abstractmethod
    async def test_connection(self, config: dict[str, object]) -> ConnectionTestResult:
        """Test if the source is reachable with given credentials.

        Args:
            config: Source-specific connection configuration.

        Returns:
            ConnectionTestResult indicating success or failure.
        """

    @abstractmethod
    async def get_sync_progress(self) -> SyncProgress | None:
        """Get current sync progress if a sync is running.

        Returns:
            SyncProgress or None if no sync is active.
        """

    @abstractmethod
    async def cancel_sync(self) -> None:
        """Cancel any running sync operation."""
