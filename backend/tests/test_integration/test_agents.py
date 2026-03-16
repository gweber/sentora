"""Integration tests for the agents and groups API endpoints.

These endpoints are read-only — they serve data from the s1_agents,
s1_installed_apps, and classification_results collections populated by sync
and classification runs.  Tests cover both populated and empty states.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

_NOW = "2025-01-01T00:00:00"

_AGENTS = [
    {
        "s1_agent_id": "agent_001",
        "hostname": "pc-scada-01",
        "os_type": "windows",
        "os_version": "10",
        "group_id": "grp_scada",
        "group_name": "SCADA Floor",
        "network_status": "connected",
        "last_active": _NOW,
        "machine_type": "desktop",
        "domain": "corp.local",
        "ip_addresses": ["10.0.1.1"],
        "tags": ["production"],
        "synced_at": _NOW,
    },
    {
        "s1_agent_id": "agent_002",
        "hostname": "srv-lab-01",
        "os_type": "linux",
        "os_version": "Ubuntu 22.04",
        "group_id": "grp_lab",
        "group_name": "Lab Systems",
        "network_status": "disconnected",
        "last_active": _NOW,
        "machine_type": "server",
        "domain": None,
        "ip_addresses": ["10.0.2.1"],
        "tags": [],
        "synced_at": _NOW,
    },
]

_APPS = [
    {
        "agent_id": "agent_001",
        "name": "Siemens WinCC Runtime",
        "normalized_name": "siemens wincc runtime",
        "version": "8.0",
        "publisher": "Siemens AG",
        "size": 524288,
        "installed_date": _NOW,
        "synced_at": _NOW,
    },
    {
        "agent_id": "agent_001",
        "name": "Microsoft .NET Framework",
        "normalized_name": "microsoft .net framework",
        "version": "4.8",
        "publisher": "Microsoft Corporation",
        "size": 102400,
        "installed_date": _NOW,
        "synced_at": _NOW,
    },
]

_GROUPS = [
    {
        "s1_group_id": "grp_scada",
        "name": "SCADA Floor",
        "description": "SCADA systems",
        "type": "static",
        "is_default": False,
        "filter_name": None,
        "site_id": "site_001",
        "site_name": "HQ",
        "agent_count": 1,
        "os_types": ["windows"],
        "created_at": _NOW,
        "updated_at": _NOW,
    },
    {
        "s1_group_id": "grp_lab",
        "name": "Lab Systems",
        "description": "Lab environment",
        "type": "static",
        "is_default": False,
        "filter_name": None,
        "site_id": "site_001",
        "site_name": "HQ",
        "agent_count": 1,
        "os_types": ["linux"],
        "created_at": _NOW,
        "updated_at": _NOW,
    },
]


@pytest_asyncio.fixture
async def agents_db(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed s1_agents, s1_installed_apps, and s1_groups into the test database."""
    await test_db["s1_agents"].insert_many(_AGENTS)
    await test_db["s1_installed_apps"].insert_many(_APPS)
    await test_db["s1_groups"].insert_many(_GROUPS)
    return test_db


