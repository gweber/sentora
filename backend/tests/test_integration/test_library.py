"""Integration tests for the library domain.

Tests library entry CRUD, subscriptions, and stats via the HTTP API.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ── Library entry CRUD ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_entries_empty(client: AsyncClient, admin_headers: dict) -> None:
    resp = await client.get("/api/v1/library/", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["entries"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_entry(client: AsyncClient, admin_headers: dict) -> None:
    payload = {
        "name": "Test Chrome",
        "vendor": "Google",
        "category": "browser",
        "description": "Test browser entry",
        "tags": ["browser", "web"],
        "markers": [
            {"pattern": "*chrome*", "display_name": "Chrome", "weight": 1.0},
            {"pattern": "*google*chrome*", "display_name": "Google Chrome", "weight": 1.2},
        ],
    }
    resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    entry = resp.json()
    assert entry["name"] == "Test Chrome"
    assert entry["vendor"] == "Google"
    assert entry["status"] == "draft"
    assert entry["source"] == "manual"
    assert len(entry["markers"]) == 2
    assert entry["markers"][0]["pattern"] == "*chrome*"
    assert entry["subscriber_count"] == 0


@pytest.mark.asyncio
async def test_get_entry(client: AsyncClient, admin_headers: dict) -> None:
    # Create
    payload = {"name": "Firefox", "vendor": "Mozilla", "markers": [{"pattern": "*firefox*"}]}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]

    # Get
    resp = await client.get(f"/api/v1/library/entries/{entry_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Firefox"


@pytest.mark.asyncio
async def test_get_entry_not_found(client: AsyncClient, admin_headers: dict) -> None:
    resp = await client.get("/api/v1/library/entries/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_entry(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"name": "Edge", "vendor": "Microsoft"}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/library/entries/{entry_id}",
        json={"description": "Chromium-based browser"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Chromium-based browser"


@pytest.mark.asyncio
async def test_delete_entry(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"name": "To Delete"}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/library/entries/{entry_id}", headers=admin_headers)
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/library/entries/{entry_id}", headers=admin_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_publish_entry(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"name": "Draft Entry"}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "draft"

    pub_resp = await client.post(
        f"/api/v1/library/entries/{entry_id}/publish", headers=admin_headers
    )
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "published"
    assert pub_resp.json()["reviewed_by"] == "testadmin"


@pytest.mark.asyncio
async def test_deprecate_entry(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"name": "Old Entry"}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]

    # Publish first, then deprecate
    await client.post(f"/api/v1/library/entries/{entry_id}/publish", headers=admin_headers)
    dep_resp = await client.post(
        f"/api/v1/library/entries/{entry_id}/deprecate", headers=admin_headers
    )
    assert dep_resp.status_code == 200
    assert dep_resp.json()["status"] == "deprecated"


@pytest.mark.asyncio
async def test_list_entries_filters(client: AsyncClient, admin_headers: dict) -> None:
    # Create entries with different sources
    await client.post("/api/v1/library/", json={"name": "A"}, headers=admin_headers)
    await client.post(
        "/api/v1/library/", json={"name": "B", "category": "browser"}, headers=admin_headers
    )

    # Default filter is status=published, but our entries are draft
    resp = await client.get("/api/v1/library/?status=draft", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2

    # Search by name
    resp = await client.get("/api/v1/library/?status=draft&search=B", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    assert any(e["name"] == "B" for e in resp.json()["entries"])


# ── Subscriptions ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_and_list(client: AsyncClient, admin_headers: dict) -> None:
    # Create and publish an entry
    payload = {"name": "Sub Test", "markers": [{"pattern": "*subtest*"}]}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]
    await client.post(f"/api/v1/library/entries/{entry_id}/publish", headers=admin_headers)

    # Subscribe a group
    sub_resp = await client.post(
        f"/api/v1/library/entries/{entry_id}/subscribe",
        json={"group_id": "group_001"},
        headers=admin_headers,
    )
    assert sub_resp.status_code == 201
    sub = sub_resp.json()
    assert sub["group_id"] == "group_001"
    assert sub["library_entry_id"] == entry_id

    # List subscriptions for the group
    list_resp = await client.get(
        "/api/v1/library/subscriptions/group/group_001", headers=admin_headers
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # Verify subscriber count incremented
    entry_resp = await client.get(f"/api/v1/library/entries/{entry_id}", headers=admin_headers)
    assert entry_resp.json()["subscriber_count"] == 1


@pytest.mark.asyncio
async def test_subscribe_duplicate_409(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"name": "Dup Sub", "markers": [{"pattern": "*dup*"}]}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]
    await client.post(f"/api/v1/library/entries/{entry_id}/publish", headers=admin_headers)

    await client.post(
        f"/api/v1/library/entries/{entry_id}/subscribe",
        json={"group_id": "group_dup"},
        headers=admin_headers,
    )
    dup_resp = await client.post(
        f"/api/v1/library/entries/{entry_id}/subscribe",
        json={"group_id": "group_dup"},
        headers=admin_headers,
    )
    assert dup_resp.status_code == 409


@pytest.mark.asyncio
async def test_unsubscribe(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"name": "Unsub Test", "markers": [{"pattern": "*unsub*"}]}
    create_resp = await client.post("/api/v1/library/", json=payload, headers=admin_headers)
    entry_id = create_resp.json()["id"]
    await client.post(f"/api/v1/library/entries/{entry_id}/publish", headers=admin_headers)

    await client.post(
        f"/api/v1/library/entries/{entry_id}/subscribe",
        json={"group_id": "group_unsub"},
        headers=admin_headers,
    )

    unsub_resp = await client.delete(
        f"/api/v1/library/entries/{entry_id}/subscribe/group_unsub",
        headers=admin_headers,
    )
    assert unsub_resp.status_code == 204

    # Verify subscriber count decremented
    entry_resp = await client.get(f"/api/v1/library/entries/{entry_id}", headers=admin_headers)
    assert entry_resp.json()["subscriber_count"] == 0


@pytest.mark.asyncio
async def test_sync_subscriptions(client: AsyncClient, admin_headers: dict) -> None:
    resp = await client.post("/api/v1/library/subscriptions/sync", headers=admin_headers)
    assert resp.status_code == 200
    assert "synced" in resp.json()


# ── Stats ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats(client: AsyncClient, admin_headers: dict) -> None:
    resp = await client.get("/api/v1/library/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_entries" in data
    assert "by_source" in data
    assert "by_status" in data
    assert "total_subscriptions" in data


# ── Sources ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sources(client: AsyncClient, admin_headers: dict) -> None:
    resp = await client.get("/api/v1/library/sources/", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    source_names = [s["name"] for s in data["sources"]]
    assert "nist_cpe" in source_names
    assert "mitre" in source_names
    assert "chocolatey" in source_names
    assert "homebrew" in source_names


@pytest.mark.asyncio
async def test_list_ingestion_runs_empty(client: AsyncClient, admin_headers: dict) -> None:
    resp = await client.get("/api/v1/library/ingestion-runs/", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["runs"] == []


@pytest.mark.asyncio
async def test_trigger_unknown_source_fails(client: AsyncClient, admin_headers: dict) -> None:
    """Triggering an unknown source returns 500 IngestionError."""
    resp = await client.post("/api/v1/library/sources/nonexistent/ingest", headers=admin_headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_source_status(client: AsyncClient, admin_headers: dict) -> None:
    """GET /sources/status returns per-source progress with all sources idle."""
    resp = await client.get("/api/v1/library/sources/status", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "nist_cpe" in data
    assert "mitre" in data
    assert "chocolatey" in data
    assert "homebrew" in data
    # All sources should be idle when no ingestion is running
    for name in ("nist_cpe", "mitre", "chocolatey", "homebrew"):
        assert data[name]["status"] == "idle"


@pytest.mark.asyncio
async def test_resume_unknown_source_fails(client: AsyncClient, admin_headers: dict) -> None:
    """Resuming an unknown source returns 500 IngestionError."""
    resp = await client.post("/api/v1/library/sources/nonexistent/resume", headers=admin_headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_resume_no_checkpoint_fails(client: AsyncClient, admin_headers: dict) -> None:
    """Resuming a source with no checkpoint returns 500."""
    resp = await client.post("/api/v1/library/sources/nist_cpe/resume", headers=admin_headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_cancel_unknown_source_fails(client: AsyncClient, admin_headers: dict) -> None:
    """Cancelling an unknown source returns 500 IngestionError."""
    resp = await client.post("/api/v1/library/sources/nonexistent/cancel", headers=admin_headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_cancel_idle_source_fails(client: AsyncClient, admin_headers: dict) -> None:
    """Cancelling a source that is not running returns 500."""
    resp = await client.post("/api/v1/library/sources/nist_cpe/cancel", headers=admin_headers)
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_trigger_all_empty(client: AsyncClient, admin_headers: dict) -> None:
    """POST /sources/trigger-all returns a list of started sources."""
    # Note: actual adapter runs will fail because there are no live APIs
    # in the test environment, but the endpoint should accept the request.
    resp = await client.post("/api/v1/library/sources/trigger-all", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sources_started" in data
    assert isinstance(data["sources_started"], list)

    # Allow the background tasks to settle before the next test
    import asyncio

    await asyncio.sleep(1.0)


@pytest.mark.asyncio
async def test_resume_all_empty(client: AsyncClient, admin_headers: dict) -> None:
    """POST /sources/resume-all with no checkpoints returns empty list."""
    resp = await client.post("/api/v1/library/sources/resume-all", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources_resumed"] == []


@pytest.mark.asyncio
async def test_list_sources_includes_status(client: AsyncClient, admin_headers: dict) -> None:
    """GET /sources/ includes per-source status field."""
    resp = await client.get("/api/v1/library/sources/", headers=admin_headers)
    assert resp.status_code == 200
    for source in resp.json()["sources"]:
        assert "status" in source


# ── Auth enforcement ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/library/")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_viewer_cannot_create(client: AsyncClient) -> None:
    from domains.auth.service import create_access_token

    token = create_access_token({"sub": "viewer", "role": "viewer"})
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/v1/library/", json={"name": "X"}, headers=headers)
    assert resp.status_code == 403
