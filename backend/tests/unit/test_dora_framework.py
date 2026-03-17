"""Unit tests for the DORA compliance framework definition.

Validates that the DORA framework and its 20 controls are correctly
defined with valid check types, severities, categories, and required
fields.  These tests verify the static definition — not engine execution.
"""

from __future__ import annotations

import pytest

from domains.compliance.entities import CheckType, ControlSeverity, FrameworkId
from domains.compliance.frameworks import dora
from domains.compliance.frameworks.registry import (
    get_all_framework_ids,
    get_control,
    get_framework,
    get_framework_controls,
)

# ── Valid enum values ────────────────────────────────────────────────────

_VALID_CHECK_TYPES = {ct.value for ct in CheckType}
_VALID_SEVERITIES = {s.value for s in ControlSeverity}


# ── Framework metadata ───────────────────────────────────────────────────


class TestDoraFrameworkMetadata:
    """Tests for DORA framework metadata correctness."""

    def test_framework_id(self) -> None:
        """DORA framework uses the dora FrameworkId."""
        assert dora.FRAMEWORK.id == FrameworkId.dora
        assert dora.FRAMEWORK.id == "dora"

    def test_framework_name(self) -> None:
        """DORA framework has the expected display name."""
        assert dora.FRAMEWORK.name == "DORA — Digital Operational Resilience Act"

    def test_framework_version(self) -> None:
        """DORA framework references EU 2022/2554."""
        assert dora.FRAMEWORK.version == "EU 2022/2554"

    def test_framework_has_description(self) -> None:
        """DORA framework has a non-empty description."""
        assert len(dora.FRAMEWORK.description) > 50

    def test_framework_has_disclaimer(self) -> None:
        """DORA framework has a non-empty legal disclaimer."""
        assert len(dora.FRAMEWORK.disclaimer) > 50
        assert "legal advice" in dora.FRAMEWORK.disclaimer.lower()

    def test_framework_registered_in_registry(self) -> None:
        """DORA appears in the global framework registry."""
        assert "dora" in get_all_framework_ids()
        fw = get_framework("dora")
        assert fw is not None
        assert fw.name == dora.FRAMEWORK.name


# ── Control count and structure ──────────────────────────────────────────


class TestDoraControlDefinitions:
    """Tests for DORA control definitions: count, fields, and validity."""

    def test_total_control_count(self) -> None:
        """DORA defines exactly 20 controls."""
        assert len(dora.CONTROLS) == 20

    def test_registry_returns_all_controls(self) -> None:
        """Registry returns 20 controls for the dora framework."""
        controls = get_framework_controls("dora")
        assert len(controls) == 20

    def test_all_control_ids_unique(self) -> None:
        """All 20 control IDs are unique."""
        ids = [c.id for c in dora.CONTROLS]
        assert len(ids) == len(set(ids))

    def test_all_controls_reference_dora_framework(self) -> None:
        """Every control references the dora framework ID."""
        for ctrl in dora.CONTROLS:
            assert ctrl.framework_id == FrameworkId.dora, (
                f"{ctrl.id} has framework_id={ctrl.framework_id}"
            )

    def test_all_check_types_are_valid(self) -> None:
        """Every control uses one of the 10 existing check types."""
        for ctrl in dora.CONTROLS:
            assert ctrl.check_type.value in _VALID_CHECK_TYPES, (
                f"{ctrl.id} has invalid check_type={ctrl.check_type}"
            )

    def test_all_severities_are_valid(self) -> None:
        """Every control has a valid severity level."""
        for ctrl in dora.CONTROLS:
            assert ctrl.severity.value in _VALID_SEVERITIES, (
                f"{ctrl.id} has invalid severity={ctrl.severity}"
            )

    def test_all_controls_have_non_empty_name(self) -> None:
        """Every control has a non-empty name."""
        for ctrl in dora.CONTROLS:
            assert ctrl.name, f"{ctrl.id} has empty name"

    def test_all_controls_have_non_empty_description(self) -> None:
        """Every control has a non-empty description."""
        for ctrl in dora.CONTROLS:
            assert len(ctrl.description) > 20, f"{ctrl.id} has too-short description"

    def test_all_controls_have_non_empty_remediation(self) -> None:
        """Every control has non-empty remediation guidance."""
        for ctrl in dora.CONTROLS:
            assert ctrl.remediation, f"{ctrl.id} has empty remediation"

    def test_all_controls_have_category(self) -> None:
        """Every control has a non-empty category."""
        for ctrl in dora.CONTROLS:
            assert ctrl.category, f"{ctrl.id} has empty category"

    def test_all_controls_lookup_by_id(self) -> None:
        """Every DORA control is findable via get_control()."""
        for ctrl in dora.CONTROLS:
            found = get_control(ctrl.id)
            assert found is not None, f"{ctrl.id} not found in registry"
            assert found.id == ctrl.id

    def test_no_hipaa_type_set(self) -> None:
        """DORA controls do not use HIPAA-specific hipaa_type field."""
        for ctrl in dora.CONTROLS:
            assert ctrl.hipaa_type is None, f"{ctrl.id} should not have hipaa_type"

    def test_no_bsi_level_set(self) -> None:
        """DORA controls do not use BSI-specific bsi_level field."""
        for ctrl in dora.CONTROLS:
            assert ctrl.bsi_level is None, f"{ctrl.id} should not have bsi_level"


