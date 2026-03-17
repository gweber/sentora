"""Smoke tests — hit every API endpoint the frontend calls and verify 2xx.

These tests ensure that every frontend ``api/*.ts`` call resolves to a
real backend route, returns a valid HTTP status, and does not crash with
serialization errors (e.g. datetime, ObjectId).  They do NOT test business
logic — that's covered by per-domain test files.

The test names mirror the frontend ``api/<module>.ts`` file + function name
so failures map directly to the broken UI flow.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _seed_agent(client: AsyncClient, db: object, headers: dict) -> str:
    """Insert a minimal agent document and return its source_id."""
    from utils.dt import utc_now

    doc = {
        "source": "sentinelone",
        "source_id": "smoke_agent_1",
        "hostname": "smoke-host",
        "os_type": "windows",
        "os_version": "Windows 10",
        "group_id": "smoke_group_1",
        "group_name": "Smoke Group",
        "site_id": "smoke_site_1",
        "site_name": "Smoke Site",
        "agent_status": "online",
        "last_active": utc_now().isoformat(),
        "machine_type": "desktop",
        "installed_app_names": ["chrome", "firefox"],
        "tags": [],
        "synced_at": utc_now().isoformat(),
    }
    await db["agents"].insert_one(doc)  # type: ignore[index]

    await db["groups"].insert_one(  # type: ignore[index]
        {
            "source": "sentinelone",
            "source_id": "smoke_group_1",
            "name": "Smoke Group",
            "site_id": "smoke_site_1",
        }
    )
    await db["sites"].insert_one(  # type: ignore[index]
        {
            "source": "sentinelone",
            "source_id": "smoke_site_1",
            "name": "Smoke Site",
        }
    )
    return "smoke_agent_1"


async def _seed_app_summary(db: object) -> None:
    """Insert a minimal app_summaries document."""
    await db["app_summaries"].insert_one(  # type: ignore[index]
        {
            "normalized_name": "chrome",
            "display_name": "Google Chrome",
            "publisher": "Google",
            "agent_count": 1,
            "category": "browser",
            "category_display": "Browser",
        }
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_fleet(client: AsyncClient, admin_headers: dict) -> None:
    """GET /dashboard/fleet — returns fleet overview stats."""
    resp = await client.get("/api/v1/dashboard/fleet", headers=admin_headers)
    assert resp.status_code == 200
    assert "total_agents" in resp.json()


@pytest.mark.asyncio
async def test_dashboard_apps(client: AsyncClient, admin_headers: dict) -> None:
    """GET /dashboard/apps — returns app stats."""
    resp = await client.get("/api/v1/dashboard/apps", headers=admin_headers)
    assert resp.status_code == 200
    assert "distinct_apps" in resp.json()


@pytest.mark.asyncio
async def test_dashboard_fingerprinting(client: AsyncClient, admin_headers: dict) -> None:
    """GET /dashboard/fingerprinting — returns fingerprinting coverage stats."""
    resp = await client.get("/api/v1/dashboard/fingerprinting", headers=admin_headers)
    assert resp.status_code == 200
    assert "total_groups" in resp.json()


# ── Agents ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agents_list(client: AsyncClient, seeded_db: object, admin_headers: dict) -> None:
    """GET /agents/ — paginated agent list."""
    await _seed_agent(client, seeded_db, admin_headers)
    resp = await client.get("/api/v1/agents/", headers=admin_headers)
    assert resp.status_code == 200
    assert "agents" in resp.json()


@pytest.mark.asyncio
async def test_agents_detail(client: AsyncClient, seeded_db: object, admin_headers: dict) -> None:
    """GET /agents/{id} — single agent detail."""
    aid = await _seed_agent(client, seeded_db, admin_headers)
    resp = await client.get(f"/api/v1/agents/{aid}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["hostname"] == "smoke-host"


@pytest.mark.asyncio
async def test_agents_apps(client: AsyncClient, seeded_db: object, admin_headers: dict) -> None:
    """GET /agents/{id}/apps — installed apps for an agent."""
    aid = await _seed_agent(client, seeded_db, admin_headers)
    resp = await client.get(f"/api/v1/agents/{aid}/apps", headers=admin_headers)
    assert resp.status_code == 200


# ── Apps ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apps_list(client: AsyncClient, seeded_db: object, admin_headers: dict) -> None:
    """GET /apps/ — paginated app list from materialized view."""
    await _seed_app_summary(seeded_db)
    resp = await client.get("/api/v1/apps/", headers=admin_headers)
    assert resp.status_code == 200
    assert "apps" in resp.json()


@pytest.mark.asyncio
async def test_apps_detail(client: AsyncClient, seeded_db: object, admin_headers: dict) -> None:
    """GET /apps/{name} — app detail. 404 when no installed_apps exist."""
    resp = await client.get("/api/v1/apps/chrome", headers=admin_headers)
    # 404 is expected — no installed_apps seeded
    assert resp.status_code in (200, 404)


# ── Audit ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_list(client: AsyncClient, admin_headers: dict) -> None:
    """GET /audit/ — paginated audit log. Verifies no datetime serialization crash."""
    resp = await client.get("/api/v1/audit/", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "total" in body


# ── Config ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_get(client: AsyncClient, admin_headers: dict) -> None:
    """GET /config/ — returns persisted config."""
    resp = await client.get("/api/v1/config/", headers=admin_headers)
    assert resp.status_code == 200
    assert "classification_threshold" in resp.json()


@pytest.mark.asyncio
async def test_config_update(client: AsyncClient, admin_headers: dict) -> None:
    """PUT /config/ — updates config and returns new state."""
    resp = await client.put(
        "/api/v1/config/",
        json={"classification_threshold": 0.75},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["classification_threshold"] == 0.75


# ── Branding (public) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_branding_get(client: AsyncClient) -> None:
    """GET /branding/ — public branding info (no auth required)."""
    resp = await client.get("/api/v1/branding/")
    assert resp.status_code == 200
    assert "app_name" in resp.json()


# ── Taxonomy ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_taxonomy_categories(client: AsyncClient, admin_headers: dict) -> None:
    """GET /taxonomy/ — list categories."""
    resp = await client.get("/api/v1/taxonomy/", headers=admin_headers)
    assert resp.status_code == 200
    assert "categories" in resp.json()


@pytest.mark.asyncio
async def test_taxonomy_create_entry(client: AsyncClient, admin_headers: dict) -> None:
    """POST /taxonomy/ — create a taxonomy entry."""
    resp = await client.post(
        "/api/v1/taxonomy/",
        json={
            "name": "Smoke Test App",
            "patterns": ["smoke*"],
            "category": "browser",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201


# ── Classification ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classification_overview(client: AsyncClient, admin_headers: dict) -> None:
    """GET /classification/overview — returns overview (empty is fine)."""
    resp = await client.get("/api/v1/classification/overview", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_classification_results(client: AsyncClient, admin_headers: dict) -> None:
    """GET /classification/results — paginated results list."""
    resp = await client.get("/api/v1/classification/results", headers=admin_headers)
    assert resp.status_code == 200
    assert "results" in resp.json()


@pytest.mark.asyncio
async def test_classification_export_csv(client: AsyncClient, admin_headers: dict) -> None:
    """GET /classification/export?format=csv — CSV export."""
    resp = await client.get(
        "/api/v1/classification/export",
        params={"format": "csv"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_classification_export_json(client: AsyncClient, admin_headers: dict) -> None:
    """GET /classification/export?format=json — JSON export."""
    resp = await client.get(
        "/api/v1/classification/export",
        params={"format": "json"},
        headers=admin_headers,
    )
    assert resp.status_code == 200


# ── Fingerprints ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fingerprints_list(client: AsyncClient, admin_headers: dict) -> None:
    """GET /fingerprints/ — list all fingerprints."""
    resp = await client.get("/api/v1/fingerprints/", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_fingerprints_crud(
    client: AsyncClient, seeded_db: object, admin_headers: dict
) -> None:
    """POST + GET /fingerprints/{group_id} — create and retrieve."""
    await _seed_agent(client, seeded_db, admin_headers)
    # Create
    resp = await client.post("/api/v1/fingerprints/smoke_group_1", headers=admin_headers)
    assert resp.status_code in (200, 201)
    fp = resp.json()
    assert fp["group_id"] == "smoke_group_1"

    # Get
    resp = await client.get("/api/v1/fingerprints/smoke_group_1", headers=admin_headers)
    assert resp.status_code == 200


# ── Tags ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tags_list(client: AsyncClient, admin_headers: dict) -> None:
    """GET /tags/ — list tag rules."""
    resp = await client.get("/api/v1/tags/", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tags_crud(client: AsyncClient, admin_headers: dict) -> None:
    """POST + GET + DELETE /tags/ — create, retrieve, delete."""
    # Create
    resp = await client.post(
        "/api/v1/tags/",
        json={"tag_name": "smoke-tag", "description": "smoke test"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    rule = resp.json()
    rule_id = rule["id"]

    # Get
    resp = await client.get(f"/api/v1/tags/{rule_id}", headers=admin_headers)
    assert resp.status_code == 200

    # Delete
    resp = await client.delete(f"/api/v1/tags/{rule_id}", headers=admin_headers)
    assert resp.status_code == 204


# ── Webhooks ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhooks_list(client: AsyncClient, admin_headers: dict) -> None:
    """GET /webhooks/ — list webhooks."""
    resp = await client.get("/api/v1/webhooks/", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhooks_crud(client: AsyncClient, admin_headers: dict) -> None:
    """POST + GET + DELETE /webhooks/ — create, retrieve, delete."""
    # Create
    resp = await client.post(
        "/api/v1/webhooks/",
        json={
            "name": "Smoke Webhook",
            "url": "https://example.com/hook",
            "events": ["sync.completed"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    wh = resp.json()
    wh_id = wh["id"]
    # Verify last_error field is present (added in audit round 4)
    assert "last_error" in wh

    # Get
    resp = await client.get(f"/api/v1/webhooks/{wh_id}", headers=admin_headers)
    assert resp.status_code == 200

    # Delete
    resp = await client.delete(f"/api/v1/webhooks/{wh_id}", headers=admin_headers)
    assert resp.status_code == 204


# ── Sync ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_status(client: AsyncClient, admin_headers: dict) -> None:
    """GET /sync/status — returns sync status."""
    resp = await client.get("/api/v1/sync/status", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sync_history(client: AsyncClient, admin_headers: dict) -> None:
    """GET /sync/history — returns sync run history."""
    resp = await client.get("/api/v1/sync/history", headers=admin_headers)
    assert resp.status_code == 200


# ── Compliance ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compliance_dashboard(client: AsyncClient, admin_headers: dict) -> None:
    """GET /compliance/dashboard — returns compliance overview."""
    resp = await client.get("/api/v1/compliance/dashboard", headers=admin_headers)
    assert resp.status_code == 200


# ── Library ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_library_list(client: AsyncClient, admin_headers: dict) -> None:
    """GET /library/ — list library entries."""
    resp = await client.get("/api/v1/library/", headers=admin_headers)
    assert resp.status_code == 200


# ── Health ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    """GET /health — basic health check (no auth)."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_deployment_info(client: AsyncClient) -> None:
    """GET /api/v1/deployment-info — public deployment info (no auth)."""
    resp = await client.get("/api/v1/deployment-info")
    assert resp.status_code == 200
    assert "deployment_mode" in resp.json()
