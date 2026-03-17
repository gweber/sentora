"""Unit tests for the NIST CSF 2.0 compliance framework definition.

Validates that the NIST CSF 2.0 framework and its 15 controls are
correctly defined with valid check types, severities, categories, and
required fields.  These tests verify the static definition — not engine
execution.
"""

from __future__ import annotations

from domains.compliance.entities import CheckType, ControlSeverity, FrameworkId
from domains.compliance.frameworks import nist_csf
from domains.compliance.frameworks.registry import (
    get_all_framework_ids,
    get_control,
    get_framework,
    get_framework_controls,
)

_VALID_CHECK_TYPES = {ct.value for ct in CheckType}
_VALID_SEVERITIES = {s.value for s in ControlSeverity}


class TestNistCsfFrameworkMetadata:
    """Tests for NIST CSF 2.0 framework metadata correctness."""

    def test_framework_id(self) -> None:
        """NIST CSF framework uses the nist_csf FrameworkId."""
        assert nist_csf.FRAMEWORK.id == FrameworkId.nist_csf
        assert nist_csf.FRAMEWORK.id == "nist_csf"

    def test_framework_name(self) -> None:
        """NIST CSF framework has the expected display name."""
        assert nist_csf.FRAMEWORK.name == "NIST CSF 2.0"

    def test_framework_version(self) -> None:
        """NIST CSF framework references version 2.0."""
        assert "2.0" in nist_csf.FRAMEWORK.version

    def test_framework_has_description(self) -> None:
        """NIST CSF framework has a non-empty description."""
        assert len(nist_csf.FRAMEWORK.description) > 50

    def test_framework_has_disclaimer(self) -> None:
        """NIST CSF framework has a non-empty disclaimer."""
        assert len(nist_csf.FRAMEWORK.disclaimer) > 50
        assert "nist csf" in nist_csf.FRAMEWORK.disclaimer.lower()

    def test_framework_registered_in_registry(self) -> None:
        """NIST CSF appears in the global framework registry."""
        assert "nist_csf" in get_all_framework_ids()
        fw = get_framework("nist_csf")
        assert fw is not None
        assert fw.name == nist_csf.FRAMEWORK.name


class TestNistCsfControlDefinitions:
    """Tests for NIST CSF 2.0 control definitions."""

    def test_total_control_count(self) -> None:
        """NIST CSF defines exactly 15 controls."""
        assert len(nist_csf.CONTROLS) == 15

    def test_registry_returns_all_controls(self) -> None:
        """Registry returns 15 controls for the nist_csf framework."""
        controls = get_framework_controls("nist_csf")
        assert len(controls) == 15

    def test_all_control_ids_unique(self) -> None:
        """All control IDs are unique."""
        ids = [c.id for c in nist_csf.CONTROLS]
        assert len(ids) == len(set(ids))

    def test_all_controls_reference_nist_csf_framework(self) -> None:
        """Every control references the nist_csf framework ID."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.framework_id == FrameworkId.nist_csf, (
                f"{ctrl.id} has framework_id={ctrl.framework_id}"
            )

    def test_all_check_types_are_valid(self) -> None:
        """Every control uses a valid check type."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.check_type.value in _VALID_CHECK_TYPES, (
                f"{ctrl.id} has invalid check_type={ctrl.check_type}"
            )

    def test_all_severities_are_valid(self) -> None:
        """Every control has a valid severity level."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.severity.value in _VALID_SEVERITIES, (
                f"{ctrl.id} has invalid severity={ctrl.severity}"
            )

    def test_all_controls_have_non_empty_name(self) -> None:
        """Every control has a non-empty name."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.name, f"{ctrl.id} has empty name"

    def test_all_controls_have_non_empty_description(self) -> None:
        """Every control has a non-empty description."""
        for ctrl in nist_csf.CONTROLS:
            assert len(ctrl.description) > 20, f"{ctrl.id} has too-short description"

    def test_all_controls_have_non_empty_remediation(self) -> None:
        """Every control has non-empty remediation guidance."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.remediation, f"{ctrl.id} has empty remediation"

    def test_all_controls_have_category(self) -> None:
        """Every control has a non-empty category."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.category, f"{ctrl.id} has empty category"

    def test_all_controls_lookup_by_id(self) -> None:
        """Every NIST CSF control is findable via get_control()."""
        for ctrl in nist_csf.CONTROLS:
            found = get_control(ctrl.id)
            assert found is not None, f"{ctrl.id} not found in registry"
            assert found.id == ctrl.id

    def test_control_ids_follow_naming_convention(self) -> None:
        """All control IDs start with NIST-."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.id.startswith("NIST-"), f"{ctrl.id} does not follow NIST- naming convention"

    def test_no_hipaa_type_set(self) -> None:
        """NIST CSF controls do not use HIPAA-specific fields."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.hipaa_type is None, f"{ctrl.id} should not have hipaa_type"

    def test_no_bsi_level_set(self) -> None:
        """NIST CSF controls do not use BSI-specific fields."""
        for ctrl in nist_csf.CONTROLS:
            assert ctrl.bsi_level is None, f"{ctrl.id} should not have bsi_level"


class TestNistCsfCategoryDistribution:
    """Tests for correct control grouping by CSF function."""

    @staticmethod
    def _controls_in_category(prefix: str) -> list[str]:
        """Return control IDs matching a category prefix."""
        return [c.id for c in nist_csf.CONTROLS if c.category.startswith(prefix)]

    def test_identify_controls(self) -> None:
        """Identify function has 4 controls."""
        assert len(self._controls_in_category("Identify")) == 4

    def test_protect_controls(self) -> None:
        """Protect function has 8 controls."""
        assert len(self._controls_in_category("Protect")) == 8

    def test_detect_controls(self) -> None:
        """Detect function has 3 controls."""
        assert len(self._controls_in_category("Detect")) == 3

    def test_exactly_3_categories(self) -> None:
        """NIST CSF uses exactly 3 distinct categories."""
        categories = {c.category for c in nist_csf.CONTROLS}
        assert len(categories) == 3


class TestNistCsfCheckTypeUsage:
    """Tests that NIST CSF only uses existing check types."""

    def test_uses_only_existing_check_types(self) -> None:
        """NIST CSF controls only use the built-in check types."""
        used_types = {c.check_type for c in nist_csf.CONTROLS}
        assert used_types.issubset(set(CheckType))

    def test_check_type_distribution(self) -> None:
        """Verify the distribution of check types across NIST CSF controls."""
        type_counts: dict[str, int] = {}
        for ctrl in nist_csf.CONTROLS:
            key = ctrl.check_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        assert type_counts["eol_software_check"] == 3
        assert type_counts["agent_online_check"] == 2
        assert type_counts["agent_version_check"] == 2
        assert type_counts["prohibited_app_check"] == 1
        assert type_counts["required_app_check"] == 1
        assert type_counts["classification_coverage_check"] == 1
        assert type_counts["unclassified_threshold_check"] == 1
        assert type_counts["sync_freshness_check"] == 1
        assert type_counts["delta_detection_check"] == 1
        assert type_counts["app_version_check"] == 1
        assert type_counts["custom_app_presence_check"] == 1
