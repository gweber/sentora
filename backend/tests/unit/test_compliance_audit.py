"""Tests for compliance controls audit fixes.

Covers:
- classification_coverage scope filtering fix (joins via agent IDs)
- custom_app_presence empty pattern returns not_applicable
- Engine check-result caching (deduplication)
- Framework definition validation (all 84 controls well-formed)
- Handbook generation script idempotency
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now

# Add scripts directory to path for handbook generation tests
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


@pytest_asyncio.fixture(scope="function")
async def scoped_agents(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed database with agents having different tags for scope testing.

    Creates:
    - agent-1: tags=["PCI-CDE", "HIPAA"], group=Default
    - agent-2: tags=["HIPAA"], group=Remote
    - agent-3: tags=[], group=Default
    - Classification results for agent-1 and agent-2 only
    - Sync run from 1 hour ago

    Returns:
        The seeded test database.
    """
    now = utc_now()

    agents = [
        {
            "source": "sentinelone",
            "source_id": "agent-1",
            "hostname": "ws-1",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(hours=1),
            "group_name": "Default",
            "group_id": "g1",
            "site_id": "s1",
            "tags": ["PCI-CDE", "HIPAA"],
            "installed_app_names": ["SentinelOne", "Chrome"],
            "synced_at": now,
        },
        {
            "source": "sentinelone",
            "source_id": "agent-2",
            "hostname": "ws-2",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(hours=2),
            "group_name": "Remote",
            "group_id": "g2",
            "site_id": "s1",
            "tags": ["HIPAA"],
            "installed_app_names": ["SentinelOne", "Slack"],
            "synced_at": now,
        },
        {
            "source": "sentinelone",
            "source_id": "agent-3",
            "hostname": "ws-3",
            "agent_version": "23.3.1.500",
            "last_active": now - timedelta(hours=3),
            "group_name": "Default",
            "group_id": "g1",
            "site_id": "s1",
            "tags": [],
            "installed_app_names": ["SentinelOne", "Firefox"],
            "synced_at": now,
        },
    ]
    await test_db["agents"].insert_many(agents)

    # Classification results — agent-1 and agent-2 classified, agent-3 not
    await test_db["classification_results"].insert_many(
        [
            {"agent_id": "agent-1", "classification": "correct", "hostname": "ws-1"},
            {"agent_id": "agent-2", "classification": "correct", "hostname": "ws-2"},
        ]
    )

    # Sync run
    await test_db["sync_runs"].insert_one(
        {"run_id": "sync-1", "status": "completed", "completed_at": now - timedelta(hours=1)}
    )

    return test_db


# ── Classification Coverage Scope Fix ─────────────────────────────────────


