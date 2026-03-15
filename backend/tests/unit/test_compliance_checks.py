"""Unit tests for compliance check implementations.

Each check type has tests for: pass case, fail case, and edge case (0 agents).
Uses a real MongoDB test database per TESTING.md requirements.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now
from datetime import timedelta


@pytest_asyncio.fixture(scope="function")
async def seeded_agents(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed test database with agents and apps for compliance check testing.

    Creates:
    - 3 agents: agent-1 (online, current), agent-2 (stale), agent-3 (online, current)
    - Apps: agent-1 has approved apps, agent-2 has a prohibited app, agent-3 has all approved
    - A completed sync run from 1 hour ago
    - Classification results for agent-1 and agent-3

    Returns:
        The seeded test database.
    """
    now = utc_now()

    # Agents
    agents = [
        {
            "s1_agent_id": "agent-1",
            "hostname": "workstation-1",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(hours=1),
            "group_name": "Default",
            "group_id": "g1",
            "site_id": "s1",
            "tags": ["PCI-CDE"],
            "installed_app_names": ["SentinelOne", "Microsoft Office", "Chrome"],
            "synced_at": now,
        },
        {
            "s1_agent_id": "agent-2",
            "hostname": "workstation-2",
            "agent_version": "23.1.0.100",
            "last_active": now - timedelta(days=14),
            "group_name": "Remote",
            "group_id": "g2",
            "site_id": "s1",
            "tags": [],
            "installed_app_names": ["SentinelOne", "uTorrent", "VLC"],
            "synced_at": now,
        },
        {
            "s1_agent_id": "agent-3",
            "hostname": "workstation-3",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(minutes=30),
            "group_name": "Default",
            "group_id": "g1",
            "site_id": "s1",
            "tags": ["PCI-CDE", "HIPAA"],
            "installed_app_names": ["SentinelOne", "Chrome", "Slack"],
            "synced_at": now,
        },
    ]
    await test_db["s1_agents"].insert_many(agents)

    # Installed apps
    apps = [
        {"agent_id": "agent-1", "normalized_name": "SentinelOne", "version": "23.3.1", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-1", "normalized_name": "Microsoft Office", "version": "365", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-1", "normalized_name": "Chrome", "version": "120.0", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-2", "normalized_name": "SentinelOne", "version": "23.1.0", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-2", "normalized_name": "uTorrent", "version": "3.5", "risk_level": "prohibited", "last_synced_at": now},
        {"agent_id": "agent-2", "normalized_name": "VLC", "version": "3.0.20", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-3", "normalized_name": "SentinelOne", "version": "23.3.1", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-3", "normalized_name": "Chrome", "version": "120.0", "risk_level": "approved", "last_synced_at": now},
        {"agent_id": "agent-3", "normalized_name": "Slack", "version": "4.35", "risk_level": "approved", "last_synced_at": now},
    ]
    await test_db["s1_installed_apps"].insert_many(apps)

    # Sync run
    await test_db["s1_sync_runs"].insert_one({
        "run_id": "sync-1",
        "status": "completed",
        "completed_at": now - timedelta(hours=1),
        "started_at": now - timedelta(hours=2),
    })

    # Classification results
    await test_db["classification_results"].insert_many([
        {"agent_id": "agent-1", "classification": "correct", "hostname": "workstation-1", "current_group_id": "g1"},
        {"agent_id": "agent-3", "classification": "correct", "hostname": "workstation-3", "current_group_id": "g1"},
    ])

    # App summaries (for unclassified threshold)
    await test_db["app_summaries"].insert_many([
        {"normalized_name": "SentinelOne", "category": "Security", "agent_count": 3},
        {"normalized_name": "Chrome", "category": "Browser", "agent_count": 2},
        {"normalized_name": "Microsoft Office", "category": "Productivity", "agent_count": 1},
        {"normalized_name": "Slack", "category": "Communication", "agent_count": 1},
        {"normalized_name": "VLC", "category": "Media", "agent_count": 1},
        # uTorrent intentionally NOT in app_summaries (unclassified)
    ])

    return test_db


# ── Prohibited App Check ──────────────────────────────────────────────────


