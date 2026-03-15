"""Integration tests for fingerprint proposal and suggestion endpoints.

Covers the uncovered lines in fingerprint/router.py:
- POST /proposals/generate — trigger proposal generation
- GET /proposals/ — list proposals
- POST /proposals/{group_id}/apply — apply proposal markers
- POST /proposals/{group_id}/dismiss — dismiss a proposal
- POST /suggestions/{group_id}/accept/{id}
- POST /suggestions/{group_id}/reject/{id}
"""

from __future__ import annotations

import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def fp_group(client: AsyncClient, analyst_headers: dict) -> str:
    """Create a fingerprint and return its group_id."""
    gid = "proposal_test_group"
    r = await client.post(f"/api/v1/fingerprints/{gid}", headers=analyst_headers)
    assert r.status_code in (200, 201)
    return gid


# ── Proposal endpoints ──────────────────────────────────────────────────────


class TestProposals:
    """Tests for the proposal generation and management endpoints."""

    async def test_list_proposals_empty(self, client: AsyncClient, admin_headers: dict) -> None:
        """GET /proposals/ returns empty list when none generated."""
        resp = await client.get("/api/v1/fingerprints/proposals/", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_dismiss_proposal_not_found(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Dismissing a nonexistent proposal returns 404."""
        resp = await client.post(
            "/api/v1/fingerprints/proposals/fake_group/dismiss",
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    async def test_apply_proposal_not_found(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Applying a nonexistent proposal returns 404."""
        resp = await client.post(
            "/api/v1/fingerprints/proposals/fake_group/apply",
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    async def test_generate_proposals_requires_auth(self, client: AsyncClient) -> None:
        """POST /proposals/generate without auth returns 401."""
        resp = await client.post("/api/v1/fingerprints/proposals/generate")
        assert resp.status_code == 401


# ── Suggestion accept/reject ────────────────────────────────────────────────


class TestSuggestionActions:
    """Tests for accepting and rejecting suggestions."""

    async def test_accept_nonexistent_suggestion_404(
        self, client: AsyncClient, fp_group: str, analyst_headers: dict
    ) -> None:
        """Accepting a suggestion that doesn't exist returns 404."""
        resp = await client.post(
            f"/api/v1/suggestions/{fp_group}/accept/000000000000000000000000",
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    async def test_reject_nonexistent_suggestion_404(
        self, client: AsyncClient, fp_group: str, analyst_headers: dict
    ) -> None:
        """Rejecting a suggestion that doesn't exist returns 404."""
        resp = await client.post(
            f"/api/v1/suggestions/{fp_group}/reject/000000000000000000000000",
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    async def test_accept_suggestion_requires_auth(self, client: AsyncClient) -> None:
        """Accept suggestion without auth returns 401."""
        resp = await client.post("/api/v1/suggestions/grp/accept/000000000000000000000000")
        assert resp.status_code == 401

    async def test_reject_suggestion_requires_auth(self, client: AsyncClient) -> None:
        """Reject suggestion without auth returns 401."""
        resp = await client.post("/api/v1/suggestions/grp/reject/000000000000000000000000")
        assert resp.status_code == 401

    async def test_compute_then_accept_suggestion(
        self, client: AsyncClient, fp_group: str, test_db: object, analyst_headers: dict
    ) -> None:
        """Compute suggestions, then accept one — it should become a marker."""
        _NOW = "2025-01-01T00:00:00"
        # Seed agents + apps
        await test_db["s1_agents"].insert_many(
            [
                {
                    "s1_agent_id": f"acc_agent_{i}",
                    "group_id": fp_group,
                    "group_name": "Test",
                    "hostname": f"h-{i}",
                    "os_type": "windows",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        await test_db["s1_installed_apps"].insert_many(
            [
                {
                    "agent_id": f"acc_agent_{i}",
                    "name": "Unique App 123",
                    "normalized_name": "unique app 123",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        # Out-of-group agent
        await test_db["s1_agents"].insert_one(
            {
                "s1_agent_id": "other_acc",
                "group_id": "other",
                "group_name": "Other",
                "hostname": "x",
                "os_type": "linux",
                "synced_at": _NOW,
            }
        )
        await test_db["s1_installed_apps"].insert_one(
            {
                "agent_id": "other_acc",
                "name": "Other App",
                "normalized_name": "other app",
                "synced_at": _NOW,
            }
        )

        # Compute
        comp = await client.post(
            f"/api/v1/suggestions/{fp_group}/compute",
            headers=analyst_headers,
        )
        assert comp.status_code == 200
        suggestions = comp.json()
        assert len(suggestions) >= 1

        # Accept the first one
        sid = suggestions[0]["id"]
        accept = await client.post(
            f"/api/v1/suggestions/{fp_group}/accept/{sid}",
            headers=analyst_headers,
        )
        assert accept.status_code == 204

        # Verify it was added as a marker
        fp = await client.get(f"/api/v1/fingerprints/{fp_group}", headers=analyst_headers)
        assert fp.status_code == 200
        patterns = [m["pattern"] for m in fp.json()["markers"]]
        assert suggestions[0]["normalized_name"] in patterns

    async def test_compute_then_reject_suggestion(
        self, client: AsyncClient, fp_group: str, test_db: object, analyst_headers: dict
    ) -> None:
        """Compute suggestions, then reject one — it should disappear from the list."""
        _NOW = "2025-01-01T00:00:00"
        await test_db["s1_agents"].insert_many(
            [
                {
                    "s1_agent_id": f"rej_agent_{i}",
                    "group_id": fp_group,
                    "group_name": "Test",
                    "hostname": f"hr-{i}",
                    "os_type": "windows",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        await test_db["s1_installed_apps"].insert_many(
            [
                {
                    "agent_id": f"rej_agent_{i}",
                    "name": "Rejectable App",
                    "normalized_name": "rejectable app",
                    "synced_at": _NOW,
                }
                for i in range(3)
            ]
        )
        await test_db["s1_agents"].insert_one(
            {
                "s1_agent_id": "other_rej",
                "group_id": "other",
                "group_name": "Other",
                "hostname": "y",
                "os_type": "linux",
                "synced_at": _NOW,
            }
        )
        await test_db["s1_installed_apps"].insert_one(
            {
                "agent_id": "other_rej",
                "name": "Linux Stuff",
                "normalized_name": "linux stuff",
                "synced_at": _NOW,
            }
        )

        comp = await client.post(
            f"/api/v1/suggestions/{fp_group}/compute",
            headers=analyst_headers,
        )
        assert comp.status_code == 200
        suggestions = comp.json()
        assert len(suggestions) >= 1

        sid = suggestions[0]["id"]
        reject = await client.post(
            f"/api/v1/suggestions/{fp_group}/reject/{sid}",
            headers=analyst_headers,
        )
        assert reject.status_code == 204

        # Rejected suggestions should not appear in subsequent GET
        get_resp = await client.get(f"/api/v1/suggestions/{fp_group}", headers=analyst_headers)
        assert get_resp.status_code == 200
        remaining_ids = [s["id"] for s in get_resp.json()]
        assert sid not in remaining_ids