class TestClassificationCoverageScopeFix:
    """Verify classification_coverage resolves scoped agent IDs before counting."""

    @pytest.mark.asyncio
    async def test_scope_filter_joins_via_agent_ids(
        self,
        scoped_agents: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """HIPAA-scoped check: 2 HIPAA agents, both classified — should pass."""
        from domains.compliance.checks.classification_coverage import execute

        result = await execute(
            scoped_agents,
            control_id="test-scope-fix",
            framework_id="hipaa",
            control_name="Classification Coverage",
            category="Admin Safeguards",
            severity="high",
            parameters={"min_classified_percent": 90},
            scope_filter={"tags": {"$in": ["HIPAA"]}},
        )
        # 2 HIPAA agents (agent-1, agent-2), both have classification results
        assert result.total_endpoints == 2
        assert result.compliant_endpoints == 2
        assert result.status.value == "pass"

    @pytest.mark.asyncio
    async def test_scope_filter_excludes_unscoped_agents(
        self,
        scoped_agents: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """PCI-CDE scope: only agent-1 matches, and it's classified — pass."""
        from domains.compliance.checks.classification_coverage import execute

        result = await execute(
            scoped_agents,
            control_id="test-scope-pci",
            framework_id="pci_dss_4",
            control_name="Classification Coverage",
            category="Security Policy",
            severity="high",
            parameters={"min_classified_percent": 90},
            scope_filter={"tags": {"$in": ["PCI-CDE"]}},
        )
        assert result.total_endpoints == 1
        assert result.compliant_endpoints == 1
        assert result.status.value == "pass"

    @pytest.mark.asyncio
    async def test_no_scope_includes_all_agents(
        self,
        scoped_agents: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Unscoped: 3 agents, 2 classified = 66.7%, threshold 90% — fail."""
        from domains.compliance.checks.classification_coverage import execute

        result = await execute(
            scoped_agents,
            control_id="test-all-agents",
            framework_id="soc2",
            control_name="Classification Coverage",
            category="Risk Assessment",
            severity="medium",
            parameters={"min_classified_percent": 90},
            scope_filter={},
        )
        assert result.total_endpoints == 3
        assert result.compliant_endpoints == 2
        assert result.non_compliant_endpoints == 1
        assert result.status.value == "fail"


# ── Custom App Presence Empty Pattern Fix ─────────────────────────────────


class TestCustomAppPresenceEmptyPattern:
    """Verify custom_app_presence returns not_applicable for empty app_pattern."""

    @pytest.mark.asyncio
    async def test_empty_pattern_returns_not_applicable(
        self,
        scoped_agents: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Empty app_pattern should return not_applicable, not error."""
        from domains.compliance.checks.custom_app_presence import execute

        result = await execute(
            scoped_agents,
            control_id="test-empty-pattern",
            framework_id="hipaa",
            control_name="VPN Software",
            category="Technical Safeguards",
            severity="medium",
            parameters={"app_pattern": "", "must_exist": True},
            scope_filter={},
        )
        assert result.status.value == "not_applicable"
        assert "configure" in result.evidence_summary.lower()

    @pytest.mark.asyncio
    async def test_configured_pattern_still_works(
        self,
        scoped_agents: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Non-empty pattern should work normally — SentinelOne present on all."""
        from domains.compliance.checks.custom_app_presence import execute

        result = await execute(
            scoped_agents,
            control_id="test-configured",
            framework_id="hipaa",
            control_name="EDR Software",
            category="Technical Safeguards",
            severity="critical",
            parameters={"app_pattern": "SentinelOne*", "must_exist": True},
            scope_filter={},
        )
        assert result.status.value == "pass"
        assert result.total_endpoints == 3


# ── Engine Check-Result Caching ───────────────────────────────────────────


class TestEngineCheckResultCaching:
    """Verify the engine deduplicates identical check executions."""

    @pytest.mark.asyncio
    async def test_cache_key_deterministic(self) -> None:
        """Same inputs produce the same cache key."""
        from domains.compliance.engine import _cache_key

        key1 = _cache_key("prohibited_app_check", {}, {})
        key2 = _cache_key("prohibited_app_check", {}, {})
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_cache_key_differs_with_params(self) -> None:
        """Different parameters produce different cache keys."""
        from domains.compliance.engine import _cache_key

        key1 = _cache_key("agent_online_check", {"max_offline_days": 7}, {})
        key2 = _cache_key("agent_online_check", {"max_offline_days": 3}, {})
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_cache_key_differs_with_scope(self) -> None:
        """Different scope filters produce different cache keys."""
        from domains.compliance.engine import _cache_key

        key1 = _cache_key("prohibited_app_check", {}, {})
        key2 = _cache_key("prohibited_app_check", {}, {"tags": {"$in": ["PCI-CDE"]}})
        assert key1 != key2

    @pytest.mark.asyncio
    async def test_remap_result_preserves_data(self) -> None:
        """Remapped result has correct control identity but same check data."""
        from domains.compliance.engine import ResolvedControl, _remap_result
        from domains.compliance.entities import (
            CheckResult,
            CheckStatus,
            ComplianceViolation,
            ControlSeverity,
        )

        now = utc_now()
        source = CheckResult(
            control_id="SOC2-CC6.7",
            framework_id="soc2",
            status=CheckStatus.failed,
            checked_at=now,
            total_endpoints=10,
            compliant_endpoints=8,
            non_compliant_endpoints=2,
            violations=[
                ComplianceViolation(
                    agent_id="a1",
                    agent_hostname="ws-1",
                    violation_detail="Prohibited app found",
                )
            ],
            evidence_summary="8/10 clean",
            severity=ControlSeverity.critical,
            category="Access Controls",
            control_name="No Prohibited Software",
        )

        target = ResolvedControl(
            control_id="DORA-9.3-01",
            framework_id="dora",
            name="Unauthorized Software Restriction",
            category="ICT Protection",
            severity=ControlSeverity.critical,
            check_type="prohibited_app_check",
            parameters={},
            scope_tags=[],
            scope_groups=[],
        )

        remapped = _remap_result(source, target)
        assert remapped.control_id == "DORA-9.3-01"
        assert remapped.framework_id == "dora"
        assert remapped.control_name == "Unauthorized Software Restriction"
        assert remapped.status == CheckStatus.failed
        assert remapped.total_endpoints == 10
        assert remapped.non_compliant_endpoints == 2
        assert len(remapped.violations) == 1


# ── Framework Definition Validation ───────────────────────────────────────


class TestFrameworkDefinitionValidation:
    """Validate that all 84 controls across 5 frameworks are well-formed."""

    def test_all_frameworks_have_controls(self) -> None:
        """Every framework must have at least 1 control."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        for fw in get_all_frameworks():
            controls = get_framework_controls(fw.id)
            assert len(controls) > 0, f"Framework {fw.id} has no controls"

    def test_total_control_count(self) -> None:
        """Verify total control count matches expected."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        total = sum(len(get_framework_controls(fw.id)) for fw in get_all_frameworks())
        assert total == 142, f"Expected 100 controls, found {total}"

    def test_all_control_ids_unique(self) -> None:
        """Control IDs must be globally unique."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        seen: set[str] = set()
        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                assert ctrl.id not in seen, f"Duplicate control ID: {ctrl.id}"
                seen.add(ctrl.id)

    def test_all_check_types_have_executors(self) -> None:
        """Every check_type used in a control must have a registered executor."""
        from domains.compliance.checks.registry import is_valid_check_type
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                assert is_valid_check_type(ctrl.check_type), (
                    f"Control {ctrl.id} uses unregistered check type: {ctrl.check_type}"
                )

    def test_all_severities_valid(self) -> None:
        """Every control must have a valid severity."""
        from domains.compliance.entities import ControlSeverity
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        valid = {s.value for s in ControlSeverity}
        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                assert ctrl.severity.value in valid, (
                    f"Control {ctrl.id} has invalid severity: {ctrl.severity}"
                )

    def test_all_controls_have_descriptions(self) -> None:
        """Every control must have a non-empty description."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                assert ctrl.description.strip(), f"Control {ctrl.id} has empty description"

    def test_all_controls_have_remediations(self) -> None:
        """Every control must have a non-empty remediation."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                assert ctrl.remediation.strip(), f"Control {ctrl.id} has empty remediation"

    def test_required_app_controls_with_empty_list(self) -> None:
        """Controls using required_app with empty list should be identifiable."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        empty_required = []
        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                if ctrl.check_type.value == "required_app_check" and not ctrl.parameters.get(
                    "required_apps"
                ):
                    empty_required.append(ctrl.id)

        # These should return not_applicable until configured
        assert len(empty_required) >= 1, "Expected some required_app controls with empty lists"

    def test_custom_app_presence_empty_pattern(self) -> None:
        """Controls with empty app_pattern should be identifiable as needing config."""
        from domains.compliance.frameworks.registry import (
            get_all_frameworks,
            get_framework_controls,
        )

        empty_pattern = []
        for fw in get_all_frameworks():
            for ctrl in get_framework_controls(fw.id):
                if ctrl.check_type.value == "custom_app_presence_check" and not ctrl.parameters.get(
                    "app_pattern"
                ):
                    empty_pattern.append(ctrl.id)

        # These should return not_applicable until configured
        assert len(empty_pattern) >= 1, "Expected some custom_app_presence controls needing config"


# ── Handbook Generation Tests ─────────────────────────────────────────────


class TestHandbookGeneration:
    """Test the handbook generation script produces valid output."""

    def test_generate_handbook_runs(self) -> None:
        """The generation function completes without errors."""
        from generate_compliance_handbook import generate_handbook

        content = generate_handbook()
        assert len(content) > 0

    def test_handbook_contains_all_frameworks(self) -> None:
        """Generated handbook mentions all 5 frameworks."""
        from generate_compliance_handbook import generate_handbook

        content = generate_handbook()
        assert "SOC 2" in content
        assert "PCI DSS" in content
        assert "HIPAA" in content
        assert "BSI IT-Grundschutz" in content
        assert "DORA" in content

    def test_handbook_contains_all_check_types(self) -> None:
        """Generated handbook documents all 11 check types."""
        from generate_compliance_handbook import generate_handbook

        content = generate_handbook()
        check_types = [
            "prohibited_app_check",
            "required_app_check",
            "agent_online_check",
            "agent_version_check",
            "app_version_check",
            "sync_freshness_check",
            "classification_coverage_check",
            "unclassified_threshold_check",
            "delta_detection_check",
            "custom_app_presence_check",
            "eol_software_check",
        ]
        for ct in check_types:
            assert ct in content, f"Check type {ct} not found in handbook"

    def test_handbook_idempotent(self) -> None:
        """Running twice produces identical output."""
        from generate_compliance_handbook import generate_handbook

        content1 = generate_handbook()
        content2 = generate_handbook()
        assert content1 == content2

    def test_handbook_no_broken_markdown_headers(self) -> None:
        """No malformed markdown headers (missing space after #)."""
        import re

        from generate_compliance_handbook import generate_handbook

        content = generate_handbook()
        # Malformed: #{1,6} followed by a non-space, non-# character
        # e.g. "#Bad" is broken but "## Good" and "###" are fine
        header_re = re.compile(r"^(#{1,6})([^#\s])")
        for line in content.split("\n"):
            match = header_re.match(line.strip())
            if match:
                msg = f"Malformed header (missing space): {line}"
                raise AssertionError(msg)
