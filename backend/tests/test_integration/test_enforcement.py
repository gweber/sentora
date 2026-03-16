"""Integration tests for the enforcement domain.

Tests the full HTTP → router → service → repository → MongoDB chain.
Covers: CRUD, check execution, summary, violations, RBAC.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


@pytest_asyncio.fixture(scope="function")
async def enforcement_seeded(seeded_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed database for enforcement integration tests.

    Creates agents, taxonomy entries, and installed apps.

    Returns:
        The seeded test database.
    """
    now = utc_now()

    agents = [
        {
            "s1_agent_id": "enf-agent-1",
            "hostname": "srv-app-01",
            "group_name": "Production",
            "group_id": "g-prod",
            "site_id": "s1",
            "tags": ["PCI-CDE"],
            "installed_app_names": ["SentinelOne Agent", "nginx"],
            "synced_at": now,
            "last_active": now,
            "agent_version": "23.3.1",
        },
        {
            "s1_agent_id": "enf-agent-2",
            "hostname": "srv-db-01",
            "group_name": "Production",
            "group_id": "g-prod",
            "site_id": "s1",
            "tags": ["PCI-CDE"],
            "installed_app_names": ["SentinelOne Agent", "PostgreSQL"],
            "synced_at": now,
            "last_active": now,
            "agent_version": "23.3.1",
        },
        {
            "s1_agent_id": "enf-agent-3",
            "hostname": "ws-dev-01",
            "group_name": "Development",
            "group_id": "g-dev",
            "site_id": "s1",
            "tags": [],
            "installed_app_names": ["uTorrent", "VLC", "VSCode"],
            "synced_at": now,
            "last_active": now,
            "agent_version": "23.3.1",
        },
    ]
    await seeded_db["s1_agents"].insert_many(agents)

    await seeded_db["taxonomy_categories"].insert_many(
        [
            {
                "key": "required_edr",
                "display": "Required / EDR",
                "created_at": now,
                "updated_at": now,
            },
            {
                "key": "forbidden_p2p",
                "display": "Forbidden / P2P",
                "created_at": now,
                "updated_at": now,
            },
        ]
    )

    await seeded_db["taxonomy_entries"].insert_many(
        [
            {
                "name": "SentinelOne",
                "patterns": ["SentinelOne*"],
                "category": "required_edr",
                "category_display": "Required / EDR",
            },
            {
                "name": "uTorrent",
                "patterns": ["*torrent*", "*Torrent*"],
                "category": "forbidden_p2p",
                "category_display": "Forbidden / P2P",
            },
        ]
    )

    return seeded_db


@pytest.mark.usefixtures("enforcement_seeded")
class TestRuleCRUD:
    """Tests for enforcement rule CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_rule(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """POST /rules creates a new rule and returns 201."""
        resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "EDR Required",
                "taxonomy_category_id": "required_edr",
                "type": "required",
                "severity": "critical",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "EDR Required"
        assert data["type"] == "required"
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_rules(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """GET /rules returns all rules."""
        # Create a rule first
        await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "Test Rule",
                "taxonomy_category_id": "required_edr",
                "type": "required",
                "severity": "high",
            },
        )
        resp = await client.get("/api/v1/enforcement/rules", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_rule(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """GET /rules/{id} returns rule detail."""
        create_resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "Get Test",
                "taxonomy_category_id": "required_edr",
                "type": "forbidden",
                "severity": "medium",
            },
        )
        rule_id = create_resp.json()["id"]
        resp = await client.get(f"/api/v1/enforcement/rules/{rule_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Test"

    @pytest.mark.asyncio
    async def test_update_rule(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """PUT /rules/{id} updates fields."""
        create_resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "Update Test",
                "taxonomy_category_id": "required_edr",
                "type": "required",
                "severity": "low",
            },
        )
        rule_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/enforcement/rules/{rule_id}",
            headers=admin_headers,
            json={"name": "Updated Name", "severity": "critical"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_rule(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """DELETE /rules/{id} removes the rule."""
        create_resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "Delete Test",
                "taxonomy_category_id": "forbidden_p2p",
                "type": "forbidden",
                "severity": "high",
            },
        )
        rule_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/enforcement/rules/{rule_id}", headers=admin_headers)
        assert resp.status_code == 200

        resp = await client.get(f"/api/v1/enforcement/rules/{rule_id}", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_toggle_rule(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """PUT /rules/{id}/toggle flips enabled state."""
        create_resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "Toggle Test",
                "taxonomy_category_id": "required_edr",
                "type": "required",
                "severity": "high",
            },
        )
        rule_id = create_resp.json()["id"]
        assert create_resp.json()["enabled"] is True

        resp = await client.put(
            f"/api/v1/enforcement/rules/{rule_id}/toggle",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False


class TestCheckExecution:
    """Tests for enforcement check execution."""

    @pytest.mark.asyncio
    async def test_run_all_checks(
        self,
        client: AsyncClient,
        enforcement_seeded: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        admin_headers: dict[str, str],
    ) -> None:
        """Create rules, run checks, verify results stored."""
        # Create a required-EDR rule
        await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "EDR Required",
                "taxonomy_category_id": "required_edr",
                "type": "required",
                "severity": "critical",
            },
        )

        resp = await client.post("/api/v1/enforcement/check", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rules_evaluated"] == 1
        # Agent-3 has no EDR → 1 failure
        assert data["failed"] == 1
        assert data["total_violations"] >= 1

        # Results are queryable
        resp = await client.get("/api/v1/enforcement/results/latest", headers=admin_headers)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_run_single_rule(
        self,
        client: AsyncClient,
        enforcement_seeded: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        admin_headers: dict[str, str],
    ) -> None:
        """Run a single rule check."""
        create_resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=admin_headers,
            json={
                "name": "No P2P",
                "taxonomy_category_id": "forbidden_p2p",
                "type": "forbidden",
                "severity": "high",
            },
        )
        rule_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/enforcement/check/{rule_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rules_evaluated"] == 1
        assert data["failed"] == 1  # agent-3 has uTorrent


class TestSummaryAndViolations:
    """Tests for summary and violations endpoints."""

    @pytest.mark.asyncio
    async def test_summary_empty(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        """Summary with no rules returns zeros."""
        resp = await client.get("/api/v1/enforcement/summary", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rules"] == 0
        assert data["total_violations"] == 0

    @pytest.mark.asyncio
    async def test_violations_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Violations with no data returns empty list."""
        resp = await client.get("/api/v1/enforcement/violations", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestRBAC:
    """Tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_viewer_can_list_rules(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers can list rules."""
        resp = await client.get("/api/v1/enforcement/rules", headers=viewer_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_rule(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers cannot create rules."""
        resp = await client.post(
            "/api/v1/enforcement/rules",
            headers=viewer_headers,
            json={
                "name": "Blocked",
                "taxonomy_category_id": "test",
                "type": "required",
                "severity": "low",
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_run_checks(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers cannot trigger checks."""
        resp = await client.post("/api/v1/enforcement/check", headers=viewer_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Unauthenticated requests return 401."""
        resp = await client.get("/api/v1/enforcement/rules")
        assert resp.status_code == 401