class TestProhibitedAppCheck:
    """Tests for the prohibited application check."""

    @pytest.mark.asyncio
    async def test_detects_prohibited_app(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agent-2 has uTorrent (prohibited) — check should fail."""
        from domains.compliance.checks.prohibited_app import execute

        result = await execute(
            seeded_agents,
            control_id="test-prohibited",
            framework_id="soc2",
            control_name="No Prohibited Software",
            category="Access Controls",
            severity="critical",
            parameters={},
            scope_filter={},
        )
        assert result.status.value == "fail"
        assert result.non_compliant_endpoints == 1
        assert result.compliant_endpoints == 2
        assert len(result.violations) == 1
        assert "uTorrent" in result.violations[0].violation_detail

    @pytest.mark.asyncio
    async def test_passes_when_no_prohibited_apps(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Scoped to PCI-CDE agents (agent-1, agent-3) — no prohibited apps — pass."""
        from domains.compliance.checks.prohibited_app import execute

        result = await execute(
            seeded_agents,
            control_id="test-prohibited",
            framework_id="soc2",
            control_name="No Prohibited Software",
            category="Access Controls",
            severity="critical",
            parameters={},
            scope_filter={"tags": {"$in": ["PCI-CDE"]}},
        )
        assert result.status.value == "pass"
        assert result.non_compliant_endpoints == 0
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_not_applicable_with_no_agents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Empty database — should return not_applicable."""
        from domains.compliance.checks.prohibited_app import execute

        result = await execute(
            test_db,
            control_id="test-prohibited",
            framework_id="soc2",
            control_name="No Prohibited Software",
            category="Access Controls",
            severity="critical",
            parameters={},
            scope_filter={},
        )
        assert result.status.value == "not_applicable"
        assert result.total_endpoints == 0


# ── Agent Online Check ────────────────────────────────────────────────────


class TestAgentOnlineCheck:
    """Tests for the agent online/staleness check."""

    @pytest.mark.asyncio
    async def test_detects_stale_agent(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agent-2 is 14 days offline — check should fail with max_offline_days=7."""
        from domains.compliance.checks.agent_online import execute

        result = await execute(
            seeded_agents,
            control_id="test-online",
            framework_id="soc2",
            control_name="Agent Online",
            category="Availability",
            severity="high",
            parameters={"max_offline_days": 7},
            scope_filter={},
        )
        assert result.status.value == "fail"
        assert result.non_compliant_endpoints == 1
        assert len(result.violations) == 1
        assert "workstation-2" in result.violations[0].agent_hostname

    @pytest.mark.asyncio
    async def test_all_agents_online(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """With max_offline_days=30, all agents pass (agent-2 is only 14 days old)."""
        from domains.compliance.checks.agent_online import execute

        result = await execute(
            seeded_agents,
            control_id="test-online",
            framework_id="soc2",
            control_name="Agent Online",
            category="Availability",
            severity="high",
            parameters={"max_offline_days": 30},
            scope_filter={},
        )
        assert result.status.value == "pass"
        assert result.non_compliant_endpoints == 0

    @pytest.mark.asyncio
    async def test_no_agents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Empty DB returns not_applicable."""
        from domains.compliance.checks.agent_online import execute

        result = await execute(
            test_db,
            control_id="test-online",
            framework_id="soc2",
            control_name="Agent Online",
            category="Availability",
            severity="high",
            parameters={"max_offline_days": 7},
            scope_filter={},
        )
        assert result.status.value == "not_applicable"


# ── Agent Version Check ───────────────────────────────────────────────────


class TestAgentVersionCheck:
    """Tests for the agent version currency check."""

    @pytest.mark.asyncio
    async def test_detects_outdated_agent(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Agent-2 has version 23.1.0.100 — below the fleet mode of 23.3.1.500."""
        from domains.compliance.checks.agent_version import execute

        result = await execute(
            seeded_agents,
            control_id="test-version",
            framework_id="soc2",
            control_name="Agent Version",
            category="Malware Protection",
            severity="critical",
            parameters={},
            scope_filter={},
        )
        assert result.status.value == "fail"
        assert result.non_compliant_endpoints == 1
        assert "23.1.0.100" in result.violations[0].violation_detail

    @pytest.mark.asyncio
    async def test_all_current_with_explicit_min(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """All agents pass when min_version is set to 23.1.0.100 (everyone meets it)."""
        from domains.compliance.checks.agent_version import execute

        result = await execute(
            seeded_agents,
            control_id="test-version",
            framework_id="soc2",
            control_name="Agent Version",
            category="Malware Protection",
            severity="critical",
            parameters={"min_version": "23.1.0.100"},
            scope_filter={},
        )
        assert result.status.value == "pass"

    @pytest.mark.asyncio
    async def test_no_agents(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Empty DB returns not_applicable."""
        from domains.compliance.checks.agent_version import execute

        result = await execute(
            test_db,
            control_id="test-version",
            framework_id="soc2",
            control_name="Agent Version",
            category="Malware Protection",
            severity="critical",
            parameters={},
            scope_filter={},
        )
        assert result.status.value == "not_applicable"


# ── Sync Freshness Check ─────────────────────────────────────────────────


class TestSyncFreshnessCheck:
    """Tests for the sync freshness check."""

    @pytest.mark.asyncio
    async def test_sync_is_fresh(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Sync completed 1h ago, threshold 24h — should pass."""
        from domains.compliance.checks.sync_freshness import execute

        result = await execute(
            seeded_agents,
            control_id="test-sync",
            framework_id="soc2",
            control_name="Sync Freshness",
            category="Monitoring",
            severity="high",
            parameters={"max_hours_since_sync": 24},
            scope_filter={},
        )
        assert result.status.value == "pass"

    @pytest.mark.asyncio
    async def test_no_sync_runs(self, test_db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """No sync runs at all — should fail."""
        from domains.compliance.checks.sync_freshness import execute

        result = await execute(
            test_db,
            control_id="test-sync",
            framework_id="soc2",
            control_name="Sync Freshness",
            category="Monitoring",
            severity="high",
            parameters={"max_hours_since_sync": 24},
            scope_filter={},
        )
        assert result.status.value == "fail"
        assert len(result.violations) == 1


# ── Classification Coverage Check ─────────────────────────────────────────


class TestClassificationCoverageCheck:
    """Tests for the classification coverage check."""

    @pytest.mark.asyncio
    async def test_below_threshold(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """2/3 agents classified = 66.7%, threshold 90% — should fail."""
        from domains.compliance.checks.classification_coverage import execute

        result = await execute(
            seeded_agents,
            control_id="test-coverage",
            framework_id="soc2",
            control_name="Classification Coverage",
            category="Risk Assessment",
            severity="medium",
            parameters={"min_classified_percent": 90},
            scope_filter={},
        )
        assert result.status.value == "fail"
        assert result.compliant_endpoints == 2
        assert result.non_compliant_endpoints == 1

    @pytest.mark.asyncio
    async def test_above_threshold(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """2/3 = 66.7%, threshold 50% — should pass."""
        from domains.compliance.checks.classification_coverage import execute

        result = await execute(
            seeded_agents,
            control_id="test-coverage",
            framework_id="soc2",
            control_name="Classification Coverage",
            category="Risk Assessment",
            severity="medium",
            parameters={"min_classified_percent": 50},
            scope_filter={},
        )
        assert result.status.value == "pass"


# ── Required App Check ────────────────────────────────────────────────────


class TestRequiredAppCheck:
    """Tests for the required application presence check."""

    @pytest.mark.asyncio
    async def test_required_app_present(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """All agents have SentinelOne installed — should pass."""
        from domains.compliance.checks.required_app import execute

        result = await execute(
            seeded_agents,
            control_id="test-required",
            framework_id="soc2",
            control_name="Required Apps",
            category="Access Controls",
            severity="high",
            parameters={"required_apps": ["SentinelOne"]},
            scope_filter={},
        )
        assert result.status.value == "pass"
        assert result.non_compliant_endpoints == 0

    @pytest.mark.asyncio
    async def test_required_app_missing(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Not all agents have 'BitLocker' — should fail."""
        from domains.compliance.checks.required_app import execute

        result = await execute(
            seeded_agents,
            control_id="test-required",
            framework_id="soc2",
            control_name="Required Apps",
            category="Access Controls",
            severity="high",
            parameters={"required_apps": ["BitLocker"]},
            scope_filter={},
        )
        assert result.status.value == "fail"
        # All 3 agents missing BitLocker
        assert result.non_compliant_endpoints == 3

    @pytest.mark.asyncio
    async def test_no_required_apps_configured(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Empty required_apps list — should be not_applicable."""
        from domains.compliance.checks.required_app import execute

        result = await execute(
            seeded_agents,
            control_id="test-required",
            framework_id="soc2",
            control_name="Required Apps",
            category="Access Controls",
            severity="high",
            parameters={"required_apps": []},
            scope_filter={},
        )
        assert result.status.value == "not_applicable"


# ── Custom App Presence Check ─────────────────────────────────────────────


class TestCustomAppPresenceCheck:
    """Tests for the custom app presence/absence check."""

    @pytest.mark.asyncio
    async def test_app_must_exist_and_does(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """SentinelOne must exist — all agents have it — pass."""
        from domains.compliance.checks.custom_app_presence import execute

        result = await execute(
            seeded_agents,
            control_id="test-custom",
            framework_id="soc2",
            control_name="Custom Presence",
            category="Custom",
            severity="medium",
            parameters={"app_pattern": "SentinelOne*", "must_exist": True},
            scope_filter={},
        )
        assert result.status.value == "pass"

    @pytest.mark.asyncio
    async def test_app_must_not_exist_but_does(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """uTorrent must NOT exist — agent-2 has it — fail."""
        from domains.compliance.checks.custom_app_presence import execute

        result = await execute(
            seeded_agents,
            control_id="test-custom",
            framework_id="soc2",
            control_name="Custom Absence",
            category="Custom",
            severity="high",
            parameters={"app_pattern": "uTorrent*", "must_exist": False},
            scope_filter={},
        )
        assert result.status.value == "fail"
        assert result.non_compliant_endpoints == 1

    @pytest.mark.asyncio
    async def test_no_pattern_returns_error(self, seeded_agents: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        """Missing app_pattern returns error status."""
        from domains.compliance.checks.custom_app_presence import execute

        result = await execute(
            seeded_agents,
            control_id="test-custom",
            framework_id="soc2",
            control_name="Custom",
            category="Custom",
            severity="medium",
            parameters={"app_pattern": "", "must_exist": True},
            scope_filter={},
        )
        assert result.status.value == "error"
