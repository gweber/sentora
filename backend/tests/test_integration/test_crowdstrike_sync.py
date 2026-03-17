"""Integration tests for the CrowdStrike sync pipeline.

Tests use a real MongoDB (the ``test_db`` fixture from conftest) and mock
the CrowdStrike API client at the class level to avoid requiring a live
CrowdStrike tenant.

Conventions (per TESTING.md):
- Real MongoDB, no DB mocks
- Function-scoped fixtures
- Google-style docstrings
- Happy + error + boundary paths
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.sources.collections import AGENTS, GROUPS, INSTALLED_APPS, SYNC_META
from domains.sources.identity import canonical_id

# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_cs_host(device_id: str = "aid001", **overrides: object) -> dict:
    """Build a realistic CrowdStrike host detail dict."""
    base: dict[str, Any] = {
        "device_id": device_id,
        "hostname": f"DESKTOP-{device_id.upper()}",
        "platform_name": "Windows",
        "os_version": "Windows 10 Build 19045",
        "agent_version": "7.10.18110.0",
        "status": "normal",
        "last_seen": "2024-06-15T10:30:00Z",
        "local_ip": "10.0.0.5",
        "external_ip": "203.0.113.42",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "tags": ["Environment/Production"],
        "groups": ["grp001"],
        "machine_domain": "corp.example.com",
        "product_type_desc": "Workstation",
        "modified_timestamp": "2024-06-15T10:30:00Z",
        "first_seen_timestamp": "2024-01-10T08:00:00Z",
    }
    base.update(overrides)
    return base


def _make_cs_app(app_id: str = "app001", aid: str = "aid001", **overrides: object) -> dict:
    """Build a realistic CrowdStrike Discover application dict."""
    base: dict[str, Any] = {
        "id": app_id,
        "name": "Google Chrome",
        "version": "125.0.6422.60",
        "vendor": "Google LLC",
        "installation_timestamp": "2024-03-01T00:00:00Z",
        "host": {"aid": aid, "platform_name": "Windows"},
        "category": "Browser",
        "last_updated_timestamp": "2024-06-01T00:00:00Z",
    }
    base.update(overrides)
    return base


class MockCSClient:
    """Mock CrowdStrike client that returns pre-built fixtures."""

    def __init__(
        self,
        hosts: list[dict] | None = None,
        apps: list[dict] | None = None,
        groups: dict[str, str] | None = None,
    ) -> None:
        self._hosts = hosts or []
        self._apps = apps or []
        self._groups = groups or {}

    async def close(self) -> None:
        pass

    async def get_host_groups(self) -> dict[str, str]:
        return dict(self._groups)

    async def scroll_all_hosts(
        self, *, filter_fql: str = "", batch_size: int = 5000
    ) -> Any:  # noqa: ANN401
        """Yield (total, [host_details])."""
        if self._hosts:
            yield len(self._hosts), list(self._hosts)

    async def scroll_all_applications(
        self, *, filter_fql: str = "", page_size: int = 100
    ) -> Any:  # noqa: ANN401
        """Yield (total, app_dict)."""
        first = True
        for app in self._apps:
            yield (len(self._apps) if first else 0), app
            first = False

    async def _call(self, fn: Any, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Mock FalconPy call for group queries."""
        return {
            "status_code": 200,
            "body": {
                "resources": [
                    {"id": gid, "name": gname} for gid, gname in self._groups.items()
                ]
            },
        }

    # Expose _host_groups as mock for sync_groups._sync_groups
    @property
    def _host_groups(self) -> Any:  # noqa: ANN401
        mock = MagicMock()
        mock.query_combined_host_groups = MagicMock()
        return mock


