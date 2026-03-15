"""Integration tests for the tenant management domain.

Tests tenant CRUD endpoints via the HTTP API with multi-tenancy enabled
and disabled. All endpoints require super_admin role.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

# ── Helpers ─────────────────────────────────────────────────────────────────


def _enable_multi_tenancy() -> object:
    """Context manager that temporarily enables multi-tenancy in settings."""
    return patch(
        "domains.tenant.router.get_settings",
        return_value=_make_settings(multi_tenancy_enabled=True),
    )


def _make_settings(**overrides: object) -> MagicMock:
    """Build a mock settings object with sensible defaults."""

    s = MagicMock()
    s.multi_tenancy_enabled = overrides.get("multi_tenancy_enabled", False)
    s.master_db_name = "sentora_test"
    s.mongo_db = "sentora_test"
    return s


# ── Multi-tenancy disabled (default) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tenants_disabled(client: AsyncClient, super_admin_headers: dict) -> None:
    """Tenant endpoints return 404 when multi-tenancy is disabled."""
    resp = await client.get("/api/v1/tenants/", headers=super_admin_headers)
    assert resp.status_code == 404
    assert "not enabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_tenant_disabled(client: AsyncClient, super_admin_headers: dict) -> None:
    """Cannot create tenant when multi-tenancy is disabled."""
    resp = await client.post(
        "/api/v1/tenants/",
        json={"name": "Acme Corp", "slug": "acme"},
        headers=super_admin_headers,
    )
    assert resp.status_code == 404


# ── Multi-tenancy enabled ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_list_tenants(client: AsyncClient, super_admin_headers: dict) -> None:
    """Create a tenant and verify it appears in the list."""
    with _enable_multi_tenancy():
        create_resp = await client.post(
            "/api/v1/tenants/",
            json={"name": "Acme Corp", "slug": "acme"},
            headers=super_admin_headers,
        )
        assert create_resp.status_code == 201
        tenant = create_resp.json()
        assert tenant["name"] == "Acme Corp"
        assert tenant["slug"] == "acme"
        assert tenant["database_name"] == "sentora_tenant_acme"
        assert tenant["disabled"] is False
        assert tenant["plan"] == "standard"

        # List should include the new tenant
        list_resp = await client.get("/api/v1/tenants/", headers=super_admin_headers)
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] >= 1
        slugs = [t["slug"] for t in data["tenants"]]
        assert "acme" in slugs


@pytest.mark.asyncio
async def test_get_tenant_by_slug(client: AsyncClient, super_admin_headers: dict) -> None:
    """Get a tenant by slug returns the tenant."""
    with _enable_multi_tenancy():
        await client.post(
            "/api/v1/tenants/",
            json={"name": "Beta Inc", "slug": "beta"},
            headers=super_admin_headers,
        )
        resp = await client.get("/api/v1/tenants/beta", headers=super_admin_headers)
        assert resp.status_code == 200
        assert resp.json()["slug"] == "beta"


@pytest.mark.asyncio
async def test_get_tenant_not_found(client: AsyncClient, super_admin_headers: dict) -> None:
    """Get nonexistent tenant returns 404."""
    with _enable_multi_tenancy():
        resp = await client.get("/api/v1/tenants/nonexistent", headers=super_admin_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_slug(client: AsyncClient, super_admin_headers: dict) -> None:
    """Creating tenant with duplicate slug returns 409."""
    with _enable_multi_tenancy():
        await client.post(
            "/api/v1/tenants/",
            json={"name": "Gamma", "slug": "gamma"},
            headers=super_admin_headers,
        )
        resp = await client.post(
            "/api/v1/tenants/",
            json={"name": "Gamma Duplicate", "slug": "gamma"},
            headers=super_admin_headers,
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_tenant(client: AsyncClient, super_admin_headers: dict) -> None:
    """Patch a tenant's name."""
    with _enable_multi_tenancy():
        await client.post(
            "/api/v1/tenants/",
            json={"name": "Delta Corp", "slug": "delta"},
            headers=super_admin_headers,
        )
        resp = await client.patch(
            "/api/v1/tenants/delta",
            json={"name": "Delta Inc"},
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Delta Inc"


@pytest.mark.asyncio
async def test_update_tenant_empty_body(client: AsyncClient, super_admin_headers: dict) -> None:
    """Patch with empty body returns 400."""
    with _enable_multi_tenancy():
        await client.post(
            "/api/v1/tenants/",
            json={"name": "Epsilon", "slug": "epsilon"},
            headers=super_admin_headers,
        )
        resp = await client.patch(
            "/api/v1/tenants/epsilon",
            json={},
            headers=super_admin_headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_tenant(client: AsyncClient, super_admin_headers: dict) -> None:
    """Delete a tenant removes it from the registry."""
    with _enable_multi_tenancy():
        await client.post(
            "/api/v1/tenants/",
            json={"name": "Zeta", "slug": "zeta"},
            headers=super_admin_headers,
        )
        del_resp = await client.delete("/api/v1/tenants/zeta", headers=super_admin_headers)
        assert del_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get("/api/v1/tenants/zeta", headers=super_admin_headers)
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_tenant_not_found(client: AsyncClient, super_admin_headers: dict) -> None:
    """Delete nonexistent tenant returns 404."""
    with _enable_multi_tenancy():
        resp = await client.delete("/api/v1/tenants/nonexistent", headers=super_admin_headers)
        assert resp.status_code == 404


# ── Auth enforcement ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenant_requires_super_admin(client: AsyncClient, admin_headers: dict) -> None:
    """Admin role (not super_admin) cannot access tenant endpoints."""
    with _enable_multi_tenancy():
        resp = await client.get("/api/v1/tenants/", headers=admin_headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tenant_unauthenticated(client: AsyncClient) -> None:
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/v1/tenants/")
    assert resp.status_code == 401
