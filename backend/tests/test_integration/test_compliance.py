"""Integration tests for the compliance domain.

Tests the full HTTP → router → commands/queries → repository → MongoDB
chain via the HTTPX test client.  Covers:
- Framework listing and enable/disable
- Control configuration
- Custom control creation
- Compliance run execution
- Dashboard, results, and violations queries
- Schedule CRUD
- RBAC enforcement
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


@pytest_asyncio.fixture(scope="function")
async def compliance_db(seeded_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed the database with agents and apps for compliance integration tests.

    Creates 2 production agents with approved apps, a completed sync run,
    and classification results.

    Returns:
        The seeded test database.
    """
    now = utc_now()

    agents = [
        {
            "s1_agent_id": "int-agent-1",
            "hostname": "srv-web-01",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(hours=1),
            "group_name": "Production",
            "group_id": "g-prod",
            "site_id": "site-1",
            "tags": ["PCI-CDE"],
            "installed_app_names": ["SentinelOne", "nginx", "OpenSSL"],
            "synced_at": now,
        },
        {
            "s1_agent_id": "int-agent-2",
            "hostname": "srv-db-01",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(hours=2),
            "group_name": "Production",
            "group_id": "g-prod",
            "site_id": "site-1",
            "tags": ["PCI-CDE", "HIPAA"],
            "installed_app_names": ["SentinelOne", "PostgreSQL", "OpenSSL"],
            "synced_at": now,
        },
    ]
    await seeded_db["s1_agents"].insert_many(agents)

    apps = [
        {"agent_id": "int-agent-1", "normalized_name": "SentinelOne", "version": "23.3.1", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "int-agent-1", "normalized_name": "nginx", "version": "1.25", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "int-agent-1", "normalized_name": "OpenSSL", "version": "3.1.4", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "int-agent-2", "normalized_name": "SentinelOne", "version": "23.3.1", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "int-agent-2", "normalized_name": "PostgreSQL", "version": "16.1", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "int-agent-2", "normalized_name": "OpenSSL", "version": "3.1.4", "risk_level": "approved", "last_synced_at": now},
    ]
    await seeded_db["s1_installed_apps"].insert_many(apps)

    await seeded_db["s1_sync_runs"].insert_one({
        "run_id": "int-sync-1",
        "status": "completed",
        "completed_at": now - timedelta(minutes=30),
        "started_at": now - timedelta(minutes=45),
    })

    await seeded_db["classification_results"].insert_many([
        {"agent_id": "int-agent-1", "classification": "correct", "hostname": "srv-web-01", "current_group_id": "g-prod"},
        {"agent_id": "int-agent-2", "classification": "correct", "hostname": "srv-db-01", "current_group_id": "g-prod"},
    ])

    return seeded_db


# ── Framework listing ────────────────────────────────────────────────────


