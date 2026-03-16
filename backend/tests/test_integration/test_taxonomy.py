"""Integration tests for the taxonomy API endpoints.

Tests run against a real (isolated test) MongoDB instance with seed data.
Every public query and command is covered per TESTING.md requirements.
"""

from __future__ import annotations

from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase


class TestListCategories:
    """Tests for GET /api/v1/taxonomy/ — list all categories."""

    async def test_returns_seeded_categories(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Seeded taxonomy has 8 categories — all must appear in the response."""
        response = await client.get("/api/v1/taxonomy/", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 8
        keys = {c["key"] for c in data["categories"]}
        assert "scada_hmi" in keys
        assert "labeling_barcode" in keys
        assert "water_treatment_environmental" in keys

    async def test_categories_have_entry_counts(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Each category must have a positive entry_count."""
        response = await client.get("/api/v1/taxonomy/", headers=admin_headers)
        assert response.status_code == 200
        for cat in response.json()["categories"]:
            assert cat["entry_count"] > 0, f"Category {cat['key']} has no entries"

    async def test_categories_sorted_by_display(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Categories must be sorted alphabetically by display name."""
        response = await client.get("/api/v1/taxonomy/", headers=admin_headers)
        assert response.status_code == 200
        displays = [c["display"] for c in response.json()["categories"]]
        assert displays == sorted(displays)


class TestGetEntriesByCategory:
    """Tests for GET /api/v1/taxonomy/category/{category}."""

    async def test_returns_entries_for_scada_hmi(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """The scada_hmi category must have at least 10 entries after seeding."""
        response = await client.get("/api/v1/taxonomy/category/scada_hmi", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 10
        assert len(data["entries"]) == data["total"]

    async def test_empty_category_returns_empty_list(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Requesting a nonexistent category returns an empty list, not a 404."""
        response = await client.get(
            "/api/v1/taxonomy/category/nonexistent_category", headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["entries"] == []

    async def test_entry_shape(self, client: AsyncClient, admin_headers: dict) -> None:
        """Every entry in the response must have all required fields."""
        response = await client.get(
            "/api/v1/taxonomy/category/labeling_barcode", headers=admin_headers
        )
        assert response.status_code == 200
        for entry in response.json()["entries"]:
            assert "id" in entry
            assert "name" in entry
            assert "patterns" in entry
            assert isinstance(entry["patterns"], list)
            assert "category" in entry
            assert "is_universal" in entry
            assert "user_added" in entry


class TestSearchTaxonomy:
    """Tests for GET /api/v1/taxonomy/search."""

    async def test_finds_wincc_by_name(self, client: AsyncClient, admin_headers: dict) -> None:
        """Searching for 'WinCC' must return the Siemens WinCC entry."""
        response = await client.get(
            "/api/v1/taxonomy/search", params={"q": "WinCC"}, headers=admin_headers
        )
        assert response.status_code == 200
        entries = response.json()["entries"]
        assert any("WinCC" in e["name"] for e in entries)

    async def test_search_is_case_insensitive(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Search must be case-insensitive ('wincc' == 'WinCC')."""
        r1 = await client.get(
            "/api/v1/taxonomy/search", params={"q": "wincc"}, headers=admin_headers
        )
        r2 = await client.get(
            "/api/v1/taxonomy/search", params={"q": "WINCC"}, headers=admin_headers
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        names1 = {e["name"] for e in r1.json()["entries"]}
        names2 = {e["name"] for e in r2.json()["entries"]}
        assert names1 == names2

    async def test_no_results_for_gibberish(self, client: AsyncClient, admin_headers: dict) -> None:
        """Searching for a nonexistent string must return an empty list."""
        response = await client.get(
            "/api/v1/taxonomy/search", params={"q": "xyzzy_no_such_app_1234"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_missing_q_param_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Omitting the required ``q`` parameter must return HTTP 422."""
        response = await client.get("/api/v1/taxonomy/search", headers=admin_headers)
        assert response.status_code == 422


class TestAddEntry:
    """Tests for POST /api/v1/taxonomy/ — create a new entry."""

    async def test_creates_entry_and_returns_201(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """A valid payload must create an entry and return HTTP 201."""
        payload = {
            "name": "My Custom Software",
            "patterns": ["custom*software*"],
            "category": "test_category",
            "category_display": "Test",
            "industry": ["testing"],
            "is_universal": False,
        }
        response = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Custom Software"
        assert data["user_added"] is True
        assert data["id"]

    async def test_created_entry_is_retrievable(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """After creation, the entry must appear in category search results."""
        payload = {
            "name": "Retrievable App",
            "patterns": ["retrievable*"],
            "category": "custom_cat",
            "category_display": "Custom",
            "industry": [],
            "is_universal": False,
        }
        create_resp = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert create_resp.status_code == 201

        search_resp = await client.get(
            "/api/v1/taxonomy/search", params={"q": "Retrievable App"}, headers=analyst_headers
        )
        assert search_resp.status_code == 200
        assert any(e["name"] == "Retrievable App" for e in search_resp.json()["entries"])

    async def test_missing_name_returns_422(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Omitting the required ``name`` field must return HTTP 422."""
        payload = {"patterns": ["test*"], "category": "cat"}
        response = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert response.status_code == 422

    async def test_empty_patterns_returns_422(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """An empty ``patterns`` list must be rejected with HTTP 422."""
        payload = {"name": "Bad Entry", "patterns": [], "category": "cat"}
        response = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert response.status_code == 422


class TestEditEntry:
    """Tests for PATCH /api/v1/taxonomy/{entry_id}."""

    async def _create_entry(self, client: AsyncClient, analyst_headers: dict) -> str:
        """Helper: create a test entry and return its ID."""
        payload = {
            "name": "Entry To Edit",
            "patterns": ["editable*"],
            "category": "edit_cat",
            "category_display": "Edit",
            "industry": [],
            "is_universal": False,
        }
        resp = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_can_update_name(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Patching ``name`` must update only the name field."""
        entry_id = await self._create_entry(client, analyst_headers)
        response = await client.patch(
            f"/api/v1/taxonomy/{entry_id}",
            json={"name": "Renamed Entry"},
            headers=analyst_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed Entry"

    async def test_nonexistent_entry_returns_404(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Patching a nonexistent ID must return HTTP 404."""
        response = await client.patch(
            "/api/v1/taxonomy/000000000000000000000000",
            json={"name": "Ghost"},
            headers=analyst_headers,
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "TAXONOMY_ENTRY_NOT_FOUND"


class TestDeleteEntry:
    """Tests for DELETE /api/v1/taxonomy/{entry_id}."""

    async def _create_entry(self, client: AsyncClient, analyst_headers: dict) -> str:
        """Helper: create a test entry and return its ID."""
        payload = {
            "name": "Entry To Delete",
            "patterns": ["deletable*"],
            "category": "del_cat",
            "category_display": "Del",
            "industry": [],
            "is_universal": False,
        }
        resp = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    async def test_deletes_and_returns_204(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Deleting an existing entry must return HTTP 204."""
        entry_id = await self._create_entry(client, analyst_headers)
        response = await client.delete(f"/api/v1/taxonomy/{entry_id}", headers=analyst_headers)
        assert response.status_code == 204

    async def test_deleted_entry_not_retrievable(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """After deletion the entry must not appear in search."""
        entry_id = await self._create_entry(client, analyst_headers)
        await client.delete(f"/api/v1/taxonomy/{entry_id}", headers=analyst_headers)
        search = await client.get(
            "/api/v1/taxonomy/search", params={"q": "Entry To Delete"}, headers=analyst_headers
        )
        assert all(e["id"] != entry_id for e in search.json()["entries"])

    async def test_nonexistent_entry_returns_404(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Deleting a nonexistent ID must return HTTP 404."""
        response = await client.delete(
            "/api/v1/taxonomy/000000000000000000000000", headers=analyst_headers
        )
        assert response.status_code == 404
        assert response.json()["error_code"] == "TAXONOMY_ENTRY_NOT_FOUND"


class TestToggleUniversal:
    """Tests for POST /api/v1/taxonomy/{entry_id}/toggle-universal."""

    async def test_toggles_flag(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Toggling universal on a non-universal entry must set it to True."""
        payload = {
            "name": "Toggle App",
            "patterns": ["toggle*"],
            "category": "toggle_cat",
            "category_display": "Toggle",
            "industry": [],
            "is_universal": False,
        }
        create = await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        assert create.status_code == 201
        entry_id = create.json()["id"]
        assert create.json()["is_universal"] is False

        toggle = await client.post(
            f"/api/v1/taxonomy/{entry_id}/toggle-universal", headers=analyst_headers
        )
        assert toggle.status_code == 200
        assert toggle.json()["is_universal"] is True

    async def test_double_toggle_restores_original(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Toggling twice must restore the original value (idempotent pair)."""
        payload = {
            "name": "Double Toggle App",
            "patterns": ["double*toggle*"],
            "category": "t_cat",
            "category_display": "T",
            "industry": [],
            "is_universal": False,
        }
        entry_id = (
            await client.post("/api/v1/taxonomy/", json=payload, headers=analyst_headers)
        ).json()["id"]

        await client.post(f"/api/v1/taxonomy/{entry_id}/toggle-universal", headers=analyst_headers)
        second = await client.post(
            f"/api/v1/taxonomy/{entry_id}/toggle-universal", headers=analyst_headers
        )
        assert second.json()["is_universal"] is False


# ── TestGetEntryById ───────────────────────────────────────────────────────────


class TestGetEntryById:
    """Tests for GET /api/v1/taxonomy/{entry_id} — single entry lookup."""

    async def test_returns_entry(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Created entry must be retrievable by its ID."""
        create = await client.post(
            "/api/v1/taxonomy/",
            json={
                "name": "Lookup App",
                "patterns": ["lookup*"],
                "category": "scada_hmi",
                "category_display": "SCADA HMI",
                "industry": [],
                "is_universal": False,
            },
            headers=analyst_headers,
        )
        assert create.status_code == 201
        entry_id = create.json()["id"]

        r = await client.get(f"/api/v1/taxonomy/{entry_id}", headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "Lookup App"

    async def test_returns_404_for_unknown_id(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.get("/api/v1/taxonomy/000000000000000000000000", headers=admin_headers)
        assert r.status_code == 404


# ── TestPatternPreview ────────────────────────────────────────────────────────


class TestPatternPreview:
    """Tests for POST /api/v1/taxonomy/preview — pattern preview."""

    async def test_preview_returns_empty_when_no_apps(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.post(
            "/api/v1/taxonomy/preview", json={"pattern": "wincc*"}, headers=admin_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_apps"] == 0
        assert data["total_agents"] == 0
        assert data["app_matches"] == []

    async def test_preview_matches_installed_app(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
        admin_headers: dict,  # type: ignore[type-arg]
    ) -> None:
        """Pattern preview should find apps in app_summaries and agents in s1_agents."""
        # Insert an app summary that matches the pattern
        await test_db["app_summaries"].insert_one(
            {
                "normalized_name": "wincc runtime",
                "display_name": "WinCC Runtime",
                "publisher": "Siemens",
                "agent_count": 3,
            }
        )
        # Insert an agent that has the matching app installed
        await test_db["s1_agents"].insert_one(
            {
                "s1_agent_id": "agent-preview-1",
                "hostname": "preview-host",
                "group_name": "Test",
                "group_id": "g1",
                "site_name": "Site",
                "os_type": "windows",
                "installed_app_names": ["wincc runtime"],
            }
        )

        r = await client.post(
            "/api/v1/taxonomy/preview", json={"pattern": "wincc*"}, headers=admin_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_apps"] >= 1
        assert data["total_agents"] >= 1
        assert len(data["app_matches"]) >= 1
        assert data["app_matches"][0]["normalized_name"] == "wincc runtime"

    async def test_preview_multi_pattern(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
        admin_headers: dict,  # type: ignore[type-arg]
    ) -> None:
        """Multi-pattern preview should OR-combine patterns."""
        await test_db["app_summaries"].insert_many(
            [
                {
                    "normalized_name": "wincc runtime",
                    "display_name": "WinCC Runtime",
                    "publisher": "Siemens",
                    "agent_count": 2,
                },
                {
                    "normalized_name": "factorytalk view",
                    "display_name": "FactoryTalk View",
                    "publisher": "Rockwell",
                    "agent_count": 1,
                },
            ]
        )

        r = await client.post(
            "/api/v1/taxonomy/preview",
            json={"patterns": ["wincc*", "factorytalk*"]},
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_apps"] == 2
        names = {m["normalized_name"] for m in data["app_matches"]}
        assert "wincc runtime" in names
        assert "factorytalk view" in names

    async def test_preview_no_match_returns_zero(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.post(
            "/api/v1/taxonomy/preview", json={"pattern": "zzz_nomatch*"}, headers=admin_headers
        )
        assert r.status_code == 200
        assert r.json()["total_apps"] == 0


# ── TestCategoryManagement ────────────────────────────────────────────────────


class TestCategoryManagement:
    """Tests for PATCH and DELETE category endpoints."""

    async def test_update_category_display(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Updating a category's display name should change it in listings."""
        r = await client.patch(
            "/api/v1/taxonomy/category/scada_hmi",
            json={"display": "Updated SCADA HMI"},
            headers=analyst_headers,
        )
        assert r.status_code == 200
        assert r.json()["display"] == "Updated SCADA HMI"

    async def test_update_category_not_found(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Updating a non-existent category raises TaxonomyError (500)."""
        r = await client.patch(
            "/api/v1/taxonomy/category/nonexistent_cat",
            json={"display": "Should Fail"},
            headers=analyst_headers,
        )
        assert r.status_code == 500

    async def test_delete_category(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Deleting a category should remove its entries."""
        create = await client.post(
            "/api/v1/taxonomy/",
            json={
                "name": "Delete Me",
                "patterns": ["delete*me*"],
                "category": "cat_to_delete",
                "category_display": "Delete This Cat",
                "industry": [],
                "is_universal": False,
            },
            headers=analyst_headers,
        )
        assert create.status_code == 201

        r = await client.delete("/api/v1/taxonomy/category/cat_to_delete", headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["entries_deleted"] >= 1

    async def test_delete_category_not_found(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Deleting a non-existent category raises TaxonomyError (500)."""
        r = await client.delete(
            "/api/v1/taxonomy/category/nonexistent_cat", headers=analyst_headers
        )
        assert r.status_code == 500