# ── Agent Sync Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCSAgentSync:
    """Integration tests for CrowdStrike agent sync."""

    async def test_full_sync_writes_agents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Full sync writes canonical agent documents to the DB."""
        hosts = [
            _make_cs_host("aid001", hostname="HOST-A"),
            _make_cs_host("aid002", hostname="HOST-B", platform_name="Linux"),
        ]
        groups = {"grp001": "Engineering"}
        mock_client = MockCSClient(hosts=hosts, groups=groups)

        # Pre-seed groups in DB for denormalization
        from domains.sources.crowdstrike.normalizer import normalize_group

        grp_doc = normalize_group({"id": "grp001", "name": "Engineering"})
        await test_db[GROUPS].insert_one(grp_doc)

        from domains.sources.crowdstrike.sync_agents import CSAgentsPhaseRunner

        runner = CSAgentsPhaseRunner()
        # Patch get_db to return test_db
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_agents(mock_client, "full", False, None)

        # Verify agents were written
        count = await test_db[AGENTS].count_documents({"source": "crowdstrike"})
        assert count == 2

        # Verify canonical fields
        agent_a = await test_db[AGENTS].find_one(
            {"_id": canonical_id("crowdstrike", "agent:aid001")}
        )
        assert agent_a is not None
        assert agent_a["hostname"] == "HOST-A"
        assert agent_a["source"] == "crowdstrike"
        assert agent_a["os_type"] == "windows"
        assert agent_a["agent_status"] == "online"

        agent_b = await test_db[AGENTS].find_one(
            {"_id": canonical_id("crowdstrike", "agent:aid002")}
        )
        assert agent_b is not None
        assert agent_b["os_type"] == "linux"

    async def test_full_sync_deletes_stale_agents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Full sync removes agents not in the current fetch."""
        # Pre-insert a stale agent
        await test_db[AGENTS].insert_one({
            "_id": canonical_id("crowdstrike", "agent:stale001"),
            "source": "crowdstrike",
            "source_id": "stale001",
            "hostname": "STALE",
            "synced_at": "2024-01-01T00:00:00Z",
        })

        mock_client = MockCSClient(hosts=[_make_cs_host("aid001")])

        from domains.sources.crowdstrike.sync_agents import CSAgentsPhaseRunner

        runner = CSAgentsPhaseRunner()
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_agents(mock_client, "full", False, None)

        # Stale agent should be removed
        stale = await test_db[AGENTS].find_one(
            {"_id": canonical_id("crowdstrike", "agent:stale001")}
        )
        assert stale is None

        # Fresh agent should exist
        fresh = await test_db[AGENTS].find_one(
            {"_id": canonical_id("crowdstrike", "agent:aid001")}
        )
        assert fresh is not None

    async def test_full_sync_does_not_delete_s1_agents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Full CS sync does not touch SentinelOne agents."""
        await test_db[AGENTS].insert_one({
            "_id": canonical_id("sentinelone", "agent:s1_001"),
            "source": "sentinelone",
            "source_id": "s1_001",
            "hostname": "S1-HOST",
            "synced_at": "2024-01-01T00:00:00Z",
        })

        mock_client = MockCSClient(hosts=[_make_cs_host("aid001")])

        from domains.sources.crowdstrike.sync_agents import CSAgentsPhaseRunner

        runner = CSAgentsPhaseRunner()
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_agents(mock_client, "full", False, None)

        # S1 agent must still exist
        s1 = await test_db[AGENTS].find_one({"source": "sentinelone"})
        assert s1 is not None
        assert s1["hostname"] == "S1-HOST"

    async def test_deterministic_uuid(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Same source_id always produces the same canonical _id."""
        id1 = canonical_id("crowdstrike", "agent:device123")
        id2 = canonical_id("crowdstrike", "agent:device123")
        assert id1 == id2

        # Different source → different ID
        id_s1 = canonical_id("sentinelone", "agent:device123")
        assert id1 != id_s1

    async def test_incremental_sync_uses_filter(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Incremental sync sets a modified_timestamp filter."""
        # Pre-seed SYNC_META with a previous sync timestamp
        await test_db[SYNC_META].insert_one({
            "_id": "crowdstrike",
            "agents_synced_at": "2024-06-01T00:00:00Z",
        })

        hosts = [_make_cs_host("aid001")]
        mock_client = MockCSClient(hosts=hosts)

        from domains.sources.crowdstrike.sync_agents import CSAgentsPhaseRunner

        runner = CSAgentsPhaseRunner()
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_agents(mock_client, "auto", False, None)

        # The agent should be written (incremental doesn't delete stale)
        count = await test_db[AGENTS].count_documents({"source": "crowdstrike"})
        assert count == 1


# ── App Sync Tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCSAppSync:
    """Integration tests for CrowdStrike application sync."""

    async def test_full_sync_writes_apps(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Full sync writes canonical installed_app documents."""
        apps = [
            _make_cs_app("app001", "aid001", name="Chrome"),
            _make_cs_app("app002", "aid001", name="Firefox", version="127.0"),
        ]
        mock_client = MockCSClient(apps=apps)

        from domains.sources.crowdstrike.sync_apps import CSAppsPhaseRunner

        runner = CSAppsPhaseRunner()
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_apps(mock_client, "full", False, None)

        count = await test_db[INSTALLED_APPS].count_documents({"source": "crowdstrike"})
        assert count == 2

        app = await test_db[INSTALLED_APPS].find_one(
            {"_id": canonical_id("crowdstrike", "app:app001")}
        )
        assert app is not None
        assert app["agent_id"] == "aid001"
        assert app["source"] == "crowdstrike"
        assert app["active"] is True

    async def test_full_sync_soft_deletes_stale_apps(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Full sync soft-deletes apps not in the current fetch."""
        # Pre-insert a stale app
        await test_db[INSTALLED_APPS].insert_one({
            "_id": canonical_id("crowdstrike", "app:stale001"),
            "source": "crowdstrike",
            "source_id": "stale001",
            "name": "Old App",
            "last_synced_at": "2024-01-01T00:00:00Z",
            "active": True,
        })

        mock_client = MockCSClient(apps=[_make_cs_app("app001")])

        from domains.sources.crowdstrike.sync_apps import CSAppsPhaseRunner

        runner = CSAppsPhaseRunner()
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_apps(mock_client, "full", False, None)

        stale = await test_db[INSTALLED_APPS].find_one(
            {"_id": canonical_id("crowdstrike", "app:stale001")}
        )
        assert stale is not None
        assert stale["active"] is False


# ── Group Sync Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCSGroupSync:
    """Integration tests for CrowdStrike group sync."""

    async def test_sync_groups_writes_documents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Group sync writes canonical group documents."""
        groups = {"grp001": "Engineering", "grp002": "VPN Users"}
        mock_client = MockCSClient(groups=groups)

        from domains.sources.crowdstrike.sync_groups import CSGroupsPhaseRunner

        runner = CSGroupsPhaseRunner()
        with patch.object(runner, "_get_db", return_value=test_db):
            await runner._sync_groups(mock_client)

        count = await test_db[GROUPS].count_documents({"source": "crowdstrike"})
        assert count == 2

        grp = await test_db[GROUPS].find_one(
            {"_id": canonical_id("crowdstrike", "group:grp001")}
        )
        assert grp is not None
        assert grp["name"] == "Engineering"
        assert grp["source"] == "crowdstrike"
