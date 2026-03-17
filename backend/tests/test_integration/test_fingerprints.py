"""Integration tests for the fingerprint API endpoints.

Tests run against a real (isolated test) MongoDB instance. Every public
fingerprint command and query is covered per TESTING.md requirements.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def group_id() -> str:
    """Return a stable group ID string used across fingerprint tests."""
    return "group_abc123"


@pytest_asyncio.fixture
async def fingerprint_id(client: AsyncClient, group_id: str, analyst_headers: dict) -> str:
    """Create a fingerprint for the group and return its group_id.

    Args:
        client: HTTPX async test client (injected).
        group_id: The group ID to create a fingerprint for (injected).
        analyst_headers: Auth headers for analyst role (injected).

    Returns:
        The group_id of the newly created fingerprint.
    """
    r = await client.post(f"/api/v1/fingerprints/{group_id}", headers=analyst_headers)
    assert r.status_code in (200, 201)
    return group_id


# ── TestCreateFingerprint ─────────────────────────────────────────────────────


class TestCreateFingerprint:
    """Tests for POST /api/v1/fingerprints/{group_id} — create fingerprint."""

    async def test_creates_fingerprint_for_group(
        self, client: AsyncClient, group_id: str, analyst_headers: dict
    ) -> None:
        """POSTing to a new group_id must return 201 with group_id set and empty markers."""
        r = await client.post(f"/api/v1/fingerprints/{group_id}", headers=analyst_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["group_id"] == group_id
        assert data["markers"] == []

    async def test_duplicate_returns_409(
        self, client: AsyncClient, group_id: str, analyst_headers: dict
    ) -> None:
        """Calling POST twice for the same group_id returns 409 on the second call."""
        r1 = await client.post(f"/api/v1/fingerprints/{group_id}", headers=analyst_headers)
        assert r1.status_code == 201
        r2 = await client.post(f"/api/v1/fingerprints/{group_id}", headers=analyst_headers)
        assert r2.status_code == 409

    async def test_response_shape(
        self, client: AsyncClient, group_id: str, analyst_headers: dict
    ) -> None:
        """The create response must include all required top-level fields."""
        r = await client.post(f"/api/v1/fingerprints/{group_id}", headers=analyst_headers)
        assert r.status_code in (200, 201)
        data = r.json()
        for field in (
            "id",
            "group_id",
            "group_name",
            "markers",
            "created_at",
            "updated_at",
            "created_by",
        ):
            assert field in data, f"Missing field: {field}"


# ── TestGetFingerprint ────────────────────────────────────────────────────────


class TestGetFingerprint:
    """Tests for GET /api/v1/fingerprints/{group_id} — retrieve fingerprint."""

    async def test_404_before_create(
        self, client: AsyncClient, group_id: str, admin_headers: dict
    ) -> None:
        """GETting a fingerprint for a group that has never been created must return 404."""
        r = await client.get(f"/api/v1/fingerprints/{group_id}", headers=admin_headers)
        assert r.status_code == 404

    async def test_returns_fingerprint_after_create(
        self, client: AsyncClient, fingerprint_id: str, admin_headers: dict
    ) -> None:
        """GETting a fingerprint after it has been created must return 200."""
        r = await client.get(f"/api/v1/fingerprints/{fingerprint_id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["group_id"] == fingerprint_id


# ── TestAddMarker ─────────────────────────────────────────────────────────────


class TestAddMarker:
    """Tests for POST /api/v1/fingerprints/{group_id}/markers — add a marker."""

    _marker_payload: dict = {
        "pattern": "wincc*",
        "display_name": "Siemens WinCC",
        "category": "scada_hmi",
        "weight": 1.5,
    }

    async def test_add_marker_success(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """Adding a valid marker must return 201 with the marker's pattern in the response."""
        r = await client.post(
            f"/api/v1/fingerprints/{fingerprint_id}/markers",
            json=self._marker_payload,
            headers=analyst_headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["pattern"] == "wincc*"

    async def test_marker_has_id(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """The returned marker must have a non-empty id field."""
        r = await client.post(
            f"/api/v1/fingerprints/{fingerprint_id}/markers",
            json=self._marker_payload,
            headers=analyst_headers,
        )
        assert r.status_code == 201
        assert r.json().get("id"), "Marker must have a non-empty id"

    async def test_weight_clamped_below(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """A weight of 0.0 (below the minimum 0.1) must be rejected with 422."""
        payload = {**self._marker_payload, "weight": 0.0}
        r = await client.post(
            f"/api/v1/fingerprints/{fingerprint_id}/markers",
            json=payload,
            headers=analyst_headers,
        )
        assert r.status_code == 422

    async def test_weight_clamped_above(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """A weight of 3.0 (above the maximum 2.0) must be rejected with 422."""
        payload = {**self._marker_payload, "weight": 3.0}
        r = await client.post(
            f"/api/v1/fingerprints/{fingerprint_id}/markers",
            json=payload,
            headers=analyst_headers,
        )
        assert r.status_code == 422

    async def test_multiple_markers(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """Adding 3 markers and then GETting the fingerprint must return all 3."""
        payloads = [
            {"pattern": "wincc*", "display_name": "WinCC", "category": "scada_hmi", "weight": 1.0},
            {"pattern": "step7*", "display_name": "Step 7", "category": "scada_hmi", "weight": 1.0},
            {
                "pattern": "tia portal*",
                "display_name": "TIA Portal",
                "category": "scada_hmi",
                "weight": 1.0,
            },
        ]
        for payload in payloads:
            r = await client.post(
                f"/api/v1/fingerprints/{fingerprint_id}/markers",
                json=payload,
                headers=analyst_headers,
            )
            assert r.status_code == 201

        get_r = await client.get(f"/api/v1/fingerprints/{fingerprint_id}", headers=analyst_headers)
        assert get_r.status_code == 200
        assert len(get_r.json()["markers"]) == 3


# ── TestUpdateMarker ──────────────────────────────────────────────────────────


class TestUpdateMarker:
    """Tests for PATCH /api/v1/fingerprints/{group_id}/markers/{marker_id} — update a marker."""

    async def _add_marker(
        self, client: AsyncClient, group_id: str, analyst_headers: dict, weight: float = 1.0
    ) -> str:
        """Helper: add a marker and return its id.

        Args:
            client: HTTPX async test client.
            group_id: The group to add the marker to.
            analyst_headers: Auth headers for analyst role.
            weight: Initial weight for the marker.

        Returns:
            The id of the newly created marker.
        """
        r = await client.post(
            f"/api/v1/fingerprints/{group_id}/markers",
            json={
                "pattern": "wincc*",
                "display_name": "Siemens WinCC",
                "category": "scada_hmi",
                "weight": weight,
            },
            headers=analyst_headers,
        )
        assert r.status_code == 201
        return r.json()["id"]

    async def test_update_weight(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """PATCHing the weight of a marker must persist the new value."""
        marker_id = await self._add_marker(client, fingerprint_id, analyst_headers, weight=1.0)
        r = await client.patch(
            f"/api/v1/fingerprints/{fingerprint_id}/markers/{marker_id}",
            json={"weight": 0.5},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        assert r.json()["weight"] == pytest.approx(0.5)

    async def test_update_pattern(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """PATCHing the pattern of a marker must persist the new glob string."""
        marker_id = await self._add_marker(client, fingerprint_id, analyst_headers)
        r = await client.patch(
            f"/api/v1/fingerprints/{fingerprint_id}/markers/{marker_id}",
            json={"pattern": "step7*"},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        assert r.json()["pattern"] == "step7*"


# ── TestDeleteMarker ──────────────────────────────────────────────────────────


class TestDeleteMarker:
    """Tests for DELETE /api/v1/fingerprints/{group_id}/markers/{marker_id} — remove a marker."""

    async def _add_marker(self, client: AsyncClient, group_id: str, analyst_headers: dict) -> str:
        """Helper: add a marker and return its id.

        Args:
            client: HTTPX async test client.
            group_id: The group to add the marker to.
            analyst_headers: Auth headers for analyst role.

        Returns:
            The id of the newly created marker.
        """
        r = await client.post(
            f"/api/v1/fingerprints/{group_id}/markers",
            json={
                "pattern": "wincc*",
                "display_name": "Siemens WinCC",
                "category": "scada_hmi",
                "weight": 1.0,
            },
            headers=analyst_headers,
        )
        assert r.status_code == 201
        return r.json()["id"]

    async def test_delete_marker(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """Deleting a marker and then GETting the fingerprint must show no markers."""
        marker_id = await self._add_marker(client, fingerprint_id, analyst_headers)
        r = await client.delete(
            f"/api/v1/fingerprints/{fingerprint_id}/markers/{marker_id}",
            headers=analyst_headers,
        )
        assert r.status_code == 204

        get_r = await client.get(f"/api/v1/fingerprints/{fingerprint_id}", headers=analyst_headers)
        assert get_r.status_code == 200
        assert get_r.json()["markers"] == []

    async def test_delete_nonexistent_marker(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """Attempting to delete a marker that does not exist must return 404."""
        r = await client.delete(
            f"/api/v1/fingerprints/{fingerprint_id}/markers/000000000000000000000000",
            headers=analyst_headers,
        )
        assert r.status_code == 404


# ── TestReorderMarkers ────────────────────────────────────────────────────────


class TestReorderMarkers:
    """Tests for PUT /api/v1/fingerprints/{group_id}/markers/order — reorder markers."""

    async def _add_marker(
        self, client: AsyncClient, group_id: str, pattern: str, analyst_headers: dict
    ) -> str:
        """Helper: add a marker with the given pattern and return its id.

        Args:
            client: HTTPX async test client.
            group_id: The group to add the marker to.
            pattern: Glob pattern for the marker.
            analyst_headers: Auth headers for analyst role.

        Returns:
            The id of the newly created marker.
        """
        r = await client.post(
            f"/api/v1/fingerprints/{group_id}/markers",
            json={
                "pattern": pattern,
                "display_name": pattern,
                "category": "scada_hmi",
                "weight": 1.0,
            },
            headers=analyst_headers,
        )
        assert r.status_code == 201
        return r.json()["id"]

    async def test_reorder(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """Submitting a reversed order must cause the GET to return markers in the new order."""
        id_a = await self._add_marker(client, fingerprint_id, "wincc*", analyst_headers)
        id_b = await self._add_marker(client, fingerprint_id, "step7*", analyst_headers)

        r = await client.put(
            f"/api/v1/fingerprints/{fingerprint_id}/markers/order",
            json={"marker_ids": [id_b, id_a]},
            headers=analyst_headers,
        )
        assert r.status_code == 204

        get_r = await client.get(f"/api/v1/fingerprints/{fingerprint_id}", headers=analyst_headers)
        assert get_r.status_code == 200
        returned_ids = [m["id"] for m in get_r.json()["markers"]]
        assert returned_ids == [id_b, id_a]

    async def test_reorder_invalid_ids(
        self, client: AsyncClient, fingerprint_id: str, analyst_headers: dict
    ) -> None:
        """Passing unknown marker IDs to the reorder endpoint must still return 204 (graceful)."""
        r = await client.put(
            f"/api/v1/fingerprints/{fingerprint_id}/markers/order",
            json={"marker_ids": ["000000000000000000000000", "111111111111111111111111"]},
            headers=analyst_headers,
        )
        assert r.status_code == 204


# ── TestComputeSuggestions ────────────────────────────────────────────────────


class TestComputeSuggestions:
    """Tests for the compute_suggestions function via the suggestions endpoint.

    Suggestions are at /api/v1/suggestions/{group_id} (GET = list, POST /compute = recompute).
    """

    async def test_suggestions_empty_when_no_agents(
        self, client: AsyncClient, fingerprint_id: str, admin_headers: dict
    ) -> None:
        """With no agent data, suggestions endpoint must return empty list."""
        r = await client.get(f"/api/v1/suggestions/{fingerprint_id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_suggestions_returned_after_compute(
        self,
        client: AsyncClient,
        fingerprint_id: str,
        test_db: AsyncIOMotorDatabase,
        analyst_headers: dict,  # type: ignore[type-arg]
    ) -> None:
        """After seeding agents+apps and computing suggestions, list should be non-empty.

        TF-IDF requires some agents NOT to have the app (IDF > 0), so we also seed
        one out-of-group agent with a different app.
        """
        _NOW = "2025-01-01T00:00:00"
        # 3 in-group agents with "wincc runtime"
        await test_db["agents"].insert_many(
            [
                {
                    "source": "sentinelone",
                    "source_id": f"sugg_agent_{i}",
                    "group_id": fingerprint_id,
                    "group_name": "Test Group",
                    "hostname": f"host-{i}",
                    "os_type": "windows",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        await test_db["installed_apps"].insert_many(
            [
                {
                    "agent_id": f"sugg_agent_{i}",
                    "name": "WinCC Runtime",
                    "normalized_name": "wincc runtime",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        # 1 out-of-group agent with different app (makes IDF > 0 for wincc runtime)
        await test_db["agents"].insert_one(
            {
                "source": "sentinelone",
                "source_id": "other_agent_s",
                "group_id": "other_group",
                "group_name": "Other",
                "hostname": "other",
                "os_type": "linux",
                "synced_at": _NOW,
            }
        )
        await test_db["installed_apps"].insert_one(
            {
                "agent_id": "other_agent_s",
                "name": "Linux Tool",
                "normalized_name": "linux tool",
                "synced_at": _NOW,
            }
        )

        # Trigger compute
        compute_r = await client.post(
            f"/api/v1/suggestions/{fingerprint_id}/compute", headers=analyst_headers
        )
        assert compute_r.status_code == 200
        suggestions = compute_r.json()
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1
        names = [s["normalized_name"] for s in suggestions]
        assert any("wincc" in n for n in names)

    async def test_direct_compute_suggestions(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Call compute_suggestions directly for coverage of the matcher module."""
        from domains.fingerprint.matcher import compute_suggestions

        # No agents → empty result
        result = await compute_suggestions(test_db, "no-such-group")
        assert result == []

    async def test_compute_suggestions_with_existing_marker_excluded(
        self,
        client: AsyncClient,
        fingerprint_id: str,
        test_db: AsyncIOMotorDatabase,
        analyst_headers: dict,  # type: ignore[type-arg]
    ) -> None:
        """Apps already covered by a marker pattern should be excluded from suggestions."""
        _NOW = "2025-01-01T00:00:00"
        await test_db["agents"].insert_many(
            [
                {
                    "source": "sentinelone",
                    "source_id": f"exc_agent_{i}",
                    "group_id": fingerprint_id,
                    "group_name": "Test Group",
                    "hostname": f"exc-host-{i}",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        await test_db["installed_apps"].insert_many(
            [
                {
                    "agent_id": f"exc_agent_{i}",
                    "name": "Step7 Basic",
                    "normalized_name": "step7 basic",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )

        # Add a marker that already covers "step7*"
        add_r = await client.post(
            f"/api/v1/fingerprints/{fingerprint_id}/markers",
            json={
                "pattern": "step7*",
                "display_name": "Step 7",
                "category": "scada",
                "weight": 1.0,
            },
            headers=analyst_headers,
        )
        assert add_r.status_code == 201

        compute_r = await client.post(
            f"/api/v1/suggestions/{fingerprint_id}/compute", headers=analyst_headers
        )
        assert compute_r.status_code == 200
        # step7 basic should be excluded since "step7*" already covers it
        names = [s["normalized_name"] for s in compute_r.json()]
        assert not any("step7" in n for n in names)
