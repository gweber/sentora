"""Tests for classification export and additional classifier verdict branches.

Covers:
- GET /classification/export?format=csv
- GET /classification/export?format=json
- classify_single_agent: misclassified, ambiguous, unclassifiable verdicts
- classify_single_agent: no fingerprints, empty markers, zero weight
- classify_single_agent: wildcard patterns, fallback app query
"""

from __future__ import annotations

import asyncio
import json

from bson import ObjectId
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase


async def _wait_for_classification_idle(timeout: float = 10.0) -> None:
    """Wait for any running classification to complete."""
    from domains.classification.classifier import classification_manager

    await asyncio.sleep(0.2)
    if not classification_manager._lock.locked():
        return
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if not classification_manager._lock.locked():
            return
        await asyncio.sleep(0.2)


async def _seed_and_classify(
    client: AsyncClient, test_db: AsyncIOMotorDatabase, analyst_headers: dict
) -> None:
    """Seed agents, fingerprints, trigger classification, and wait."""
    now = "2025-01-01T00:00:00"
    await test_db["s1_agents"].insert_many(
        [
            {
                "s1_agent_id": "exp_agent1",
                "hostname": "exp-host-1",
                "group_id": "grp_a",
                "group_name": "Group A",
                "os_type": "windows",
                "synced_at": now,
                "installed_app_names": ["wincc runtime"],
            },
        ]
    )
    await test_db["fingerprints"].insert_one(
        {
            "_id": str(ObjectId()),
            "group_id": "grp_a",
            "group_name": "Group A",
            "markers": [
                {
                    "_id": str(ObjectId()),
                    "pattern": "wincc*",
                    "display_name": "WinCC",
                    "category": "scada",
                    "weight": 1.0,
                    "source": "manual",
                    "confidence": 1.0,
                    "added_at": now,
                    "added_by": "user",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "user",
        }
    )
    r = await client.post("/api/v1/classification/trigger", headers=analyst_headers)
    assert r.status_code == 202
    await _wait_for_classification_idle()


class TestExportCSV:
    """GET /classification/export?format=csv."""

    async def test_csv_export(
        self, client: AsyncClient, test_db: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """CSV export returns a valid CSV with headers."""
        await _seed_and_classify(client, test_db, analyst_headers)
        resp = await client.get(
            "/api/v1/classification/export", params={"format": "csv"}, headers=analyst_headers
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        lines = resp.text.strip().split("\n")
        assert len(lines) >= 2  # header + at least one data row
        header = lines[0]
        assert "hostname" in header
        assert "classification" in header

    async def test_csv_export_with_filter(
        self, client: AsyncClient, test_db: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """CSV export respects the classification filter."""
        await _seed_and_classify(client, test_db, analyst_headers)
        resp = await client.get(
            "/api/v1/classification/export",
            params={"format": "csv", "classification": "nonexistent"},
            headers=analyst_headers,
        )
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # only header, no data


class TestExportJSON:
    """GET /classification/export?format=json."""

    async def test_json_export(
        self, client: AsyncClient, test_db: AsyncIOMotorDatabase, analyst_headers: dict
    ) -> None:
        """JSON export returns valid JSON with results array."""
        await _seed_and_classify(client, test_db, analyst_headers)
        resp = await client.get(
            "/api/v1/classification/export", params={"format": "json"}, headers=analyst_headers
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        data = json.loads(resp.text)
        assert isinstance(data, dict)
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) >= 1
        assert "agent_id" in data["results"][0]


class TestClassifierVerdicts:
    """Unit tests for classify_single_agent verdict branches."""

    async def _classify(self, db: object, agent_doc: dict, fingerprint_docs: list[dict]) -> object:
        """Helper: insert fingerprints and classify."""
        from domains.classification.classifier import classify_single_agent
        from domains.fingerprint.repository import list_all

        for fp_doc in fingerprint_docs:
            await db["fingerprints"].insert_one(fp_doc)

        fingerprints = await list_all(db)
        return await classify_single_agent(db, agent_doc, fingerprints)

    async def test_misclassified_verdict(self, test_db: AsyncIOMotorDatabase) -> None:
        """Agent in group A whose apps match group B fingerprint → misclassified."""
        now = "2025-01-01T00:00:00"
        agent = {
            "s1_agent_id": "mis_agent",
            "hostname": "mis-host",
            "group_id": "grp_wrong",
            "group_name": "Wrong Group",
            "installed_app_names": ["wincc runtime"],
        }
        fp = {
            "_id": str(ObjectId()),
            "group_id": "grp_correct",
            "group_name": "Correct Group",
            "markers": [
                {
                    "_id": str(ObjectId()),
                    "pattern": "wincc*",
                    "display_name": "WinCC",
                    "category": "scada",
                    "weight": 1.0,
                    "source": "manual",
                    "confidence": 1.0,
                    "added_at": now,
                    "added_by": "user",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "user",
        }
        result = await self._classify(test_db, agent, [fp])
        assert result.classification == "misclassified"
        assert result.suggested_group_id == "grp_correct"
        assert len(result.anomaly_reasons) >= 1

    async def test_ambiguous_verdict_small_gap(self, test_db: AsyncIOMotorDatabase) -> None:
        """When two fingerprints score similarly, verdict is ambiguous."""
        now = "2025-01-01T00:00:00"
        agent = {
            "s1_agent_id": "amb_agent",
            "hostname": "amb-host",
            "group_id": "grp_a",
            "group_name": "Group A",
            "installed_app_names": ["shared app"],
        }
        # Two fingerprints both matching the same app → tied scores, gap < 0.15
        fp_a = {
            "_id": str(ObjectId()),
            "group_id": "grp_a",
            "group_name": "Group A",
            "markers": [
                {
                    "_id": str(ObjectId()),
                    "pattern": "shared app",
                    "display_name": "Shared",
                    "category": "test",
                    "weight": 1.0,
                    "source": "manual",
                    "confidence": 1.0,
                    "added_at": now,
                    "added_by": "user",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "user",
        }
        fp_b = {
            "_id": str(ObjectId()),
            "group_id": "grp_b",
            "group_name": "Group B",
            "markers": [
                {
                    "_id": str(ObjectId()),
                    "pattern": "shared app",
                    "display_name": "Shared",
                    "category": "test",
                    "weight": 1.0,
                    "source": "manual",
                    "confidence": 1.0,
                    "added_at": now,
                    "added_by": "user",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "user",
        }
        result = await self._classify(test_db, agent, [fp_a, fp_b])
        assert result.classification == "ambiguous"

    async def test_unclassifiable_no_match(self, test_db: AsyncIOMotorDatabase) -> None:
        """Agent with no matching apps → unclassifiable."""
        now = "2025-01-01T00:00:00"
        agent = {
            "s1_agent_id": "unc_agent",
            "hostname": "unc-host",
            "group_id": "grp_x",
            "group_name": "Group X",
            "installed_app_names": ["random thing"],
        }
        fp = {
            "_id": str(ObjectId()),
            "group_id": "grp_y",
            "group_name": "Group Y",
            "markers": [
                {
                    "_id": str(ObjectId()),
                    "pattern": "very specific app",
                    "display_name": "Specific",
                    "category": "test",
                    "weight": 1.0,
                    "source": "manual",
                    "confidence": 1.0,
                    "added_at": now,
                    "added_by": "user",
                }
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "user",
        }
        result = await self._classify(test_db, agent, [fp])
        assert result.classification == "unclassifiable"

    async def test_unclassifiable_no_fingerprints(self, test_db: AsyncIOMotorDatabase) -> None:
        """No fingerprints at all → unclassifiable."""
        from domains.classification.classifier import classify_single_agent

        agent = {
            "s1_agent_id": "nofp_agent",
            "hostname": "nofp-host",
            "group_id": "grp_z",
            "group_name": "Group Z",
            "installed_app_names": ["some app"],
        }
        result = await classify_single_agent(test_db, agent, [])
        assert result.classification == "unclassifiable"
        assert "No fingerprints" in result.anomaly_reasons[0]

    async def test_empty_markers_score_zero(self, test_db: AsyncIOMotorDatabase) -> None:
        """A fingerprint with no markers scores 0."""
        from domains.classification.classifier import classify_single_agent
        from domains.fingerprint.entities import Fingerprint

        fp = Fingerprint(
            group_id="grp_empty",
            group_name="Empty",
            markers=[],
        )
        agent = {
            "s1_agent_id": "empty_agent",
            "hostname": "empty-host",
            "group_id": "grp_empty",
            "group_name": "Empty",
            "installed_app_names": ["some app"],
        }
        result = await classify_single_agent(test_db, agent, [fp])
        assert result.match_scores[0].score == 0.0

    async def test_fallback_app_query(self, test_db: AsyncIOMotorDatabase) -> None:
        """When installed_app_names is empty, falls back to s1_installed_apps query."""
        now = "2025-01-01T00:00:00"
        from domains.classification.classifier import classify_single_agent
        from domains.fingerprint.entities import Fingerprint, FingerprintMarker

        # Insert apps in s1_installed_apps
        await test_db["s1_installed_apps"].insert_one(
            {
                "agent_id": "fallback_agent",
                "name": "WinCC Runtime",
                "normalized_name": "wincc runtime",
                "synced_at": now,
            }
        )

        fp = Fingerprint(
            group_id="grp_fb",
            group_name="Fallback Group",
            markers=[
                FingerprintMarker(
                    pattern="wincc*",
                    display_name="WinCC",
                    source="manual",
                    confidence=1.0,
                    weight=1.0,
                ),
            ],
        )
        agent = {
            "s1_agent_id": "fallback_agent",
            "hostname": "fb-host",
            "group_id": "grp_fb",
            "group_name": "Fallback Group",
            # No installed_app_names — triggers fallback
        }
        result = await classify_single_agent(test_db, agent, [fp])
        assert result.match_scores[0].score > 0.0

    async def test_wildcard_pattern_matching(self, test_db: AsyncIOMotorDatabase) -> None:
        """Wildcard patterns in markers match against app names."""
        from domains.classification.classifier import classify_single_agent
        from domains.fingerprint.entities import Fingerprint, FingerprintMarker

        fp = Fingerprint(
            group_id="grp_wc",
            group_name="Wildcard Group",
            markers=[
                FingerprintMarker(
                    pattern="wincc*",
                    display_name="WinCC",
                    source="manual",
                    confidence=1.0,
                    weight=1.0,
                ),
            ],
        )
        agent = {
            "s1_agent_id": "wc_agent",
            "hostname": "wc-host",
            "group_id": "grp_wc",
            "group_name": "Wildcard Group",
            "installed_app_names": ["wincc runtime advanced"],
        }
        result = await classify_single_agent(test_db, agent, [fp])
        assert result.match_scores[0].score == 1.0
        assert "WinCC" in result.match_scores[0].matched_markers
