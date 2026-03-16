"""Integration tests for S1 API error handling during sync.

Tests mock S1Client._get to simulate various S1 API failures and verify
that SyncManager propagates errors gracefully — recording the failure in
run status, message, and history.

Each test:
1. Configures a valid S1 API token so the fail-fast guard is bypassed.
2. Patches S1Client._get to simulate a specific failure.
3. Triggers a sync via the test client (with admin JWT auth).
4. Waits for the background task to settle.
5. Checks the sync status/history for proper error reporting.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Never
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.sync.manager import sync_manager
from domains.sync.s1_client import S1ApiError, S1Client, S1RateLimitError

# Target string for patch() — must match the import path used by the manager
_S1_GET = "domains.sync.s1_client.S1Client._get"


@pytest.fixture(autouse=True)
def reset_sync_manager() -> None:
    """Reset in-memory SyncManager state before every test."""
    sync_manager._current_run = None
    sync_manager._last_completed = None
    sync_manager._history = []
    sync_manager._clients = set()
    # Reset all phase runners to idle
    for runner in sync_manager._runners.values():
        runner._status = "idle"
        runner._cancelled = False
        runner._run_id = None
        runner._synced = 0
        runner._total = 0
        runner._message = None
        runner._error = None


def _make_admin_token() -> str:
    """Create a valid admin JWT for test requests."""
    from domains.auth.service import create_access_token

    return create_access_token({"sub": "test-admin", "role": "admin"})


@pytest_asyncio.fixture(scope="function")
async def authed_client(seeded_db: AsyncIOMotorDatabase) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[type-arg]
    """Provide an authenticated HTTPX test client with admin JWT and
    S1 config that bypasses the fail-fast guard.
    """
    import database
    from config import get_settings
    from main import app

    original_db = database._client
    database._client = seeded_db.client

    settings = get_settings()
    original_mongo_db = settings.__dict__.get("mongo_db")
    original_s1_token = settings.__dict__.get("s1_api_token")
    original_s1_url = settings.__dict__.get("s1_base_url")

    # Set valid S1 config so the sync pipeline doesn't hit the fail-fast guard
    object.__setattr__(settings, "mongo_db", "sentora_test")
    object.__setattr__(settings, "s1_api_token", "fake-test-token-for-s1-errors")
    object.__setattr__(settings, "s1_base_url", "https://test-tenant.sentinelone.net/web/api/v2.1")

    token = _make_admin_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    # Restore
    database._client = original_db
    if original_mongo_db is not None:
        object.__setattr__(settings, "mongo_db", original_mongo_db)
    if original_s1_token is not None:
        object.__setattr__(settings, "s1_api_token", original_s1_token)
    if original_s1_url is not None:
        object.__setattr__(settings, "s1_base_url", original_s1_url)


async def _wait_for_sync_to_settle(max_seconds: float = 5.0) -> None:
    """Poll until no phase runners are active, or timeout."""
    # Brief initial sleep to let background tasks start
    await asyncio.sleep(0.1)
    elapsed = 0.1
    while elapsed < max_seconds:
        if not sync_manager.is_running():
            return
        await asyncio.sleep(0.2)
        elapsed += 0.2


async def _get_last_failed_run(client: AsyncClient) -> dict:
    """Fetch the last completed run from the status endpoint and assert it failed.

    Returns a dict with the run fields plus an ``error_messages`` list
    that aggregates error information from the run message and per-phase
    error fields, so callers can search for error text uniformly.
    """
    resp = await client.get("/api/v1/sync/status")
    assert resp.status_code == 200
    data = resp.json()
    last = data["last_completed_run"]
    assert last is not None, "Expected a last_completed_run after sync failure"
    assert last["status"] == "failed"
    # Build a list of error messages from the run message and per-phase errors
    errors: list[str] = []
    if last.get("message"):
        errors.append(last["message"])
    # Collect per-phase error details from the phases status
    phases = data.get("phases", {})
    for phase_info in phases.values():
        if phase_info.get("error"):
            errors.append(phase_info["error"])
        if phase_info.get("message"):
            errors.append(phase_info["message"])
    last["error_messages"] = errors
    return last


# ---------------------------------------------------------------------------
# Helper: build a side_effect function that works as a method replacement
# ---------------------------------------------------------------------------


def _make_raiser(exc: BaseException) -> Callable[..., Never]:
    """Return an async function that raises *exc* regardless of arguments.

    Works correctly when patched onto S1Client._get because it accepts
    (self, path, *, params=..., raw_query=...) via *args/**kwargs.
    """

    async def _raise(*args: object, **kwargs: object) -> Never:
        raise exc

    return _raise  # type: ignore[return-value]


# ===========================================================================
# 1. S1 API Timeout
# ===========================================================================


class TestS1ApiTimeout:
    """S1 API returns a timeout during the sites fetch (first phase)."""

    async def test_timeout_results_in_failed_run(self, authed_client: AsyncClient) -> None:
        """A TimeoutException during the S1 API call should fail the sync
        with a clear error message mentioning the timeout.
        """
        side_effect = _make_raiser(httpx.TimeoutException("Connection timed out"))

        with patch.object(S1Client, "_get", new=side_effect):
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200

            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"]).lower()
            assert "timed out" in error_text or "timeout" in error_text

    async def test_timeout_recorded_in_history(self, authed_client: AsyncClient) -> None:
        """The failed run should appear in the sync history."""
        side_effect = _make_raiser(httpx.TimeoutException("Connection timed out"))

        with patch.object(S1Client, "_get", new=side_effect):
            await authed_client.post("/api/v1/sync/trigger")
            await _wait_for_sync_to_settle()

            resp = await authed_client.get("/api/v1/sync/history")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 1
            assert any(r["status"] == "failed" for r in data["runs"])


# ===========================================================================
# 2. S1 API 429 (Rate Limited)
# ===========================================================================


class TestS1ApiRateLimit:
    """S1 API returns HTTP 429 Too Many Requests."""

    async def test_429_results_in_failed_run(self, authed_client: AsyncClient) -> None:
        """A 429 response should raise S1RateLimitError and fail the sync."""
        side_effect = _make_raiser(S1RateLimitError(429, "Rate limit exceeded", "/sites"))

        with patch.object(S1Client, "_get", new=side_effect):
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200

            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"]).lower()
            assert "429" in error_text or "rate limit" in error_text

    async def test_429_allows_retry_after_failure(self, authed_client: AsyncClient) -> None:
        """After a 429-induced failure, a new sync trigger should be accepted."""
        side_effect = _make_raiser(S1RateLimitError(429, "Rate limit exceeded", "/sites"))

        with patch.object(S1Client, "_get", new=side_effect):
            await authed_client.post("/api/v1/sync/trigger")
            await _wait_for_sync_to_settle()

            # Should be able to trigger again (not 409)
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200


# ===========================================================================
# 3. S1 API 500 (Server Error)
# ===========================================================================


class TestS1ApiServerError:
    """S1 API returns HTTP 500 Internal Server Error."""

    async def test_500_results_in_failed_run(self, authed_client: AsyncClient) -> None:
        """A 500 response should fail the sync with a clear S1 API error."""
        side_effect = _make_raiser(S1ApiError(500, "Internal Server Error", "/sites"))

        with patch.object(S1Client, "_get", new=side_effect):
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200

            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"]).lower()
            assert "500" in error_text or "server error" in error_text

    async def test_500_error_message_contains_api_details(self, authed_client: AsyncClient) -> None:
        """The error messages should include the S1 API error status and context."""
        side_effect = _make_raiser(S1ApiError(500, "Internal Server Error", "/groups"))

        with patch.object(S1Client, "_get", new=side_effect):
            await authed_client.post("/api/v1/sync/trigger")
            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"])
            # Should reference the S1 API error class output format
            assert "S1 API error 500" in error_text


# ===========================================================================
# 4. S1 API Auth Failure (401)
# ===========================================================================


class TestS1ApiAuthFailure:
    """S1 API returns HTTP 401 Unauthorized (expired or invalid token)."""

    async def test_401_results_in_failed_run(self, authed_client: AsyncClient) -> None:
        """A 401 response should fail the sync with an auth-related error."""
        side_effect = _make_raiser(S1ApiError(401, "Unauthorized - Invalid API token", "/sites"))

        with patch.object(S1Client, "_get", new=side_effect):
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200

            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"]).lower()
            assert "401" in error_text or "unauthorized" in error_text

    async def test_401_error_message_mentions_auth(self, authed_client: AsyncClient) -> None:
        """Error messages for 401 should clearly mention the authentication failure."""
        side_effect = _make_raiser(S1ApiError(401, "Unauthorized - Invalid API token", "/sites"))

        with patch.object(S1Client, "_get", new=side_effect):
            await authed_client.post("/api/v1/sync/trigger")
            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"])
            assert "401" in error_text
            assert "Unauthorized" in error_text


# ===========================================================================
# 5. Network Unreachable (ConnectError)
# ===========================================================================


class TestS1NetworkUnreachable:
    """Network-level failure — cannot connect to S1 at all."""

    async def test_connect_error_results_in_failed_run(self, authed_client: AsyncClient) -> None:
        """A ConnectError should fail the sync with a network error message."""
        side_effect = _make_raiser(httpx.ConnectError("Failed to establish connection"))

        with patch.object(S1Client, "_get", new=side_effect):
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200

            await _wait_for_sync_to_settle()

            last = await _get_last_failed_run(authed_client)
            error_text = " ".join(last["error_messages"]).lower()
            assert "connect" in error_text or "connection" in error_text or "network" in error_text

    async def test_connect_error_recorded_in_history(self, authed_client: AsyncClient) -> None:
        """The network-failure run should appear in sync history."""
        side_effect = _make_raiser(httpx.ConnectError("Failed to establish connection"))

        with patch.object(S1Client, "_get", new=side_effect):
            await authed_client.post("/api/v1/sync/trigger")
            await _wait_for_sync_to_settle()

            resp = await authed_client.get("/api/v1/sync/history")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 1
            failed_runs = [r for r in data["runs"] if r["status"] == "failed"]
            assert len(failed_runs) >= 1
            error_text = (failed_runs[0].get("message") or "").lower()
            assert "connect" in error_text or "connection" in error_text or "failed" in error_text

    async def test_connect_error_sync_not_stuck_running(self, authed_client: AsyncClient) -> None:
        """After a network failure, the sync manager should not be stuck in 'running' state."""
        side_effect = _make_raiser(httpx.ConnectError("Failed to establish connection"))

        with patch.object(S1Client, "_get", new=side_effect):
            await authed_client.post("/api/v1/sync/trigger")
            await _wait_for_sync_to_settle()

        # After the patch context exits, verify manager is not stuck
        assert not sync_manager.is_running()

        # A new trigger should be accepted (not 409)
        side_effect2 = _make_raiser(S1ApiError(500, "test", "/test"))
        with patch.object(S1Client, "_get", new=side_effect2):
            resp = await authed_client.post("/api/v1/sync/trigger")
            assert resp.status_code == 200
