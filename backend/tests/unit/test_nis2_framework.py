"""Unit tests for the NIS2 compliance framework definition.

Validates that the NIS2 framework and its 13 controls are correctly
defined with valid check types, severities, categories, and required
fields.  These tests verify the static definition — not engine execution.
"""

from __future__ import annotations

from domains.compliance.entities import CheckType, ControlSeverity, FrameworkId
from domains.compliance.frameworks import nis2
from domains.compliance.frameworks.registry import (
    get_all_framework_ids,
    get_control,
    get_framework,
    get_framework_controls,
)

_VALID_CHECK_TYPES = {ct.value for ct in CheckType}
_VALID_SEVERITIES = {s.value for s in ControlSeverity}


class TestNis2FrameworkMetadata:
    """Tests for NIS2 framework metadata correctness."""

    def test_framework_id(self) -> None:
        """NIS2 framework uses the nis2 FrameworkId."""
        assert nis2.FRAMEWORK.id == FrameworkId.nis2
        assert nis2.FRAMEWORK.id == "nis2"

    def test_framework_name(self) -> None:
        """NIS2 framework has the expected display name."""
        assert "NIS2" in nis2.FRAMEWORK.name

    def test_framework_version(self) -> None:
        """NIS2 framework references EU directive 2022/2555."""
        assert "2022/2555" in nis2.FRAMEWORK.version

    def test_framework_has_description(self) -> None:
        """NIS2 framework has a non-empty description."""
        assert len(nis2.FRAMEWORK.description) > 50

    def test_framework_has_disclaimer(self) -> None:
        """NIS2 framework has a non-empty disclaimer."""
        assert len(nis2.FRAMEWORK.disclaimer) > 50
        assert "nis2" in nis2.FRAMEWORK.disclaimer.lower()

    def test_framework_registered_in_registry(self) -> None:
        """NIS2 appears in the global framework registry."""
        assert "nis2" in get_all_framework_ids()
        fw = get_framework("nis2")
        assert fw is not None
        assert fw.name == nis2.FRAMEWORK.name


class TestNis2ControlDefinitions:
    """Tests for NIS2 control definitions."""

    def test_total_control_count(self) -> None:
        """NIS2 defines exactly 13 controls."""
        assert len(nis2.CONTROLS) == 13

    def test_registry_returns_all_controls(self) -> None:
        """Registry returns 13 controls for the nis2 framework."""
        controls = get_framework_controls("nis2")
        assert len(controls) == 13

    def test_all_control_ids_unique(self) -> None:
        """All control IDs are unique."""
        ids = [c.id for c in nis2.CONTROLS]
        assert len(ids) == len(set(ids))

    def test_all_controls_reference_nis2_framework(self) -> None:
        """Every control references the nis2 framework ID."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.framework_id == FrameworkId.nis2, (
                f"{ctrl.id} has framework_id={ctrl.framework_id}"
            )

    def test_all_check_types_are_valid(self) -> None:
        """Every control uses a valid check type."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.check_type.value in _VALID_CHECK_TYPES, (
                f"{ctrl.id} has invalid check_type={ctrl.check_type}"
            )

    def test_all_severities_are_valid(self) -> None:
        """Every control has a valid severity level."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.severity.value in _VALID_SEVERITIES, (
                f"{ctrl.id} has invalid severity={ctrl.severity}"
            )

    def test_all_controls_have_non_empty_name(self) -> None:
        """Every control has a non-empty name."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.name, f"{ctrl.id} has empty name"

    def test_all_controls_have_non_empty_description(self) -> None:
        """Every control has a non-empty description."""
        for ctrl in nis2.CONTROLS:
            assert len(ctrl.description) > 20, f"{ctrl.id} has too-short description"

    def test_all_controls_have_non_empty_remediation(self) -> None:
        """Every control has non-empty remediation guidance."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.remediation, f"{ctrl.id} has empty remediation"

    def test_all_controls_have_category(self) -> None:
        """Every control has a non-empty category."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.category, f"{ctrl.id} has empty category"

    def test_all_controls_lookup_by_id(self) -> None:
        """Every NIS2 control is findable via get_control()."""
        for ctrl in nis2.CONTROLS:
            found = get_control(ctrl.id)
            assert found is not None, f"{ctrl.id} not found in registry"
            assert found.id == ctrl.id

    def test_control_ids_follow_naming_convention(self) -> None:
        """All control IDs start with NIS2-."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.id.startswith("NIS2-"), f"{ctrl.id} does not follow NIS2- naming convention"

    def test_no_hipaa_type_set(self) -> None:
        """NIS2 controls do not use HIPAA-specific fields."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.hipaa_type is None, f"{ctrl.id} should not have hipaa_type"

    def test_no_bsi_level_set(self) -> None:
        """NIS2 controls do not use BSI-specific fields."""
        for ctrl in nis2.CONTROLS:
            assert ctrl.bsi_level is None, f"{ctrl.id} should not have bsi_level"


class TestNis2CategoryDistribution:
    """Tests for correct control grouping by NIS2 article."""

    @staticmethod
    def _controls_in_category(substring: str) -> list[str]:
        """Return control IDs matching a category substring."""
        return [c.id for c in nis2.CONTROLS if substring in c.category]

    def test_art21_2a_controls(self) -> None:
        """Art. 21(2)(a) risk analysis has 4 controls."""
        assert len(self._controls_in_category("21.2a")) == 4

    def test_art21_2d_controls(self) -> None:
        """Art. 21(2)(d) supply chain has 2 controls."""
        assert len(self._controls_in_category("21.2d")) == 2

    def test_art21_2e_controls(self) -> None:
        """Art. 21(2)(e) acquisition/development/maintenance has 4 controls."""
        assert len(self._controls_in_category("21.2e")) == 4

    def test_art21_2h_controls(self) -> None:
        """Art. 21(2)(h) cyber hygiene has 2 controls."""
        assert len(self._controls_in_category("21.2h")) == 2

    def test_art21_2i_controls(self) -> None:
        """Art. 21(2)(i) cryptography has 1 control."""
        assert len(self._controls_in_category("21.2i")) == 1

    def test_exactly_5_categories(self) -> None:
        """NIS2 uses exactly 5 distinct categories."""
        categories = {c.category for c in nis2.CONTROLS}
        assert len(categories) == 5


class TestNis2CheckTypeUsage:
    """Tests that NIS2 only uses existing check types."""

    def test_uses_only_existing_check_types(self) -> None:
        """NIS2 controls only use the built-in check types."""
        used_types = {c.check_type for c in nis2.CONTROLS}
        assert used_types.issubset(set(CheckType))
