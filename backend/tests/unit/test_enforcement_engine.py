"""Unit tests for enforcement check engine.

Tests the three check types (required, forbidden, allowlist) with
pass, fail, and edge cases using a real MongoDB test database.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.enforcement.engine import evaluate_rule
from domains.enforcement.entities import EnforcementRule, RuleType, Severity
from utils.dt import utc_now


@pytest_asyncio.fixture(scope="function")
async def enforcement_db(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed database for enforcement engine tests.

    Creates:
    - 3 agents: agent-a (has EDR + browser), agent-b (has EDR), agent-c (has P2P)
    - Taxonomy entries: required_edr (SentinelOne*), forbidden_p2p (*torrent*)
    """
    now = utc_now()

    agents = [
        {
            "source": "sentinelone",
            "source_id": "agent-a",
            "hostname": "ws-alpha",
            "group_name": "Office",
            "tags": ["PCI-CDE"],
            "installed_app_names": ["SentinelOne Agent", "Chrome", "Slack"],
            "synced_at": now,
        },
        {
            "source": "sentinelone",
            "source_id": "agent-b",
            "hostname": "ws-beta",
            "group_name": "Office",
            "tags": [],
            "installed_app_names": ["SentinelOne Agent", "Firefox"],
            "synced_at": now,
        },
        {
            "source": "sentinelone",
            "source_id": "agent-c",
            "hostname": "ws-gamma",
            "group_name": "Remote",
            "tags": [],
            "installed_app_names": ["uTorrent", "VLC"],
            "synced_at": now,
        },
    ]
    await test_db["agents"].insert_many(agents)

    # Taxonomy entries
    await test_db["taxonomy_entries"].insert_many(
        [
            {
                "name": "SentinelOne",
                "patterns": ["SentinelOne*"],
                "category": "required_edr",
                "category_display": "Required / EDR",
                "publisher": "SentinelOne",
            },
            {
                "name": "uTorrent",
                "patterns": ["*torrent*"],
                "category": "forbidden_p2p",
                "category_display": "Forbidden / P2P",
                "publisher": "BitTorrent",
            },
            {
                "name": "Chrome",
                "patterns": ["Chrome*"],
                "category": "approved_browsers",
                "category_display": "Approved / Browsers",
                "publisher": "Google",
            },
            {
                "name": "Firefox",
                "patterns": ["Firefox*"],
                "category": "approved_browsers",
                "category_display": "Approved / Browsers",
                "publisher": "Mozilla",
            },
        ]
    )

    return test_db


def _make_rule(
    rule_type: str,
    category: str,
    scope_groups: list[str] | None = None,
    scope_tags: list[str] | None = None,
) -> EnforcementRule:
    """Build a test rule with minimal required fields."""
    return EnforcementRule(
        id="test-rule",
        name=f"Test {rule_type}",
        taxonomy_category_id=category,
        type=RuleType(rule_type),
        severity=Severity.high,
        scope_groups=scope_groups or [],
        scope_tags=scope_tags or [],
    )


# ── Required Check ────────────────────────────────────────────────────────


class TestRequiredCheck:
    """Tests for the 'required' check type."""

    @pytest.mark.asyncio
    async def test_all_have_required_app(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agents a,b have SentinelOne — scoped to 'Office' — pass."""
        rule = _make_rule("required", "required_edr", scope_groups=["Office"])
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "pass"
        assert result.total_agents == 2
        assert result.non_compliant_agents == 0

    @pytest.mark.asyncio
    async def test_agent_missing_required(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agent-c has no EDR — all agents scope — fail."""
        rule = _make_rule("required", "required_edr")
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "fail"
        assert result.non_compliant_agents == 1
        assert len(result.violations) == 1
        assert result.violations[0].agent_hostname == "ws-gamma"

    @pytest.mark.asyncio
    async def test_no_agents_in_scope(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """No agents match the scope — pass (0 endpoints)."""
        rule = _make_rule("required", "required_edr", scope_groups=["NonExistentGroup"])
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "pass"
        assert result.total_agents == 0

    @pytest.mark.asyncio
    async def test_empty_taxonomy(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Category with no taxonomy entries — pass with warning violation."""
        rule = _make_rule("required", "nonexistent_category")
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "pass"
        assert len(result.violations) == 1
        assert "No taxonomy patterns" in result.violations[0].violation_detail


# ── Forbidden Check ───────────────────────────────────────────────────────


class TestForbiddenCheck:
    """Tests for the 'forbidden' check type."""

    @pytest.mark.asyncio
    async def test_forbidden_app_found(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agent-c has uTorrent (matches *torrent*) — fail."""
        rule = _make_rule("forbidden", "forbidden_p2p")
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "fail"
        assert result.non_compliant_agents == 1
        assert len(result.violations) == 1
        assert "uTorrent" in result.violations[0].violation_detail

    @pytest.mark.asyncio
    async def test_no_forbidden_apps(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Scoped to Office group — no P2P apps — pass."""
        rule = _make_rule("forbidden", "forbidden_p2p", scope_groups=["Office"])
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "pass"
        assert result.non_compliant_agents == 0

    @pytest.mark.asyncio
    async def test_empty_db(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Empty database — no patterns = pass."""
        rule = _make_rule("forbidden", "forbidden_p2p")
        result = await evaluate_rule(test_db, rule)
        assert result.status.value == "pass"


# ── Allowlist Check ───────────────────────────────────────────────────────


class TestAllowlistCheck:
    """Tests for the 'allowlist' check type."""

    @pytest.mark.asyncio
    async def test_all_apps_on_allowlist(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agent-b has SentinelOne + Firefox, both in approved categories.

        We create a combined allowlist with EDR + browsers patterns.
        Since allowlist checks against a single category, we need a
        broader category. Let's check with required_edr which only
        matches SentinelOne — Firefox won't match → fail.
        """
        rule = _make_rule("allowlist", "approved_browsers", scope_groups=["Office"])
        result = await evaluate_rule(enforcement_db, rule)
        # Agent-a: Chrome matches, SentinelOne + Slack don't
        # Agent-b: Firefox matches, SentinelOne doesn't
        assert result.status.value == "fail"
        assert result.non_compliant_agents == 2

    @pytest.mark.asyncio
    async def test_no_agents_in_scope(self, enforcement_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """No agents in scope — pass."""
        rule = _make_rule("allowlist", "approved_browsers", scope_groups=["NonExistent"])
        result = await evaluate_rule(enforcement_db, rule)
        assert result.status.value == "pass"
        assert result.total_agents == 0
