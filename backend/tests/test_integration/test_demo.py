"""Integration tests for the demo data router.

Tests demo data seed, status check, and clear endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_demo_status_not_seeded(client: AsyncClient, admin_headers: dict) -> None:
    """Demo status returns seeded=False on a fresh database."""
    resp = await client.get("/api/v1/demo/status", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["seeded"] is False


@pytest.mark.asyncio
async def test_demo_seed_and_status(client: AsyncClient, admin_headers: dict) -> None:
    """Seeding demo data returns OK with counts, then status shows seeded=True."""
    seed_resp = await client.post("/api/v1/demo/seed", headers=admin_headers)
    assert seed_resp.status_code == 200
    data = seed_resp.json()
    assert data["status"] == "ok"
    assert "counts" in data

    status_resp = await client.get("/api/v1/demo/status", headers=admin_headers)
    assert status_resp.json()["seeded"] is True


@pytest.mark.asyncio
async def test_demo_clear(client: AsyncClient, admin_headers: dict) -> None:
    """Clearing demo data returns cleared status."""
    # Seed first
    await client.post("/api/v1/demo/seed", headers=admin_headers)
    # Clear
    clear_resp = await client.delete("/api/v1/demo/seed", headers=admin_headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "cleared"


@pytest.mark.asyncio
async def test_demo_requires_admin(client: AsyncClient, analyst_headers: dict) -> None:
    """Non-admin roles cannot access demo endpoints."""
    resp = await client.get("/api/v1/demo/status", headers=analyst_headers)
    assert resp.status_code == 403
