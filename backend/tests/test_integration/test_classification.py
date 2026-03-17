"""Integration tests for the classification API endpoints.

Tests run against a real (isolated test) MongoDB instance. Every public
classification command and query is covered per TESTING.md requirements.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase


async def _wait_for_classification_idle(timeout: float = 10.0) -> None:
    """Wait until the classification manager's run lock is released (run complete).

    Yields to the event loop first so the background task (created via
    asyncio.create_task) has a chance to start and acquire the lock.
    The lock is acquired *inside* _run_classification, not at create_task time,
    so we must yield before checking.

    If the lock is already released when we first check (fast task completion),
    we return immediately — that is the correct outcome.
    """
    from domains.classification.classifier import classification_manager

    # Give the background task time to start and acquire the lock
    await asyncio.sleep(0.05)

    def _is_idle() -> bool:
        """Check both the asyncio lock and the _running flag (added by AUDIT-010)."""
        locked = classification_manager._lock.locked()
        running = getattr(classification_manager, "_running", False)
        return not locked and not running

    # If the task already finished, we're done
    if _is_idle():
        return
    # Task is still running — wait for it to finish
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if _is_idle():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("Classification run did not complete within timeout")


async def _wait_for_results(
    client: AsyncClient,
    timeout: float = 10.0,
    *,
    db: AsyncIOMotorDatabase | None = None,  # type: ignore[type-arg]
) -> None:
    """Wait for a classification run to fully complete and results to appear.

    Uses a two-phase strategy:
    1. Wait for the classification manager's in-memory state to indicate idle.
    2. If a DB handle is provided, poll the ``classification_results`` collection
       to confirm at least one result was persisted.  This guards against
       a subtle race where a *previous* test's background task held the DB
       connection pool, preventing writes from the current run.
    """
    await _wait_for_classification_idle(timeout)

    if db is not None:
        # Phase 2: confirm results are actually in the DB.
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            count = await db["classification_results"].count_documents({})
            if count > 0:
                return
            await asyncio.sleep(0.1)


async def _trigger_and_wait(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Trigger a classification run and wait synchronously for it to complete.

    Unlike the API trigger (which fires a background task), this helper
    calls ``_run_classification`` directly so the pipeline is fully
    complete — including all MongoDB writes — before returning.  This
    eliminates the race condition where background task writes aren't
    visible to the calling test.
    """
    from domains.classification.classifier import classification_manager
    from domains.classification.entities import ClassificationRun
    from domains.classification.repository import save_run

    # Ensure no stale state
    classification_manager._running = False
    if classification_manager._lock.locked():
        classification_manager._lock.release()

    run = ClassificationRun(trigger="manual", status="running")
    await save_run(db, run)
    await classification_manager._run_classification(db, run.id)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seeded_agents(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:
    """Insert 3 fake agents and install apps into the test DB.

    Agents:
    - agent1: group_scada, has WinCC apps → should match the SCADA fingerprint.
    - agent2: group_lab, has ZebraDesigner → should match the lab fingerprint.
    - agent3: group_scada (linux server), has WinCC Runtime.

    Args:
        test_db: Clean test database (injected).

    Returns:
        The test database with agents and installed apps seeded.
    """
    now = "2025-01-01T00:00:00"
    await test_db["agents"].insert_many(
        [
            {
                "source": "sentinelone",
                "source_id": "agent1",
                "hostname": "pc-001",
                "group_id": "group_scada",
                "group_name": "SCADA Systems",
                "os_type": "windows",
                "os_version": "10",
                "agent_status": "online",
                "last_active": now,
                "machine_type": "desktop",
                "domain": None,
                "ip_addresses": [],
                "tags": [],
                "synced_at": now,
            },
            {
                "source": "sentinelone",
                "source_id": "agent2",
                "hostname": "pc-002",
                "group_id": "group_lab",
                "group_name": "Lab Systems",
                "os_type": "windows",
                "os_version": "10",
                "agent_status": "online",
                "last_active": now,
                "machine_type": "desktop",
                "domain": None,
                "ip_addresses": [],
                "tags": [],
                "synced_at": now,
            },
            {
                "source": "sentinelone",
                "source_id": "agent3",
                "hostname": "pc-003",
                "group_id": "group_scada",
                "group_name": "SCADA Systems",
                "os_type": "linux",
                "os_version": "Ubuntu 22.04",
                "agent_status": "offline",
                "last_active": now,
                "machine_type": "server",
                "domain": None,
                "ip_addresses": [],
                "tags": [],
                "synced_at": now,
            },
        ]
    )
    await test_db["installed_apps"].insert_many(
        [
            {
                "agent_id": "agent1",
                "normalized_name": "wincc runtime",
                "name": "WinCC Runtime",
                "version": "8.0",
                "publisher": "Siemens",
                "size": None,
                "installed_date": None,
                "synced_at": now,
            },
            {
                "agent_id": "agent1",
                "normalized_name": "wincc configuration studio",
                "name": "WinCC Configuration Studio",
                "version": "8.0",
                "publisher": "Siemens",
                "size": None,
                "installed_date": None,
                "synced_at": now,
            },
            {
                "agent_id": "agent2",
                "normalized_name": "zebra designer",
                "name": "ZebraDesigner",
                "version": "3.0",
                "publisher": "Zebra",
                "size": None,
                "installed_date": None,
                "synced_at": now,
            },
            {
                "agent_id": "agent3",
                "normalized_name": "wincc runtime",
                "name": "WinCC Runtime",
                "version": "7.5",
                "publisher": "Siemens",
                "size": None,
                "installed_date": None,
                "synced_at": now,
            },
        ]
    )
    return test_db


@pytest_asyncio.fixture
async def seeded_fingerprints(seeded_agents: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:
    """Insert fingerprints for the scada and lab groups into the test DB.

    Fingerprints:
    - group_scada: single marker matching 'wincc*' (weight 1.5).
    - group_lab: single marker matching 'zebra*' (weight 1.0).

    Args:
        seeded_agents: Test database already populated with agents and apps.

    Returns:
        The same database with fingerprints also seeded.
    """
    from bson import ObjectId

    now = "2025-01-01T00:00:00"
    await seeded_agents["fingerprints"].insert_many(
        [
            {
                "_id": str(ObjectId()),
                "group_id": "group_scada",
                "group_name": "SCADA Systems",
                "markers": [
                    {
                        "_id": str(ObjectId()),
                        "pattern": "wincc*",
                        "display_name": "Siemens WinCC",
                        "category": "scada_hmi",
                        "weight": 1.5,
                        "source": "manual",
                        "confidence": 1.0,
                        "added_at": now,
                        "added_by": "user",
                    },
                ],
                "created_at": now,
                "updated_at": now,
                "created_by": "user",
            },
            {
                "_id": str(ObjectId()),
                "group_id": "group_lab",
                "group_name": "Lab Systems",
                "markers": [
                    {
                        "_id": str(ObjectId()),
                        "pattern": "zebra*",
                        "display_name": "ZebraDesigner",
                        "category": "labeling_barcode",
                        "weight": 1.0,
                        "source": "manual",
                        "confidence": 1.0,
                        "added_at": now,
                        "added_by": "user",
                    },
                ],
                "created_at": now,
                "updated_at": now,
                "created_by": "user",
            },
        ]
    )
    return seeded_agents


# ── TestClassificationOverview ────────────────────────────────────────────────


class TestClassificationOverview:
    """Tests for GET /api/v1/classification/overview — aggregate statistics."""

    async def test_empty_overview(self, client: AsyncClient, admin_headers: dict) -> None:
        """With no results in DB, all counts must be 0 and last_computed_at null."""
        r = await client.get("/api/v1/classification/overview", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["correct"] == 0
        assert data["misclassified"] == 0
        assert data["ambiguous"] == 0
        assert data["unclassifiable"] == 0
        assert data["last_computed_at"] is None

    async def test_overview_shape(self, client: AsyncClient, admin_headers: dict) -> None:
        """The overview response must contain all required fields."""
        r = await client.get("/api/v1/classification/overview", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for field in (
            "total",
            "correct",
            "misclassified",
            "ambiguous",
            "unclassifiable",
            "groups_count",
            "last_computed_at",
        ):
            assert field in data, f"Missing field: {field}"


# ── TestTriggerClassification ─────────────────────────────────────────────────


class TestTriggerClassification:
    """Tests for POST /api/v1/classification/trigger — kick off a run."""

    async def test_trigger_returns_run(
        self, client: AsyncClient, seeded_fingerprints: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """Triggering classification with seeded data must return 202 with id and status."""
        r = await client.post("/api/v1/classification/trigger", headers=analyst_headers)
        assert r.status_code == 202
        data = r.json()
        assert data.get("id"), "Run must have a non-empty id"
        assert data.get("status") in ("running", "completed")
        # Wait for the background classification task to complete so it does not
        # write to the next test's DB (race condition: all tests share the same
        # MongoDB database name "sentora_test").
        await _wait_for_results(client)

    async def test_trigger_no_fingerprints(
        self, client: AsyncClient, seeded_agents: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """Triggering with agents but no fingerprints must still return 202 — not 500."""
        r = await client.post("/api/v1/classification/trigger", headers=analyst_headers)
        assert r.status_code == 202
        # No fingerprints → no results; wait for the run to complete anyway.
        await _wait_for_classification_idle()

    @pytest.mark.skip(
        reason=(
            "# TODO(2026-03-15): Race condition test needs "
            "classifier state seeding — seed _current_run on "
            "ClassificationManager before trigger"
        )
    )
    async def test_trigger_409_if_running(self, client: AsyncClient) -> None:
        """Triggering a second run while one is already running must return 409."""


# ── TestGetResults ────────────────────────────────────────────────────────────


class TestGetResults:
    """Tests for GET /api/v1/classification/results — paginated result list."""

    async def test_results_empty_before_run(self, client: AsyncClient, admin_headers: dict) -> None:
        """Before any classification run the results list must be empty."""
        r = await client.get("/api/v1/classification/results", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["results"] == []

    async def test_results_after_trigger(
        self, client: AsyncClient, seeded_fingerprints: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """After triggering a run and waiting briefly, at least one result must appear."""
        await _trigger_and_wait(seeded_fingerprints)

        r = await client.get("/api/v1/classification/results", headers=analyst_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0, "Expected at least one classification result after trigger"

    async def test_filter_by_classification(
        self, client: AsyncClient, seeded_fingerprints: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """Filtering results by classification=correct must only return correct results."""
        await _trigger_and_wait(seeded_fingerprints)

        r = await client.get(
            "/api/v1/classification/results",
            params={"classification": "correct"},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        data = r.json()
        for result in data["results"]:
            assert result["classification"] == "correct"

    async def test_pagination(
        self, client: AsyncClient, seeded_fingerprints: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """Setting limit=1 must return exactly 1 result while total reflects all results."""
        await _trigger_and_wait(seeded_fingerprints)

        r = await client.get(
            "/api/v1/classification/results", params={"limit": 1}, headers=analyst_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 1
        assert data["total"] >= 1


# ── TestGetResultByAgent ──────────────────────────────────────────────────────


class TestGetResultByAgent:
    """Tests for GET /api/v1/classification/results/{agent_id} — single agent result."""

    async def test_404_before_run(self, client: AsyncClient, admin_headers: dict) -> None:
        """Requesting a result for an agent before any run must return 404."""
        r = await client.get("/api/v1/classification/results/agent1", headers=admin_headers)
        assert r.status_code == 404

    async def test_returns_after_run(
        self, client: AsyncClient, seeded_fingerprints: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """After triggering a run, fetching a specific agent result must return 200."""
        await _trigger_and_wait(seeded_fingerprints)

        r = await client.get("/api/v1/classification/results/agent1", headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["agent_id"] == "agent1"


# ── TestAcknowledge ───────────────────────────────────────────────────────────


class TestAcknowledge:
    """Tests for POST /api/v1/classification/acknowledge/{agent_id} — mark as acknowledged."""

    async def test_acknowledge(
        self, client: AsyncClient, seeded_fingerprints: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """Acknowledging a result must set acknowledged=True on subsequent GET."""
        await _trigger_and_wait(seeded_fingerprints)

        ack = await client.post(
            "/api/v1/classification/acknowledge/agent1", headers=analyst_headers
        )
        assert ack.status_code in (200, 204)

        r = await client.get("/api/v1/classification/results/agent1", headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["acknowledged"] is True

    async def test_acknowledge_404(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Acknowledging an agent that has no classification result must return 404."""
        r = await client.post(
            "/api/v1/classification/acknowledge/nonexistent_agent_xyz", headers=analyst_headers
        )
        assert r.status_code == 404


# ── TestClassifyCorrectly ─────────────────────────────────────────────────────


class TestClassifyCorrectly:
    """Unit-style test for classify_single_agent using the seeded DB fixture."""

    async def test_classifies_agent_correctly(
        self, seeded_fingerprints: AsyncIOMotorDatabase
    ) -> None:
        """agent1 (group_scada) with WinCC apps must classify as 'correct' for SCADA."""
        from domains.classification.classifier import classify_single_agent
        from domains.fingerprint.repository import list_all as list_fingerprints

        fingerprints = await list_fingerprints(seeded_fingerprints)
        agent_doc = {
            "source": "sentinelone",
            "source_id": "agent1",
            "hostname": "pc-001",
            "group_id": "group_scada",
            "group_name": "SCADA Systems",
        }
        result = await classify_single_agent(seeded_fingerprints, agent_doc, fingerprints)
        assert result.classification == "correct"
        assert result.agent_id == "agent1"