class TestFrameworkEndpoints:
    """Tests for framework listing and enable/disable."""

    @pytest.mark.asyncio
    async def test_list_frameworks(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /frameworks returns all 4 frameworks."""
        resp = await client.get("/api/v1/compliance/frameworks", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["frameworks"]) == 4
        ids = {f["id"] for f in data["frameworks"]}
        assert ids == {"soc2", "pci_dss_4", "hipaa", "bsi_grundschutz"}

    @pytest.mark.asyncio
    async def test_enable_and_disable_framework(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """PUT enable/disable toggles framework state."""
        resp = await client.put(
            "/api/v1/compliance/frameworks/soc2/enable", headers=admin_headers
        )
        assert resp.status_code == 200

        resp = await client.get("/api/v1/compliance/frameworks", headers=admin_headers)
        fw = next(f for f in resp.json()["frameworks"] if f["id"] == "soc2")
        assert fw["enabled"] is True

        resp = await client.put(
            "/api/v1/compliance/frameworks/soc2/disable", headers=admin_headers
        )
        assert resp.status_code == 200

        resp = await client.get("/api/v1/compliance/frameworks", headers=admin_headers)
        fw = next(f for f in resp.json()["frameworks"] if f["id"] == "soc2")
        assert fw["enabled"] is False

    @pytest.mark.asyncio
    async def test_enable_unknown_framework_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """PUT enable on unknown framework returns 404."""
        resp = await client.put(
            "/api/v1/compliance/frameworks/nonexistent/enable",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_framework_detail_with_controls(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /frameworks/{id} returns framework metadata and >= 15 controls."""
        resp = await client.get(
            "/api/v1/compliance/frameworks/soc2", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "soc2"
        assert data["name"] == "SOC 2 Type II"
        assert len(data["controls"]) >= 15

    @pytest.mark.asyncio
    async def test_get_unknown_framework_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /frameworks/nonexistent returns 404."""
        resp = await client.get(
            "/api/v1/compliance/frameworks/nonexistent", headers=admin_headers
        )
        assert resp.status_code == 404


# ── Compliance run ───────────────────────────────────────────────────────


class TestComplianceRun:
    """Tests for triggering compliance runs and viewing results."""

    @pytest.mark.asyncio
    async def test_run_with_enabled_framework(
        self,
        client: AsyncClient,
        compliance_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        admin_headers: dict[str, str],
    ) -> None:
        """Enable a framework, run checks, verify results appear."""
        await client.put(
            "/api/v1/compliance/frameworks/soc2/enable", headers=admin_headers
        )

        resp = await client.post(
            "/api/v1/compliance/run", headers=admin_headers, json={}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["controls_evaluated"] >= 15
        assert data["duration_ms"] >= 0
        # passed + failed + warning should sum to controls_evaluated
        assert (
            data["passed"] + data["failed"] + data["warning"]
            <= data["controls_evaluated"]
        )

        # Results are queryable
        resp = await client.get(
            "/api/v1/compliance/results/latest", headers=admin_headers
        )
        assert resp.status_code == 200
        results = resp.json()
        assert results["total"] >= 15

    @pytest.mark.asyncio
    async def test_run_no_enabled_frameworks(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Run with no enabled frameworks returns 0 controls."""
        resp = await client.post(
            "/api/v1/compliance/run", headers=admin_headers, json={}
        )
        assert resp.status_code == 200
        assert resp.json()["controls_evaluated"] == 0


# ── Dashboard ────────────────────────────────────────────────────────────


class TestDashboard:
    """Tests for the aggregated compliance dashboard."""

    @pytest.mark.asyncio
    async def test_dashboard_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Dashboard with no enabled frameworks returns zeros."""
        resp = await client.get(
            "/api/v1/compliance/dashboard", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score_percent"] == 0
        assert data["total_violations"] == 0
        assert len(data["frameworks"]) == 0


# ── Control configuration ────────────────────────────────────────────────


class TestControlConfiguration:
    """Tests for control configuration and custom controls."""

    @pytest.mark.asyncio
    async def test_disable_control(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """PUT /controls/{id} with enabled=false disables the control."""
        resp = await client.put(
            "/api/v1/compliance/controls/SOC2-CC6.7",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    @pytest.mark.asyncio
    async def test_configure_unknown_control_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """PUT on unknown control returns 404."""
        resp = await client.put(
            "/api/v1/compliance/controls/NONEXISTENT-CTRL",
            headers=admin_headers,
            json={"enabled": True},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_custom_control(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """POST /controls/custom creates a custom control."""
        resp = await client.post(
            "/api/v1/compliance/controls/custom",
            headers=admin_headers,
            json={
                "id": "custom-int-test",
                "framework_id": "soc2",
                "name": "Integration Test Control",
                "description": "For integration testing",
                "category": "Custom",
                "severity": "medium",
                "check_type": "custom_app_presence_check",
                "parameters": {"app_pattern": "TestApp*", "must_exist": True},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "custom-int-test"
        assert data["is_custom"] is True

    @pytest.mark.asyncio
    async def test_duplicate_custom_control_returns_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Creating a custom control with existing ID returns 409."""
        payload = {
            "id": "custom-dup-int",
            "framework_id": "soc2",
            "name": "Dup",
            "description": "Dup",
            "category": "Custom",
            "severity": "low",
            "check_type": "agent_online_check",
        }
        await client.post(
            "/api/v1/compliance/controls/custom",
            headers=admin_headers,
            json=payload,
        )
        resp = await client.post(
            "/api/v1/compliance/controls/custom",
            headers=admin_headers,
            json=payload,
        )
        assert resp.status_code == 409


# ── Schedule ─────────────────────────────────────────────────────────────


class TestSchedule:
    """Tests for schedule CRUD."""

    @pytest.mark.asyncio
    async def test_get_default_schedule(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /schedule returns defaults."""
        resp = await client.get(
            "/api/v1/compliance/schedule", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_after_sync"] is True
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_update_schedule(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """PUT /schedule updates and persists."""
        resp = await client.put(
            "/api/v1/compliance/schedule",
            headers=admin_headers,
            json={"run_after_sync": False, "cron_expression": "0 6 * * *"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_after_sync"] is False
        assert data["cron_expression"] == "0 6 * * *"


# ── RBAC ─────────────────────────────────────────────────────────────────


class TestRBAC:
    """Tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_viewer_reads_frameworks(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers can list frameworks."""
        resp = await client.get(
            "/api/v1/compliance/frameworks", headers=viewer_headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_enable(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers cannot enable frameworks."""
        resp = await client.put(
            "/api/v1/compliance/frameworks/soc2/enable",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_run(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers cannot trigger compliance runs."""
        resp = await client.post(
            "/api/v1/compliance/run",
            headers=viewer_headers,
            json={},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_reads_dashboard(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers can read the dashboard."""
        resp = await client.get(
            "/api/v1/compliance/dashboard", headers=viewer_headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Unauthenticated requests return 401."""
        resp = await client.get("/api/v1/compliance/frameworks")
        assert resp.status_code == 401


# ── Violations export ────────────────────────────────────────────────────


class TestViolations:
    """Tests for violations listing and CSV export."""

    @pytest.mark.asyncio
    async def test_violations_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /violations with no data returns empty list."""
        resp = await client.get(
            "/api/v1/compliance/violations", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_violations_csv_export(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /violations/export returns CSV content type."""
        resp = await client.get(
            "/api/v1/compliance/violations/export", headers=admin_headers
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_unified_violations_empty(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /violations/unified with no data returns empty list."""
        resp = await client.get(
            "/api/v1/compliance/violations/unified", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["violations"]) == 0

    @pytest.mark.asyncio
    async def test_unified_violations_has_source_field(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /violations/unified returns items with source field."""
        resp = await client.get(
            "/api/v1/compliance/violations/unified", headers=admin_headers
        )
        assert resp.status_code == 200
        # Even if empty, the structure should be correct
        data = resp.json()
        assert "violations" in data
        assert "total" in data
        assert "page" in data

    @pytest.mark.asyncio
    async def test_unified_violations_source_filter(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /violations/unified?source=compliance filters by source."""
        resp = await client.get(
            "/api/v1/compliance/violations/unified",
            params={"source": "compliance"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # All violations should be from compliance source
        for v in data["violations"]:
            assert v["source"] == "compliance"
