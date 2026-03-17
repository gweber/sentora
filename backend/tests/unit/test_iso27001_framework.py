"""Unit tests for the ISO/IEC 27001:2022 compliance framework definition.

Validates that the ISO 27001 framework and its 16 controls are correctly
defined with valid check types, severities, categories, and required
fields.  These tests verify the static definition — not engine execution.
"""

from __future__ import annotations

from domains.compliance.entities import CheckType, ControlSeverity, FrameworkId
from domains.compliance.frameworks import iso27001
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


class TestIso27001FrameworkMetadata:
    """Tests for ISO 27001 framework metadata correctness."""

    def test_framework_id(self) -> None:
        """ISO 27001 framework uses the iso27001 FrameworkId."""
        assert iso27001.FRAMEWORK.id == FrameworkId.iso27001
        assert iso27001.FRAMEWORK.id == "iso27001"

    def test_framework_name(self) -> None:
        """ISO 27001 framework has the expected display name."""
        assert iso27001.FRAMEWORK.name == "ISO/IEC 27001:2022"

    def test_framework_version(self) -> None:
        """ISO 27001 framework references the 2022 edition."""
        assert iso27001.FRAMEWORK.version == "2022"

    def test_framework_has_description(self) -> None:
        """ISO 27001 framework has a non-empty description."""
        assert len(iso27001.FRAMEWORK.description) > 50

    def test_framework_has_disclaimer(self) -> None:
        """ISO 27001 framework has a non-empty legal disclaimer."""
        assert len(iso27001.FRAMEWORK.disclaimer) > 50
        assert "certification" in iso27001.FRAMEWORK.disclaimer.lower()

    def test_framework_registered_in_registry(self) -> None:
        """ISO 27001 appears in the global framework registry."""
        assert "iso27001" in get_all_framework_ids()
        fw = get_framework("iso27001")
        assert fw is not None
        assert fw.name == iso27001.FRAMEWORK.name


# ── Control count and structure ──────────────────────────────────────────


