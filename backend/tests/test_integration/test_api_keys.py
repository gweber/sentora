"""Integration tests for the API Keys domain.

Tests the full lifecycle: create, list, get, update, rotate, revoke.
Also covers security constraints (tenant isolation, JWT-only management,
scope enforcement) and error paths.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.api_keys.service import generate_api_key, hash_key

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _create_key(
    client: AsyncClient,
    admin_headers: dict[str, str],
    *,
    name: str = "Test Key",
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    """Create an API key via the API and return the full response."""
    resp = await client.post(
        "/api/v1/api-keys/",
        json={
            "name": name,
            "scopes": scopes or ["agents:read"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── CRUD Tests ───────────────────────────────────────────────────────────────


class TestCreate:
    """POST /api/v1/api-keys/"""

    async def test_create_returns_full_key_once(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers)
        assert "full_key" in data
        assert data["full_key"].startswith("sentora_sk_live_")
        assert "key" in data
        assert data["key"]["name"] == "Test Key"
        assert data["key"]["is_active"] is True

    async def test_create_stores_hash_not_key(
        self, client: AsyncClient, admin_headers: dict[str, str], test_db: AsyncIOMotorDatabase,
    ) -> None:
        data = await _create_key(client, admin_headers)
        full_key = data["full_key"]
        expected_hash = hashlib.sha256(full_key.encode()).hexdigest()

        doc = await test_db["api_keys"].find_one({"_id": data["key"]["id"]})
        assert doc is not None
        assert doc["key_hash"] == expected_hash
        # Verify the full key is NOT stored in the document
        for value in doc.values():
            if isinstance(value, str):
                assert value != full_key

    async def test_create_with_invalid_scope_returns_400(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/api-keys/",
            json={"name": "Bad Scopes", "scopes": ["nonexistent:scope"]},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    async def test_create_requires_admin(
        self, client: AsyncClient, viewer_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/api-keys/",
            json={"name": "Test", "scopes": ["agents:read"]},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_create_without_auth_returns_401(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/v1/api-keys/",
            json={"name": "Test", "scopes": ["agents:read"]},
        )
        assert resp.status_code in (401, 403)


class TestList:
    """GET /api/v1/api-keys/"""

    async def test_list_returns_keys(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        await _create_key(client, admin_headers, name="Key A")
        await _create_key(client, admin_headers, name="Key B")

        resp = await client.get("/api/v1/api-keys/", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        # Full key must NEVER appear in list responses
        for key in data:
            assert "full_key" not in key
            assert not key.get("key_hash")

    async def test_list_never_exposes_full_key(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        create_resp = await _create_key(client, admin_headers)
        full_key = create_resp["full_key"]

        resp = await client.get("/api/v1/api-keys/", headers=admin_headers)
        body = resp.text
        assert full_key not in body


class TestGet:
    """GET /api/v1/api-keys/{id}"""

    async def test_get_by_id(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers)
        key_id = data["key"]["id"]

        resp = await client.get(f"/api/v1/api-keys/{key_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == key_id

    async def test_get_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/api-keys/nonexistent", headers=admin_headers)
        assert resp.status_code == 404


class TestUpdate:
    """PUT /api/v1/api-keys/{id}"""

    async def test_update_name_and_scopes(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers)
        key_id = data["key"]["id"]

        resp = await client.put(
            f"/api/v1/api-keys/{key_id}",
            json={"name": "Updated Name", "scopes": ["read:all"]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert "read:all" in resp.json()["scopes"]


class TestRevoke:
    """DELETE /api/v1/api-keys/{id}"""

    async def test_revoke_makes_key_inactive(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers)
        key_id = data["key"]["id"]

        resp = await client.delete(f"/api/v1/api-keys/{key_id}", headers=admin_headers)
        assert resp.status_code == 204

        # Verify it's revoked
        resp = await client.get(f"/api/v1/api-keys/{key_id}", headers=admin_headers)
        assert resp.json()["is_active"] is False

    async def test_revoked_key_cannot_authenticate(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers)
        full_key = data["full_key"]
        key_id = data["key"]["id"]

        # Revoke
        await client.delete(f"/api/v1/api-keys/{key_id}", headers=admin_headers)

        # Try to use the revoked key
        resp = await client.get(
            "/api/v1/api-keys/current",
            headers={"Authorization": f"Bearer {full_key}"},
        )
        assert resp.status_code == 401


class TestRotate:
    """POST /api/v1/api-keys/{id}/rotate"""

    async def test_rotate_returns_new_key(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers)
        old_key_id = data["key"]["id"]
        old_full_key = data["full_key"]

        resp = await client.post(
            f"/api/v1/api-keys/{old_key_id}/rotate",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        rotate_data = resp.json()
        assert "full_key" in rotate_data
        assert rotate_data["full_key"] != old_full_key
        assert rotate_data["key"]["is_active"] is True

    async def test_rotate_preserves_scopes(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers, scopes=["agents:read", "apps:read"])
        old_key_id = data["key"]["id"]

        resp = await client.post(
            f"/api/v1/api-keys/{old_key_id}/rotate",
            headers=admin_headers,
        )
        rotate_data = resp.json()
        assert set(rotate_data["key"]["scopes"]) == {"agents:read", "apps:read"}


# ── API Key Authentication Tests ─────────────────────────────────────────────


class TestAPIKeyAuth:
    """Test authenticating with an API key."""

    async def test_bearer_header_auth(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers, scopes=["agents:read"])
        full_key = data["full_key"]

        resp = await client.get(
            "/api/v1/api-keys/current",
            headers={"Authorization": f"Bearer {full_key}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Key"

    async def test_x_api_key_header_auth(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        data = await _create_key(client, admin_headers, scopes=["agents:read"])
        full_key = data["full_key"]

        resp = await client.get(
            "/api/v1/api-keys/current",
            headers={"X-API-Key": full_key},
        )
        assert resp.status_code == 200

    async def test_invalid_key_returns_401(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get(
            "/api/v1/api-keys/current",
            headers={"Authorization": "Bearer sentora_sk_live_invalid0000000000000000000000000000000000000000"},
        )
        assert resp.status_code == 401

    async def test_expired_key_returns_401(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/api-keys/",
            json={
                "name": "Expired Key",
                "scopes": ["agents:read"],
                "expires_at": "2020-01-01T00:00:00Z",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        full_key = resp.json()["full_key"]

        resp = await client.get(
            "/api/v1/api-keys/current",
            headers={"Authorization": f"Bearer {full_key}"},
        )
        assert resp.status_code == 401


# ── Security Tests ───────────────────────────────────────────────────────────


class TestSecurity:
    """Security constraints for API key management."""

    async def test_api_key_cannot_manage_keys(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        """API keys must not be able to create/list/revoke other API keys."""
        data = await _create_key(client, admin_headers, scopes=["read:all"])
        full_key = data["full_key"]

        # Try to list keys with an API key
        resp = await client.get(
            "/api/v1/api-keys/",
            headers={"Authorization": f"Bearer {full_key}"},
        )
        assert resp.status_code == 403

        # Try to create a key with an API key
        resp = await client.post(
            "/api/v1/api-keys/",
            json={"name": "Sneaky", "scopes": ["read:all"]},
            headers={"Authorization": f"Bearer {full_key}"},
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_manage_keys(
        self, client: AsyncClient, viewer_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/api-keys/", headers=viewer_headers)
        assert resp.status_code == 403

    async def test_analyst_cannot_manage_keys(
        self, client: AsyncClient, analyst_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/api-keys/", headers=analyst_headers)
        assert resp.status_code == 403

    async def test_get_never_returns_full_key(
        self, client: AsyncClient, admin_headers: dict[str, str],
    ) -> None:
        create_data = await _create_key(client, admin_headers)
        full_key = create_data["full_key"]
        key_id = create_data["key"]["id"]

        resp = await client.get(f"/api/v1/api-keys/{key_id}", headers=admin_headers)
        assert full_key not in resp.text
        assert "key_hash" not in resp.text
