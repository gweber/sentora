"""Integration tests for the sync API endpoints.

Tests cover the REST endpoints (trigger, status, history) of the sync domain.
The SyncManager uses independent phase runners that execute as background
asyncio tasks.  In the test environment no S1 API token is configured, so
triggered syncs fail immediately with a network/connection error — there is
no simulated/fake pipeline.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from domains.sync.manager import sync_manager


@pytest.fixture(autouse=True)
def reset_sync_manager() -> None:
    """Reset in-memory SyncManager state before every test.

    The SyncManager is a module-level singleton. Without this fixture,
    state from one test (a running or completed run) leaks into the next.
    """
    for attr, value in (
        ("_current_run", None),
        ("_last_completed", None),
        ("_history", []),
        ("_clients", set()),
    ):
        setattr(sync_manager, attr, value)
    # Reset all phase runners to idle
    for runner in sync_manager._runners.values():
        runner._status = "idle"
        runner._cancelled = False
        runner._run_id = None
        runner._synced = 0
        runner._total = 0
        runner._message = None
        runner._error = None


class TestTriggerSync:
    """Tests for POST /api/v1/sync/trigger."""

    async def test_trigger_returns_phases_started(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Triggering a sync returns the mode and list of phases started."""
        response = await client.post("/api/v1/sync/trigger", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "phases_started" in data
        assert isinstance(data["phases_started"], list)
        assert len(data["phases_started"]) > 0

    async def test_trigger_response_shape(self, client: AsyncClient, admin_headers: dict) -> None:
        """Response must include mode and phases_started fields."""
        response = await client.post("/api/v1/sync/trigger", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "phases_started" in data
        assert data["mode"] == "auto"

    async def test_trigger_409_when_running(self, client: AsyncClient, admin_headers: dict) -> None:
        """A second trigger while all phases are running returns 409.

        We manually set all phase runners to "running" since the fail-fast
        path completes near-instantly, making a natural race impossible to
        test reliably.
        """
        for runner in sync_manager._runners.values():
            runner._status = "running"
        response = await client.post("/api/v1/sync/trigger", headers=admin_headers)
        assert response.status_code == 409
        assert "already running" in response.json()["detail"].lower()

    async def test_trigger_settles_to_failed_without_token(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Without an S1 API token, the sync fails with a connection error."""
        await client.post("/api/v1/sync/trigger", headers=admin_headers)
        # Let the background tasks settle (phases fail near-instantly)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if not sync_manager.is_running():
                break
        response = await client.get("/api/v1/sync/status", headers=admin_headers)
        data = response.json()
        last = data["last_completed_run"]
        assert last is not None
        assert last["status"] == "failed"
        # The run message should indicate failure
        assert last["message"] is not None
        assert "failed" in last["message"].lower()

    async def test_trigger_allowed_after_failure(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """After a sync fails, a new trigger is accepted (not 409)."""
        await client.post("/api/v1/sync/trigger", headers=admin_headers)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if not sync_manager.is_running():
                break
        response = await client.post("/api/v1/sync/trigger", headers=admin_headers)
        assert response.status_code == 200


class TestGetSyncStatus:
    """Tests for GET /api/v1/sync/status."""

    async def test_status_idle(self, client: AsyncClient, admin_headers: dict) -> None:
        """Status before any sync has no current_run and no last_completed_run."""
        response = await client.get("/api/v1/sync/status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["current_run"] is None
        assert data["last_completed_run"] is None

    async def test_status_while_running(self, client: AsyncClient, admin_headers: dict) -> None:
        """Status during a sync shows a non-null current_run with status 'running'.

        We manually set the manager state since the fail-fast path completes
        near-instantly.
        """
        from domains.sync.dto import SyncRunResponse
        from utils.dt import utc_now

        sync_manager._current_run = SyncRunResponse(
            id="test-running",
            started_at=utc_now().isoformat(),
            status="running",
            trigger="manual",
            phase="agents",
            message="Syncing agents…",
        )
        response = await client.get("/api/v1/sync/status", headers=admin_headers)
        assert response.status_code == 200
        current = response.json()["current_run"]
        assert current is not None
        assert current["status"] == "running"


class TestGetSyncHistory:
    """Tests for GET /api/v1/sync/history."""

    async def test_history_empty_before_sync(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """History is empty before any sync has completed."""
        response = await client.get("/api/v1/sync/history", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["runs"] == []

    async def test_history_after_failed_sync(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """After a sync fails, history contains one run with status 'failed'."""
        await client.post("/api/v1/sync/trigger", headers=admin_headers)
        for _ in range(40):
            await asyncio.sleep(0.5)
            if not sync_manager.is_running():
                break
        response = await client.get("/api/v1/sync/history", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["runs"][0]["status"] == "failed"