# ── Category distribution ────────────────────────────────────────────────


class TestDoraCategoryDistribution:
    """Tests for correct control grouping by DORA article category."""

    @staticmethod
    def _controls_in_category(category_prefix: str) -> list[str]:
        """Return control IDs matching a category prefix."""
        return [c.id for c in dora.CONTROLS if category_prefix in c.category]

    def test_art8_has_6_controls(self) -> None:
        """ICT Asset Identification (Art. 8) has 6 controls."""
        ids = self._controls_in_category("Art. 8")
        assert len(ids) == 6
        assert set(ids) == {
            "DORA-8.1-01",
            "DORA-8.1-02",
            "DORA-8.4-01",
            "DORA-8.6-01",
            "DORA-8.2-01",
            "DORA-8.7-01",
        }

    def test_art9_has_7_controls(self) -> None:
        """ICT Protection & Prevention (Art. 9) has 7 controls."""
        ids = self._controls_in_category("Art. 9")
        assert len(ids) == 7
        assert set(ids) == {
            "DORA-9.1-01",
            "DORA-9.2-01",
            "DORA-9.2-02",
            "DORA-9.3-01",
            "DORA-9.3-02",
            "DORA-9.4-01",
            "DORA-9.4-02",
        }

    def test_art10_has_2_controls(self) -> None:
        """ICT Anomaly Detection (Art. 10) has 2 controls."""
        ids = self._controls_in_category("Art. 10")
        assert len(ids) == 2
        assert set(ids) == {"DORA-10.1-01", "DORA-10.1-02"}

    def test_art11_has_2_controls(self) -> None:
        """ICT Business Continuity (Art. 11) has 2 controls."""
        ids = self._controls_in_category("Art. 11")
        assert len(ids) == 2
        assert set(ids) == {"DORA-11.1-01", "DORA-11.2-01"}

    def test_art28_has_3_controls(self) -> None:
        """ICT Third-Party Software Risk (Art. 28) has 3 controls."""
        ids = self._controls_in_category("Art. 28")
        assert len(ids) == 3
        assert set(ids) == {"DORA-28.1-01", "DORA-28.1-02", "DORA-28.3-01"}

    def test_exactly_5_categories(self) -> None:
        """DORA uses exactly 5 distinct categories."""
        categories = {c.category for c in dora.CONTROLS}
        assert len(categories) == 5


# ── Configurable controls ────────────────────────────────────────────────


class TestDoraConfigurableControls:
    """Tests for controls that require tenant-specific configuration."""

    @pytest.mark.parametrize(
        "control_id",
        ["DORA-8.4-01", "DORA-9.2-01", "DORA-9.2-02"],
    )
    def test_configurable_controls_have_empty_required_apps(self, control_id: str) -> None:
        """Controls requiring configuration default to empty required_apps.

        The required_app check returns not_applicable when required_apps
        is empty, which is the correct default for unconfigured controls.
        """
        ctrl = get_control(control_id)
        assert ctrl is not None
        assert ctrl.check_type == CheckType.required_app
        assert ctrl.parameters.get("required_apps") == []

    @pytest.mark.parametrize(
        "control_id",
        ["DORA-8.4-01", "DORA-9.2-01", "DORA-9.2-02"],
    )
    def test_configurable_controls_mention_configuration_in_remediation(
        self, control_id: str
    ) -> None:
        """Configurable controls tell the MSP to configure them."""
        ctrl = get_control(control_id)
        assert ctrl is not None
        assert "configure" in ctrl.remediation.lower()


# ── Check type usage ─────────────────────────────────────────────────────


class TestDoraCheckTypeUsage:
    """Tests that DORA only uses existing check types and maps correctly."""

    def test_uses_only_existing_check_types(self) -> None:
        """DORA controls only use the 10 built-in check types."""
        used_types = {c.check_type for c in dora.CONTROLS}
        assert used_types.issubset(set(CheckType))

    def test_check_type_distribution(self) -> None:
        """Verify the distribution of check types across DORA controls."""
        type_counts: dict[str, int] = {}
        for ctrl in dora.CONTROLS:
            key = ctrl.check_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        assert type_counts["prohibited_app_check"] == 2
        assert type_counts["required_app_check"] == 3
        assert type_counts["agent_version_check"] == 1
        assert type_counts["agent_online_check"] == 2
        assert type_counts["app_version_check"] == 1
        assert type_counts["eol_software_check"] == 1
        assert type_counts["sync_freshness_check"] == 2
        assert type_counts["classification_coverage_check"] == 2
        assert type_counts["unclassified_threshold_check"] == 3
        assert type_counts["delta_detection_check"] == 3
        # custom_app_presence not used by DORA
        assert "custom_app_presence_check" not in type_counts
