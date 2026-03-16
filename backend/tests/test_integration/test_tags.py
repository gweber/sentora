"""Integration tests for the tags API endpoints.

Tests run against a real (isolated test) MongoDB instance. All public
tag endpoints are covered: CRUD for rules and patterns, preview, and apply
(with a monkeypatched S1Client._post so no real HTTP calls are made).
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _wait_for_apply(
    client: AsyncClient, rule_id: str, headers: dict | None = None, timeout: float = 10.0
) -> None:
    """Poll GET /{rule_id} until apply_status is no longer 'running'.

    The background _run_apply task sets apply_status to 'done' or 'failed' when
    finished. We poll until the status reflects the completed state so we don't
    leave a running asyncio task that bleeds into the next test's fresh DB.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        r = await client.get(f"/api/v1/tags/{rule_id}", headers=headers)
        if r.status_code == 200 and r.json().get("apply_status") in ("done", "failed"):
            return
        await asyncio.sleep(0.2)
    raise AssertionError(f"apply_status did not settle within {timeout}s")


def _rule_payload(tag_name: str = "manufacturing", description: str = "") -> dict:
    return {"tag_name": tag_name, "description": description}


def _pattern_payload(pattern: str = "siemens*", display_name: str = "Siemens") -> dict:
    return {"pattern": pattern, "display_name": display_name, "category": "scada_hmi"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def rule_id(client: AsyncClient, analyst_headers: dict) -> str:
    """Create a tag rule and return its id."""
    r = await client.post("/api/v1/tags/", json=_rule_payload(), headers=analyst_headers)
    assert r.status_code == 201
    return r.json()["id"]


@pytest_asyncio.fixture
async def rule_with_pattern(
    client: AsyncClient, rule_id: str, analyst_headers: dict
) -> tuple[str, str]:
    """Return (rule_id, pattern_id) after adding a pattern to the rule."""
    r = await client.post(
        f"/api/v1/tags/{rule_id}/patterns", json=_pattern_payload(), headers=analyst_headers
    )
    assert r.status_code == 201
    return rule_id, r.json()["id"]


# ── TestCreateTagRule ─────────────────────────────────────────────────────────


class TestCreateTagRule:
    async def test_creates_rule(self, client: AsyncClient, analyst_headers: dict) -> None:
        r = await client.post("/api/v1/tags/", json=_rule_payload(), headers=analyst_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["tag_name"] == "manufacturing"
        assert data["patterns"] == []
        assert data["apply_status"] == "idle"

    async def test_response_shape(self, client: AsyncClient, analyst_headers: dict) -> None:
        r = await client.post("/api/v1/tags/", json=_rule_payload(), headers=analyst_headers)
        assert r.status_code == 201
        data = r.json()
        for field in (
            "id",
            "tag_name",
            "description",
            "patterns",
            "apply_status",
            "last_applied_at",
            "last_applied_count",
            "created_at",
            "updated_at",
            "created_by",
        ):
            assert field in data, f"Missing field: {field}"

    async def test_duplicate_tag_name_returns_409(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        await client.post("/api/v1/tags/", json=_rule_payload(), headers=analyst_headers)
        r = await client.post("/api/v1/tags/", json=_rule_payload(), headers=analyst_headers)
        assert r.status_code == 409


# ── TestGetTagRule ────────────────────────────────────────────────────────────


class TestGetTagRule:
    async def test_get_existing(
        self, client: AsyncClient, rule_id: str, admin_headers: dict
    ) -> None:
        r = await client.get(f"/api/v1/tags/{rule_id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["id"] == rule_id

    async def test_get_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.get("/api/v1/tags/nonexistent_id", headers=admin_headers)
        assert r.status_code == 404

    async def test_list_returns_created_rule(
        self, client: AsyncClient, rule_id: str, admin_headers: dict
    ) -> None:
        r = await client.get("/api/v1/tags/", headers=admin_headers)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert rule_id in ids


# ── TestUpdateTagRule ─────────────────────────────────────────────────────────


class TestUpdateTagRule:
    async def test_update_tag_name(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        r = await client.patch(
            f"/api/v1/tags/{rule_id}", json={"tag_name": "labs"}, headers=analyst_headers
        )
        assert r.status_code == 200
        assert r.json()["tag_name"] == "labs"

    async def test_update_description(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        r = await client.patch(
            f"/api/v1/tags/{rule_id}", json={"description": "updated"}, headers=analyst_headers
        )
        assert r.status_code == 200
        assert r.json()["description"] == "updated"

    async def test_rename_to_existing_returns_409(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        r2 = await client.post("/api/v1/tags/", json=_rule_payload("labs"), headers=analyst_headers)
        assert r2.status_code == 201
        r = await client.patch(
            f"/api/v1/tags/{rule_id}", json={"tag_name": "labs"}, headers=analyst_headers
        )
        assert r.status_code == 409


# ── TestDeleteTagRule ─────────────────────────────────────────────────────────


class TestDeleteTagRule:
    async def test_delete_returns_204(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        r = await client.delete(f"/api/v1/tags/{rule_id}", headers=analyst_headers)
        assert r.status_code == 204

    async def test_deleted_rule_not_in_list(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        await client.delete(f"/api/v1/tags/{rule_id}", headers=analyst_headers)
        r = await client.get("/api/v1/tags/", headers=analyst_headers)
        ids = [x["id"] for x in r.json()]
        assert rule_id not in ids

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        r = await client.delete("/api/v1/tags/nonexistent_id", headers=analyst_headers)
        assert r.status_code == 404


# ── TestTagPatterns ───────────────────────────────────────────────────────────


class TestTagPatterns:
    async def test_add_pattern(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        r = await client.post(
            f"/api/v1/tags/{rule_id}/patterns", json=_pattern_payload(), headers=analyst_headers
        )
        assert r.status_code == 201
        data = r.json()
        assert data["pattern"] == "siemens*"
        assert data["display_name"] == "Siemens"

    async def test_pattern_appears_in_rule(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        await client.post(
            f"/api/v1/tags/{rule_id}/patterns", json=_pattern_payload(), headers=analyst_headers
        )
        r = await client.get(f"/api/v1/tags/{rule_id}", headers=analyst_headers)
        assert len(r.json()["patterns"]) == 1

    async def test_remove_pattern(
        self, client: AsyncClient, rule_with_pattern: tuple[str, str], analyst_headers: dict
    ) -> None:
        rule_id, pattern_id = rule_with_pattern
        r = await client.delete(
            f"/api/v1/tags/{rule_id}/patterns/{pattern_id}", headers=analyst_headers
        )
        assert r.status_code == 204
        r2 = await client.get(f"/api/v1/tags/{rule_id}", headers=analyst_headers)
        assert r2.json()["patterns"] == []

    async def test_remove_nonexistent_pattern_returns_404(
        self, client: AsyncClient, rule_id: str, analyst_headers: dict
    ) -> None:
        r = await client.delete(
            f"/api/v1/tags/{rule_id}/patterns/nonexistent_pattern", headers=analyst_headers
        )
        assert r.status_code == 404

    async def test_add_pattern_to_nonexistent_rule_returns_404(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        r = await client.post(
            "/api/v1/tags/nonexistent/patterns", json=_pattern_payload(), headers=analyst_headers
        )
        assert r.status_code == 404


# ── TestPreview ───────────────────────────────────────────────────────────────


class TestPreview:
    async def test_preview_empty_patterns(
        self, client: AsyncClient, rule_id: str, admin_headers: dict
    ) -> None:
        r = await client.post(f"/api/v1/tags/{rule_id}/preview", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["matched_count"] == 0
        assert data["agents"] == []
        assert data["preview_capped"] is False

    async def test_preview_with_matching_agent(
        self,
        client: AsyncClient,
        rule_id: str,
        seeded_db: AsyncIOMotorDatabase,
        analyst_headers: dict,
    ) -> None:
        # Insert an agent with a known app name
        await seeded_db["s1_agents"].insert_one(
            {
                "s1_agent_id": "agent_001",
                "hostname": "host-manufacturing-01",
                "group_name": "Manufacturing",
                "site_name": "Site A",
                "os_type": "windows",
                "installed_app_names": ["siemens wincc", "windows defender"],
            }
        )
        # Add a pattern that matches
        await client.post(
            f"/api/v1/tags/{rule_id}/patterns",
            json=_pattern_payload("siemens*", "Siemens WinCC"),
            headers=analyst_headers,
        )
        r = await client.post(f"/api/v1/tags/{rule_id}/preview", headers=analyst_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["matched_count"] == 1
        assert data["agents"][0]["hostname"] == "host-manufacturing-01"
        assert "siemens*" in data["agents"][0]["matched_patterns"]

    async def test_preview_no_match(
        self,
        client: AsyncClient,
        rule_id: str,
        seeded_db: AsyncIOMotorDatabase,
        analyst_headers: dict,
    ) -> None:
        await seeded_db["s1_agents"].insert_one(
            {
                "s1_agent_id": "agent_002",
                "hostname": "host-lab-01",
                "group_name": "Labs",
                "site_name": "Site B",
                "os_type": "linux",
                "installed_app_names": ["python", "jupyter"],
            }
        )
        await client.post(
            f"/api/v1/tags/{rule_id}/patterns",
            json=_pattern_payload("siemens*", "Siemens"),
            headers=analyst_headers,
        )
        r = await client.post(f"/api/v1/tags/{rule_id}/preview", headers=analyst_headers)
        assert r.status_code == 200
        assert r.json()["matched_count"] == 0

    async def test_preview_nonexistent_rule_returns_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.post("/api/v1/tags/nonexistent_id/preview", headers=admin_headers)
        assert r.status_code == 404


# ── TestApply ─────────────────────────────────────────────────────────────────


class TestApply:
    async def test_apply_starts(
        self,
        client: AsyncClient,
        rule_id: str,
        monkeypatch: pytest.MonkeyPatch,
        analyst_headers: dict,
    ) -> None:
        """Apply should start the background task and return 'started'."""
        # Monkeypatch _post on S1Client so no real HTTP calls are made
        from domains.sync import s1_client as s1_module

        async def _fake_post(self_: object, path: str, body: dict) -> dict:  # noqa: ARG001
            return {}

        monkeypatch.setattr(s1_module.S1Client, "_post", _fake_post)

        await client.post(
            f"/api/v1/tags/{rule_id}/patterns",
            json=_pattern_payload("siemens*", "Siemens"),
            headers=analyst_headers,
        )
        r = await client.post(f"/api/v1/tags/{rule_id}/apply", headers=analyst_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("started", "already_running")
        assert data["rule_id"] == rule_id

        # Poll until background task settles (handles coverage instrumentation overhead)
        await _wait_for_apply(client, rule_id, headers=analyst_headers)

        # Rule should now be in "done" or "failed" (no agents → done with count=0)
        r2 = await client.get(f"/api/v1/tags/{rule_id}", headers=analyst_headers)
        assert r2.json()["apply_status"] in ("done", "failed", "idle")

    async def test_apply_nonexistent_returns_404(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        r = await client.post("/api/v1/tags/nonexistent_id/apply", headers=analyst_headers)
        assert r.status_code == 404
