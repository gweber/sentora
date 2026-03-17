"""Integration tests for NIST CSF 2.0, NIS2, and CIS Controls v8 frameworks.

Tests the HTTP API for framework operations including listing, enable/disable,
control details, and compliance run execution for all three new frameworks.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


class _AdminClient:
    """Thin wrapper that injects admin Authorization headers."""

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
async def frameworks_db(
    seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed the database with agents for new-framework integration tests.

    Creates 2 agents with apps and a completed sync run.

    Returns:
        The seeded test database.
    """
    now = utc_now()

    agents = [
        {
            "source": "sentinelone",
            "source_id": "fw-agent-1",
            "hostname": "srv-fw-01",
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
            "source_id": "fw-agent-2",
            "hostname": "srv-fw-02",
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

    for agent in agents:
        await seeded_db["classification_results"].insert_one(
            {
                "agent_id": agent["source_id"],
                "computed_at": now,
                "results": [],
            }
        )

    return seeded_db


_FRAMEWORK_IDS = ["nist_csf", "nis2", "cis_v8"]
_EXPECTED_COUNTS = {"nist_csf": 15, "nis2": 13, "cis_v8": 14}


class TestNewFrameworksListing:
    """Tests that new frameworks appear correctly in the API."""

    @pytest.mark.asyncio
    async def test_all_new_frameworks_in_listing(self, admin_client: AsyncClient) -> None:
        """All three new frameworks appear in the framework listing."""
        resp = await admin_client.get("/api/v1/compliance/frameworks")
        assert resp.status_code == 200
        fw_ids = {f["id"] for f in resp.json()["frameworks"]}
        for fid in _FRAMEWORK_IDS:
            assert fid in fw_ids, f"{fid} not found in framework listing"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework_id", _FRAMEWORK_IDS)
    async def test_framework_has_disclaimer(
        self, admin_client: AsyncClient, framework_id: str
    ) -> None:
        """Each new framework has a non-empty disclaimer."""
        resp = await admin_client.get("/api/v1/compliance/frameworks")
        fw = next(f for f in resp.json()["frameworks"] if f["id"] == framework_id)
        assert len(fw["disclaimer"]) > 50


class TestNewFrameworksEnableDisable:
    """Tests framework enable/disable for new frameworks."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework_id", _FRAMEWORK_IDS)
    async def test_enable_framework(self, admin_client: AsyncClient, framework_id: str) -> None:
        """Enabling a new framework succeeds."""
        resp = await admin_client.put(f"/api/v1/compliance/frameworks/{framework_id}/enable")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework_id", _FRAMEWORK_IDS)
    async def test_disable_framework(self, admin_client: AsyncClient, framework_id: str) -> None:
        """Disabling a new framework succeeds."""
        await admin_client.put(f"/api/v1/compliance/frameworks/{framework_id}/enable")
        resp = await admin_client.put(f"/api/v1/compliance/frameworks/{framework_id}/disable")
        assert resp.status_code == 200


class TestNewFrameworksDetail:
    """Tests framework detail returns correct control counts."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework_id", _FRAMEWORK_IDS)
    async def test_detail_returns_expected_controls(
        self, admin_client: AsyncClient, framework_id: str
    ) -> None:
        """Framework detail returns the expected number of controls."""
        resp = await admin_client.get(f"/api/v1/compliance/frameworks/{framework_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert len(detail["controls"]) == _EXPECTED_COUNTS[framework_id]


class TestNewFrameworksComplianceRun:
    """Tests compliance run execution for new frameworks."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework_id", _FRAMEWORK_IDS)
    async def test_run_produces_results(
        self,
        admin_client: AsyncClient,
        frameworks_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        framework_id: str,
    ) -> None:
        """Running compliance checks produces results for each new framework."""
        await admin_client.put(f"/api/v1/compliance/frameworks/{framework_id}/enable")

        resp = await admin_client.post(
            "/api/v1/compliance/run",
            json={"framework_id": framework_id},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["controls_evaluated"] > 0
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework_id", _FRAMEWORK_IDS)
    async def test_results_appear_in_dashboard(
        self,
        admin_client: AsyncClient,
        frameworks_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        framework_id: str,
    ) -> None:
        """After a run, the framework score appears in the dashboard."""
        await admin_client.put(f"/api/v1/compliance/frameworks/{framework_id}/enable")
        await admin_client.post(
            "/api/v1/compliance/run",
            json={"framework_id": framework_id},
        )

        resp = await admin_client.get("/api/v1/compliance/dashboard")
        assert resp.status_code == 200
        fw_score = next(
            (fw for fw in resp.json()["frameworks"] if fw["framework_id"] == framework_id),
            None,
        )
        assert fw_score is not None
        assert fw_score["total_controls"] > 0
