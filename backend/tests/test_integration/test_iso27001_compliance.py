"""Integration tests for the ISO 27001 compliance framework.

Tests the HTTP API for ISO 27001 framework operations including
enable/disable, control listing, disable_reason (Statement of
Applicability), and compliance run execution.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


class _AdminClient:
    """Thin wrapper that injects admin Authorization headers into all requests."""

    def __init__(self, client: AsyncClient, headers: dict[str, str]) -> None:
        self._client = client
        self._headers = headers

    async def get(self, url: str, **kwargs: object) -> object:
        kwargs.setdefault("headers", self._headers)  # type: ignore[arg-type]
        return await self._client.get(url, **kwargs)  # type: ignore[arg-type]

    async def put(self, url: str, **kwargs: object) -> object:
        kwargs.setdefault("headers", self._headers)  # type: ignore[arg-type]
        return await self._client.put(url, **kwargs)  # type: ignore[arg-type]

    async def post(self, url: str, **kwargs: object) -> object:
        kwargs.setdefault("headers", self._headers)  # type: ignore[arg-type]
        return await self._client.post(url, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(scope="function")
def admin_client(client: AsyncClient, admin_headers: dict[str, str]) -> _AdminClient:
    """Provide an admin-authenticated HTTP client."""
    return _AdminClient(client, admin_headers)  # type: ignore[return-value]


@pytest_asyncio.fixture(scope="function")
async def iso_db(seeded_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed the database with agents for ISO 27001 integration tests.

    Creates 2 agents with apps and a completed sync run for compliance
    check execution.

    Returns:
        The seeded test database.
    """
    now = utc_now()

    agents = [
        {
            "source": "sentinelone",
            "source_id": "iso-agent-1",
            "hostname": "ws-iso-01",
            "agent_version": "23.3.1.500",
            "last_active": now,
            "group_name": "Production",
            "group_id": "g-prod",
            "site_id": "site-1",
            "tags": [],
            "installed_app_names": ["SentinelOne", "Chrome"],
            "synced_at": now,
        },
        {
            "source": "sentinelone",
            "source_id": "iso-agent-2",
            "hostname": "ws-iso-02",
            "agent_version": "23.3.1.500",
            "last_active": now,
            "group_name": "Development",
            "group_id": "g-dev",
            "site_id": "site-1",
            "tags": [],
            "installed_app_names": ["SentinelOne", "VSCode"],
            "synced_at": now,
        },
    ]
    await seeded_db["agents"].insert_many(agents)

    await seeded_db["sync_runs"].insert_one(
        {
            "status": "completed",
            "completed_at": now,
            "started_at": now,
            "phases": {},
        }
    )

    # Classification results
    for agent in agents:
        await seeded_db["classification_results"].insert_one(
            {
                "agent_id": agent["source_id"],
                "computed_at": now,
                "results": [],
            }
        )

    return seeded_db


class TestIso27001FrameworkApi:
    """Tests for ISO 27001 framework listing and enable/disable via API."""

    @pytest.mark.asyncio
    async def test_iso27001_appears_in_framework_list(self, admin_client: AsyncClient) -> None:
        """ISO 27001 appears in the framework listing with correct metadata."""
        resp = await admin_client.get("/api/v1/compliance/frameworks")
        assert resp.status_code == 200
        frameworks = resp.json()["frameworks"]
        iso = next((f for f in frameworks if f["id"] == "iso27001"), None)
        assert iso is not None
        assert iso["name"] == "ISO/IEC 27001:2022"
        assert iso["total_controls"] == 16
        assert "certification" in iso["disclaimer"].lower()

    @pytest.mark.asyncio
    async def test_enable_iso27001(self, admin_client: AsyncClient) -> None:
        """Enabling ISO 27001 succeeds and is persisted."""
        resp = await admin_client.put("/api/v1/compliance/frameworks/iso27001/enable")
        assert resp.status_code == 200

        resp = await admin_client.get("/api/v1/compliance/frameworks")
        iso = next(f for f in resp.json()["frameworks"] if f["id"] == "iso27001")
        assert iso["enabled"] is True

    @pytest.mark.asyncio
    async def test_disable_iso27001(self, admin_client: AsyncClient) -> None:
        """Disabling ISO 27001 succeeds."""
        await admin_client.put("/api/v1/compliance/frameworks/iso27001/enable")
        resp = await admin_client.put("/api/v1/compliance/frameworks/iso27001/disable")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_iso27001_detail_returns_16_controls(self, admin_client: AsyncClient) -> None:
        """Framework detail returns all 16 ISO 27001 controls."""
        resp = await admin_client.get("/api/v1/compliance/frameworks/iso27001")
        assert resp.status_code == 200
        detail = resp.json()
        assert len(detail["controls"]) == 16
        assert detail["version"] == "2022"