class TestIso27001ControlDefinitions:
    """Tests for ISO 27001 control definitions: count, fields, and validity."""

    def test_total_control_count(self) -> None:
        """ISO 27001 defines exactly 16 controls."""
        assert len(iso27001.CONTROLS) == 16

    def test_registry_returns_all_controls(self) -> None:
        """Registry returns 16 controls for the iso27001 framework."""
        controls = get_framework_controls("iso27001")
        assert len(controls) == 16

    def test_all_control_ids_unique(self) -> None:
        """All 16 control IDs are unique."""
        ids = [c.id for c in iso27001.CONTROLS]
        assert len(ids) == len(set(ids))

    def test_all_controls_reference_iso27001_framework(self) -> None:
        """Every control references the iso27001 framework ID."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.framework_id == FrameworkId.iso27001, (
                f"{ctrl.id} has framework_id={ctrl.framework_id}"
            )

    def test_all_check_types_are_valid(self) -> None:
        """Every control uses one of the existing check types."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.check_type.value in _VALID_CHECK_TYPES, (
                f"{ctrl.id} has invalid check_type={ctrl.check_type}"
            )

    def test_all_severities_are_valid(self) -> None:
        """Every control has a valid severity level."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.severity.value in _VALID_SEVERITIES, (
                f"{ctrl.id} has invalid severity={ctrl.severity}"
            )

    def test_all_controls_have_non_empty_name(self) -> None:
        """Every control has a non-empty name."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.name, f"{ctrl.id} has empty name"

    def test_all_controls_have_non_empty_description(self) -> None:
        """Every control has a non-empty description."""
        for ctrl in iso27001.CONTROLS:
            assert len(ctrl.description) > 20, f"{ctrl.id} has too-short description"

    def test_all_controls_have_non_empty_remediation(self) -> None:
        """Every control has non-empty remediation guidance."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.remediation, f"{ctrl.id} has empty remediation"

    def test_all_controls_have_category(self) -> None:
        """Every control has a non-empty category."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.category, f"{ctrl.id} has empty category"

    def test_all_controls_lookup_by_id(self) -> None:
        """Every ISO 27001 control is findable via get_control()."""
        for ctrl in iso27001.CONTROLS:
            found = get_control(ctrl.id)
            assert found is not None, f"{ctrl.id} not found in registry"
            assert found.id == ctrl.id

    def test_no_hipaa_type_set(self) -> None:
        """ISO 27001 controls do not use HIPAA-specific hipaa_type field."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.hipaa_type is None, f"{ctrl.id} should not have hipaa_type"

    def test_no_bsi_level_set(self) -> None:
        """ISO 27001 controls do not use BSI-specific bsi_level field."""
        for ctrl in iso27001.CONTROLS:
            assert ctrl.bsi_level is None, f"{ctrl.id} should not have bsi_level"


# ── Category distribution ────────────────────────────────────────────────


class TestIso27001CategoryDistribution:
    """Tests for correct control grouping by Annex A theme."""

    @staticmethod
    def _controls_in_category(category: str) -> list[str]:
        """Return control IDs matching a category."""
        return [c.id for c in iso27001.CONTROLS if c.category == category]

    def test_a5_organizational_controls(self) -> None:
        """A.5 Organizational Controls has 4 controls."""
        ids = self._controls_in_category("A.5 Organizational Controls")
        assert len(ids) == 4
        assert set(ids) == {
            "ISO-A.5.9",
            "ISO-A.5.9-SYNC",
            "ISO-A.5.10",
            "ISO-A.5.14",
        }

    def test_a8_technological_controls(self) -> None:
        """A.8 Technological Controls has 12 controls."""
        ids = self._controls_in_category("A.8 Technological Controls")
        assert len(ids) == 12

    def test_exactly_2_categories(self) -> None:
        """ISO 27001 uses exactly 2 distinct Annex A categories."""
        categories = {c.category for c in iso27001.CONTROLS}
        assert len(categories) == 2


# ── Configurable controls ────────────────────────────────────────────────


class TestIso27001ConfigurableControls:
    """Tests for controls that require tenant-specific configuration."""

    def test_required_app_control_has_empty_default(self) -> None:
        """ISO-A.8.19-REQ defaults to empty required_apps.

        The required_app check returns not_applicable when required_apps
        is empty, which is the correct default for unconfigured controls.
        """
        ctrl = get_control("ISO-A.8.19-REQ")
        assert ctrl is not None
        assert ctrl.check_type == CheckType.required_app
        assert ctrl.parameters.get("required_apps") == []

    def test_configurable_control_mentions_configuration(self) -> None:
        """The configurable control tells the user to configure it."""
        ctrl = get_control("ISO-A.8.19-REQ")
        assert ctrl is not None
        assert "configure" in ctrl.remediation.lower()


# ── Parameter differentiation ────────────────────────────────────────────


class TestIso27001ParameterDifferentiation:
    """Tests that controls using the same check type differ in parameters or scope."""

    def test_agent_online_controls_differ_in_threshold(self) -> None:
        """A.8.1 and A.8.7 use agent_online with different thresholds."""
        a81 = get_control("ISO-A.8.1")
        a87 = get_control("ISO-A.8.7")
        assert a81 is not None and a87 is not None
        assert a81.parameters["max_offline_days"] == 7
        assert a87.parameters["max_offline_days"] == 1

    def test_delta_detection_controls_differ_in_lookback(self) -> None:
        """A.8.9 and A.8.32 use delta_detection with different lookbacks."""
        a89 = get_control("ISO-A.8.9")
        a832 = get_control("ISO-A.8.32")
        assert a89 is not None and a832 is not None
        assert a89.parameters["lookback_hours"] == 24
        assert a832.parameters["lookback_hours"] == 48

    def test_prohibited_app_controls_differ_in_scope(self) -> None:
        """A.5.10 and A.8.19 use prohibited_app with different scopes."""
        a510 = get_control("ISO-A.5.10")
        a819 = get_control("ISO-A.8.19")
        assert a510 is not None and a819 is not None
        # A.5.10 applies fleet-wide (no scope)
        assert a510.scope_groups == []
        # A.8.19 scopes to Production group
        assert a819.scope_groups == ["Production"]

    def test_classification_coverage_controls_differ_in_threshold(self) -> None:
        """A.5.9, A.8.16, and A.8.25 use classification_coverage with different thresholds."""
        a59 = get_control("ISO-A.5.9")
        a816 = get_control("ISO-A.8.16")
        a825 = get_control("ISO-A.8.25")
        assert a59 is not None and a816 is not None and a825 is not None
        assert a816.parameters["min_classified_percent"] == 80
        assert a59.parameters["min_classified_percent"] == 90
        assert a825.parameters["min_classified_percent"] == 95

    def test_sync_freshness_controls_differ_in_threshold(self) -> None:
        """A.5.9-SYNC and A.5.14 use sync_freshness with different windows."""
        a59_sync = get_control("ISO-A.5.9-SYNC")
        a514 = get_control("ISO-A.5.14")
        assert a59_sync is not None and a514 is not None
        assert a59_sync.parameters["max_hours_since_sync"] == 24
        assert a514.parameters["max_hours_since_sync"] == 48


# ── Check type usage ─────────────────────────────────────────────────────


class TestIso27001CheckTypeUsage:
    """Tests that ISO 27001 only uses existing check types and maps correctly."""

    def test_uses_only_existing_check_types(self) -> None:
        """ISO 27001 controls only use the built-in check types."""
        used_types = {c.check_type for c in iso27001.CONTROLS}
        assert used_types.issubset(set(CheckType))

    def test_check_type_distribution(self) -> None:
        """Verify the distribution of check types across ISO 27001 controls."""
        type_counts: dict[str, int] = {}
        for ctrl in iso27001.CONTROLS:
            key = ctrl.check_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        assert type_counts["prohibited_app_check"] == 2
        assert type_counts["required_app_check"] == 1
        assert type_counts["agent_version_check"] == 1
        assert type_counts["agent_online_check"] == 2
        assert type_counts["app_version_check"] == 1
        assert type_counts["eol_software_check"] == 1
        assert type_counts["sync_freshness_check"] == 2
        assert type_counts["classification_coverage_check"] == 3
        assert type_counts["unclassified_threshold_check"] == 1
        assert type_counts["delta_detection_check"] == 2
        # custom_app_presence not used by ISO 27001
        assert "custom_app_presence_check" not in type_counts
