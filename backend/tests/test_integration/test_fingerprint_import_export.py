"""Integration tests for fingerprint import/export API endpoints.

Tests run against a real (isolated test) MongoDB instance. Covers the
export (GET /api/v1/fingerprints/export) and import
(POST /api/v1/fingerprints/import) endpoints.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

# ── Fixtures ──────────────────────────────────────────────────────────────────


GROUP_ID = "ie_test_group_1"


@pytest_asyncio.fixture
async def group_with_fingerprint(
    client: AsyncClient, test_db: AsyncIOMotorDatabase, analyst_headers: dict
) -> str:
    """Insert a group into s1_groups, create a fingerprint, add a marker, return group_id.

    Args:
        client: HTTPX async test client (injected).
        test_db: Isolated test database (injected).
        analyst_headers: Auth headers for analyst role (injected).

    Returns:
        The group_id of the created fingerprint.
    """
    await test_db["s1_groups"].insert_one(
        {
            "s1_group_id": GROUP_ID,
            "name": "Import Export Test Group",
            "site_name": "Default Site",
        }
    )

    r = await client.post(f"/api/v1/fingerprints/{GROUP_ID}", headers=analyst_headers)
    assert r.status_code == 201

    marker_r = await client.post(
        f"/api/v1/fingerprints/{GROUP_ID}/markers",
        json={
            "pattern": "wincc*",
            "display_name": "Siemens WinCC",
            "category": "scada_hmi",
            "weight": 1.5,
            "source": "manual",
        },
        headers=analyst_headers,
    )
    assert marker_r.status_code == 201

    return GROUP_ID


# ── TestFingerprintExport ─────────────────────────────────────────────────────


class TestFingerprintExport:
    """Tests for GET /api/v1/fingerprints/export — export all fingerprints."""

    async def test_export_empty(self, client: AsyncClient, analyst_headers: dict) -> None:
        """When no fingerprints exist, export returns an empty JSON array."""
        r = await client.get("/api/v1/fingerprints/export", headers=analyst_headers)
        assert r.status_code == 200
        assert r.headers["content-disposition"] == 'attachment; filename="fingerprints_export.json"'
        data = json.loads(r.content)
        assert data == []

    async def test_export_with_data(
        self, client: AsyncClient, analyst_headers: dict, group_with_fingerprint: str
    ) -> None:
        """After creating a fingerprint with a marker, export returns the correct structure."""
        r = await client.get("/api/v1/fingerprints/export", headers=analyst_headers)
        assert r.status_code == 200
        assert r.headers["content-disposition"] == 'attachment; filename="fingerprints_export.json"'

        data = json.loads(r.content)
        assert isinstance(data, list)
        assert len(data) >= 1

        # Find our group in the export
        exported = [item for item in data if item["group_id"] == group_with_fingerprint]
        assert len(exported) == 1
        item = exported[0]

        assert "group_id" in item
        assert "markers" in item
        assert isinstance(item["markers"], list)
        assert len(item["markers"]) == 1

        marker = item["markers"][0]
        assert marker["pattern"] == "wincc*"
        assert marker["display_name"] == "Siemens WinCC"
        assert marker["category"] == "scada_hmi"
        assert marker["weight"] == pytest.approx(1.5)
        assert marker["source"] == "manual"
        assert "confidence" in marker

    async def test_export_requires_auth(self, client: AsyncClient) -> None:
        """Export without auth headers must return 401."""
        r = await client.get("/api/v1/fingerprints/export")
        assert r.status_code == 401


# ── TestFingerprintImport ─────────────────────────────────────────────────────


class TestFingerprintImport:
    """Tests for POST /api/v1/fingerprints/import — import fingerprints."""

    async def test_import_creates_fingerprint(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
        admin_headers: dict,
    ) -> None:
        """Importing markers for an existing group creates the fingerprint."""
        group_id = "import_target_group"
        await test_db["s1_groups"].insert_one(
            {
                "s1_group_id": group_id,
                "name": "Import Target Group",
                "site_name": "Default Site",
            }
        )

        payload = {
            "items": [
                {
                    "group_id": group_id,
                    "markers": [
                        {
                            "pattern": "step7*",
                            "display_name": "Siemens Step 7",
                            "category": "scada_hmi",
                            "weight": 1.0,
                            "source": "manual",
                            "confidence": 0.9,
                        },
                    ],
                }
            ]
        }

        r = await client.post(
            "/api/v1/fingerprints/import",
            json=payload,
            params={"strategy": "merge"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 1
        assert data["skipped"] == 0
        assert data["errors"] == []

        # Verify the fingerprint was actually created
        get_r = await client.get(f"/api/v1/fingerprints/{group_id}", headers=admin_headers)
        assert get_r.status_code == 200
        markers = get_r.json()["markers"]
        assert len(markers) >= 1
        patterns = [m["pattern"] for m in markers]
        assert "step7*" in patterns

    async def test_import_requires_admin(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Import with analyst role must return 403 (admin required)."""
        payload = {
            "items": [
                {
                    "group_id": "any_group",
                    "markers": [
                        {
                            "pattern": "test*",
                            "display_name": "Test",
                            "category": "test",
                            "weight": 1.0,
                            "source": "manual",
                            "confidence": 1.0,
                        },
                    ],
                }
            ]
        }
        r = await client.post(
            "/api/v1/fingerprints/import",
            json=payload,
            headers=analyst_headers,
        )
        assert r.status_code == 403

    async def test_import_empty_items_422(self, client: AsyncClient, admin_headers: dict) -> None:
        """Importing with an empty items list must return 422 validation error."""
        r = await client.post(
            "/api/v1/fingerprints/import",
            json={"items": []},
            headers=admin_headers,
        )
        assert r.status_code == 422