class TestDisableReason:
    """Tests for the disable_reason field (Statement of Applicability)."""

    @pytest.mark.asyncio
    async def test_disable_control_with_reason(self, admin_client: AsyncClient) -> None:
        """Disabling a control with a reason persists the justification."""
        resp = await admin_client.put(
            "/api/v1/compliance/controls/ISO-A.5.10",
            json={
                "enabled": False,
                "disable_reason": "No endpoints process restricted data",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert resp.json()["disable_reason"] == "No endpoints process restricted data"

    @pytest.mark.asyncio
    async def test_disable_reason_persisted_in_detail(self, admin_client: AsyncClient) -> None:
        """Disable reason appears in the framework detail response."""
        await admin_client.put(
            "/api/v1/compliance/controls/ISO-A.5.10",
            json={
                "enabled": False,
                "disable_reason": "SoA exclusion: no applicable data types",
            },
        )
        resp = await admin_client.get("/api/v1/compliance/frameworks/iso27001")
        controls = resp.json()["controls"]
        ctrl = next(c for c in controls if c["id"] == "ISO-A.5.10")
        assert ctrl["enabled"] is False
        assert ctrl["disable_reason"] == "SoA exclusion: no applicable data types"

    @pytest.mark.asyncio
    async def test_re_enable_clears_reason(self, admin_client: AsyncClient) -> None:
        """Re-enabling a control clears the disable_reason."""
        await admin_client.put(
            "/api/v1/compliance/controls/ISO-A.5.10",
            json={"enabled": False, "disable_reason": "Temporary exclusion"},
        )
        resp = await admin_client.put(
            "/api/v1/compliance/controls/ISO-A.5.10",
            json={"enabled": True, "disable_reason": None},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
        assert resp.json()["disable_reason"] is None

    @pytest.mark.asyncio
    async def test_disable_without_reason(self, admin_client: AsyncClient) -> None:
        """Disabling without a reason is allowed (reason is optional)."""
        resp = await admin_client.put(
            "/api/v1/compliance/controls/ISO-A.8.1",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert resp.json()["disable_reason"] is None


class TestIso27001ComplianceRun:
    """Tests for ISO 27001 compliance run execution."""

    @pytest.mark.asyncio
    async def test_run_iso27001_returns_results(
        self,
        admin_client: AsyncClient,
        iso_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Running ISO 27001 checks produces results for enabled controls."""
        # Enable the framework
        await admin_client.put("/api/v1/compliance/frameworks/iso27001/enable")

        # Trigger a compliance run
        resp = await admin_client.post(
            "/api/v1/compliance/run",
            json={"framework_id": "iso27001"},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["controls_evaluated"] > 0
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_iso27001_results_appear_in_latest(
        self,
        admin_client: AsyncClient,
        iso_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """After a run, ISO 27001 results appear in the latest results query."""
        await admin_client.put("/api/v1/compliance/frameworks/iso27001/enable")
        await admin_client.post(
            "/api/v1/compliance/run",
            json={"framework_id": "iso27001"},
        )

        resp = await admin_client.get(
            "/api/v1/compliance/results/latest",
            params={"framework_id": "iso27001"},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) > 0
        assert all(r["framework_id"] == "iso27001" for r in results)

    @pytest.mark.asyncio
    async def test_iso27001_appears_in_dashboard(
        self,
        admin_client: AsyncClient,
        iso_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """After a run, ISO 27001 score appears in the dashboard."""
        await admin_client.put("/api/v1/compliance/frameworks/iso27001/enable")
        await admin_client.post(
            "/api/v1/compliance/run",
            json={"framework_id": "iso27001"},
        )

        resp = await admin_client.get("/api/v1/compliance/dashboard")
        assert resp.status_code == 200
        dashboard = resp.json()
        iso_score = next(
            (fw for fw in dashboard["frameworks"] if fw["framework_id"] == "iso27001"),
            None,
        )
        assert iso_score is not None
        assert iso_score["total_controls"] > 0
