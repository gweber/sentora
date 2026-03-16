"""Integration tests for the dashboard endpoints.

Tests cover GET /api/v1/dashboard/fleet, /apps, /fingerprinting, and POST /refresh.
On an empty database the endpoints compute on demand and cache results.
"""

from __future__ import annotations

from httpx import AsyncClient


class TestDashboardFleet:
    """Tests for GET /api/v1/dashboard/fleet."""

    async def test_fleet_returns_200(self, client: AsyncClient, admin_headers: dict) -> None:
        """Fleet endpoint returns 200 even on an empty database."""
        response = await client.get("/api/v1/dashboard/fleet", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_agents" in data
        assert "total_groups" in data
        assert "total_sites" in data

    async def test_fleet_zero_counts_on_empty_db(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """On an empty database, all fleet counts are zero."""
        data = (await client.get("/api/v1/dashboard/fleet", headers=admin_headers)).json()
        assert data["total_agents"] == 0
        assert data["total_groups"] == 0
        assert data["total_sites"] == 0

    async def test_fleet_cached_on_second_call(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Second call returns cached data (no recompute)."""
        r1 = (await client.get("/api/v1/dashboard/fleet", headers=admin_headers)).json()
        r2 = (await client.get("/api/v1/dashboard/fleet", headers=admin_headers)).json()
        assert r1 == r2


class TestDashboardApps:
    """Tests for GET /api/v1/dashboard/apps."""

    async def test_apps_returns_200(self, client: AsyncClient, admin_headers: dict) -> None:
        """Apps endpoint returns 200 even on an empty database."""
        response = await client.get("/api/v1/dashboard/apps", headers=admin_headers)
        assert response.status_code == 200


class TestDashboardFingerprinting:
    """Tests for GET /api/v1/dashboard/fingerprinting."""

    async def test_fingerprinting_returns_200(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Fingerprinting endpoint returns 200 even on an empty database."""
        response = await client.get("/api/v1/dashboard/fingerprinting", headers=admin_headers)
        assert response.status_code == 200


class TestDashboardRefresh:
    """Tests for POST /api/v1/dashboard/refresh."""

    async def test_refresh_returns_200(self, client: AsyncClient, admin_headers: dict) -> None:
        """Manual refresh returns 200."""
        response = await client.post("/api/v1/dashboard/refresh", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "refreshed"

    async def test_refresh_updates_cache(self, client: AsyncClient, admin_headers: dict) -> None:
        """After refresh, fleet endpoint returns fresh data."""
        await client.post("/api/v1/dashboard/refresh", headers=admin_headers)
        response = await client.get("/api/v1/dashboard/fleet", headers=admin_headers)
        assert response.status_code == 200