class TestListAgents:
    """Tests for GET /api/v1/agents/."""

    async def test_empty_collection_returns_empty_list(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Before any sync, the agents list is empty but does not error."""
        response = await client.get("/api/v1/agents/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["agents"] == []
        assert data["total"] == 0

    async def test_returns_seeded_agents(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """After seeding, both agents appear in the list."""
        response = await client.get("/api/v1/agents/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        hostnames = {a["hostname"] for a in data["agents"]}
        assert "pc-scada-01" in hostnames
        assert "srv-lab-01" in hostnames

    async def test_filter_by_group_id(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """group_id filter returns only agents in that group."""
        response = await client.get(
            "/api/v1/agents/", params={"group_id": "grp_scada"}, headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["agents"][0]["hostname"] == "pc-scada-01"

    async def test_hostname_search(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """search param filters agents by hostname substring."""
        response = await client.get(
            "/api/v1/agents/", params={"search": "srv"}, headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["agents"][0]["hostname"] == "srv-lab-01"

    async def test_pagination_limit(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """limit=1 returns exactly one agent."""
        response = await client.get("/api/v1/agents/", params={"limit": 1}, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 1
        assert data["total"] == 2

    async def test_agent_has_required_fields(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Every agent must have the required shape fields."""
        response = await client.get("/api/v1/agents/", headers=admin_headers)
        assert response.status_code == 200
        for agent in response.json()["agents"]:
            assert "s1_agent_id" in agent
            assert "hostname" in agent
            assert "group_id" in agent
            assert "group_name" in agent
            assert "os_type" in agent
            assert "network_status" in agent


class TestGetAgentDetail:
    """Tests for GET /api/v1/agents/{agent_id}."""

    async def test_404_for_unknown_agent(self, client: AsyncClient, admin_headers: dict) -> None:
        """Requesting an unknown agent_id returns 404."""
        response = await client.get("/api/v1/agents/nonexistent_agent", headers=admin_headers)
        assert response.status_code == 404

    async def test_returns_agent_with_installed_apps(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Agent detail includes the installed_apps list."""
        response = await client.get("/api/v1/agents/agent_001", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["hostname"] == "pc-scada-01"
        assert "installed_apps" in data
        assert len(data["installed_apps"]) == 2

    async def test_installed_apps_shape(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Each installed app must have name, normalized_name, publisher, version."""
        response = await client.get("/api/v1/agents/agent_001", headers=admin_headers)
        assert response.status_code == 200
        for app in response.json()["installed_apps"]:
            assert "name" in app
            assert "normalized_name" in app

    async def test_agent_with_no_apps(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Agent with no installed apps returns empty installed_apps list."""
        response = await client.get("/api/v1/agents/agent_002", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["installed_apps"] == []

    async def test_classification_null_before_run(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """classification field is null when no classification has been run."""
        response = await client.get("/api/v1/agents/agent_001", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["classification"] is None


class TestGetAgentApps:
    """Tests for GET /api/v1/agents/{agent_id}/apps."""

    async def test_404_for_unknown_agent(self, client: AsyncClient, admin_headers: dict) -> None:
        """Returns 404 for an agent that doesn't exist."""
        response = await client.get("/api/v1/agents/nonexistent/apps", headers=admin_headers)
        assert response.status_code == 404

    async def test_returns_apps(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Returns all installed apps for agent_001."""
        response = await client.get("/api/v1/agents/agent_001/apps", headers=admin_headers)
        assert response.status_code == 200
        apps = response.json()
        assert len(apps) == 2
        names = {a["normalized_name"] for a in apps}
        assert "siemens wincc runtime" in names


class TestListGroups:
    """Tests for GET /api/v1/groups/."""

    async def test_empty_collection_returns_empty_groups(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Before any sync, groups list is empty."""
        response = await client.get("/api/v1/groups/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["groups"] == []
        assert data["total"] == 0

    async def test_returns_distinct_groups(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """After seeding, two distinct groups are returned."""
        response = await client.get("/api/v1/groups/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        group_names = {g["group_name"] for g in data["groups"]}
        assert "SCADA Floor" in group_names
        assert "Lab Systems" in group_names

    async def test_group_has_agent_count(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Each group includes an agent_count field."""
        response = await client.get("/api/v1/groups/", headers=admin_headers)
        assert response.status_code == 200
        for group in response.json()["groups"]:
            assert "agent_count" in group
            assert group["agent_count"] >= 1

    async def test_group_has_fingerprint_flag(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Each group includes a has_fingerprint boolean field."""
        response = await client.get("/api/v1/groups/", headers=admin_headers)
        assert response.status_code == 200
        for group in response.json()["groups"]:
            assert "has_fingerprint" in group
            assert isinstance(group["has_fingerprint"], bool)

    async def test_has_fingerprint_true_when_exists(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """has_fingerprint is True for groups that have a fingerprint document."""
        from bson import ObjectId

        await agents_db["fingerprints"].insert_one(
            {
                "_id": str(ObjectId()),
                "group_id": "grp_scada",
                "group_name": "SCADA Floor",
                "markers": [],
                "created_at": _NOW,
                "updated_at": _NOW,
                "created_by": "user",
            }
        )
        response = await client.get("/api/v1/groups/", headers=admin_headers)
        assert response.status_code == 200
        groups = {g["group_id"]: g for g in response.json()["groups"]}
        assert groups["grp_scada"]["has_fingerprint"] is True
        assert groups["grp_lab"]["has_fingerprint"] is False


class TestListApps:
    """Tests for GET /api/v1/apps/."""

    async def test_empty_collection_returns_empty_list(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Before any sync, the apps list is empty but does not error."""
        response = await client.get("/api/v1/apps/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["apps"] == []
        assert data["total"] == 0

    async def test_returns_distinct_apps(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """After seeding, distinct apps appear with agent counts."""
        response = await client.get("/api/v1/apps/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {a["normalized_name"] for a in data["apps"]}
        assert "siemens wincc runtime" in names
        assert "microsoft .net framework" in names

    async def test_search_filter(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """q parameter filters apps by name."""
        response = await client.get("/api/v1/apps/", params={"q": "siemens"}, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["apps"][0]["normalized_name"] == "siemens wincc runtime"

    async def test_sort_by_name(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """sort=name returns apps sorted alphabetically."""
        response = await client.get(
            "/api/v1/apps/", params={"sort": "name", "order": "asc"}, headers=admin_headers
        )
        assert response.status_code == 200
        names = [a["normalized_name"] for a in response.json()["apps"]]
        assert names == sorted(names)

    async def test_pagination(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """limit=1 returns one app, total still reflects all."""
        response = await client.get("/api/v1/apps/", params={"limit": 1}, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["apps"]) == 1
        assert data["total"] == 2

    async def test_app_has_required_fields(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Each app has the expected shape."""
        response = await client.get("/api/v1/apps/", headers=admin_headers)
        assert response.status_code == 200
        for app in response.json()["apps"]:
            assert "normalized_name" in app
            assert "display_name" in app
            assert "agent_count" in app
            assert isinstance(app["agent_count"], int)


class TestGetAppDetail:
    """Tests for GET /api/v1/apps/{normalized_name}."""

    async def test_404_for_unknown_app(self, client: AsyncClient, admin_headers: dict) -> None:
        """Returns 404 for an app that doesn't exist."""
        response = await client.get("/api/v1/apps/nonexistent-app-xyz", headers=admin_headers)
        assert response.status_code == 404

    async def test_returns_detail(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Returns detail for a known app."""
        response = await client.get("/api/v1/apps/siemens%20wincc%20runtime", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["normalized_name"] == "siemens wincc runtime"
        assert data["agent_count"] == 1
        assert len(data["versions"]) >= 1
        assert len(data["agents"]) == 1
        assert data["agents"][0]["hostname"] == "pc-scada-01"

    async def test_detail_has_required_fields(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Detail response has all expected top-level fields."""
        response = await client.get("/api/v1/apps/siemens%20wincc%20runtime", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        for field in (
            "normalized_name",
            "display_name",
            "agent_count",
            "group_count",
            "site_count",
            "versions",
            "agents",
        ):
            assert field in data


class TestRebuildAppCache:
    """Tests for POST /api/v1/apps/rebuild-cache."""

    async def test_rebuild_empty(self, client: AsyncClient, admin_headers: dict) -> None:
        """Rebuild on empty DB returns 0 apps."""
        response = await client.post("/api/v1/apps/rebuild-cache", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["apps_cached"] == 0

    async def test_rebuild_with_data(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Rebuild with data caches the right count."""
        response = await client.post("/api/v1/apps/rebuild-cache", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["apps_cached"] == 2

        # Verify the cached list endpoint works
        response = await client.get("/api/v1/apps/", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 2


class TestListSites:
    """Tests for GET /api/v1/sites/."""

    async def test_empty_sites(self, client: AsyncClient, admin_headers: dict) -> None:
        response = await client.get("/api/v1/sites/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["sites"] == []
        assert data["total"] == 0

    async def test_returns_seeded_sites(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """After seeding s1_sites, sites list returns the seeded site."""
        await agents_db["s1_sites"].insert_one(
            {
                "s1_site_id": "site_001",
                "name": "HQ",
                "state": "active",
                "site_type": "Paid",
                "account_id": "acc-1",
                "account_name": "Acme",
            }
        )

        response = await client.get("/api/v1/sites/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        site = data["sites"][0]
        assert site["s1_site_id"] == "site_001"
        assert site["name"] == "HQ"

    async def test_sites_include_group_and_agent_counts(
        self, agents_db: AsyncIOMotorDatabase, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Sites response includes aggregated group_count and agent_count."""
        await agents_db["s1_sites"].insert_one(
            {
                "s1_site_id": "site_001",
                "name": "HQ",
                "state": "active",
            }
        )
        # s1_groups already seeded in agents_db with site_id "site_001"
        # s1_agents already seeded with matching group entries

        response = await client.get("/api/v1/sites/", headers=admin_headers)
        assert response.status_code == 200
        site = response.json()["sites"][0]
        assert "group_count" in site
        assert "agent_count" in site
