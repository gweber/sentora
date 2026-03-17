"""Unit tests for the CIS Controls v8 compliance framework definition.

Validates that the CIS Controls v8 framework and its 14 controls are
correctly defined with valid check types, severities, categories, and
required fields.  These tests verify the static definition — not engine
execution.
"""

from __future__ import annotations

from domains.compliance.entities import CheckType, ControlSeverity, FrameworkId
from domains.compliance.frameworks import cis_v8
from domains.compliance.frameworks.registry import (
    get_all_framework_ids,
    get_control,
    get_framework,
    get_framework_controls,
)

_VALID_CHECK_TYPES = {ct.value for ct in CheckType}
_VALID_SEVERITIES = {s.value for s in ControlSeverity}


class TestCisV8FrameworkMetadata:
    """Tests for CIS Controls v8 framework metadata correctness."""

    def test_framework_id(self) -> None:
        """CIS v8 framework uses the cis_v8 FrameworkId."""
        assert cis_v8.FRAMEWORK.id == FrameworkId.cis_v8
        assert cis_v8.FRAMEWORK.id == "cis_v8"

    def test_framework_name(self) -> None:
        """CIS v8 framework has the expected display name."""
        assert cis_v8.FRAMEWORK.name == "CIS Controls v8"

    def test_framework_version(self) -> None:
        """CIS v8 framework references version 8.0."""
        assert "8.0" in cis_v8.FRAMEWORK.version

    def test_framework_has_description(self) -> None:
        """CIS v8 framework has a non-empty description."""
        assert len(cis_v8.FRAMEWORK.description) > 50

    def test_framework_has_disclaimer(self) -> None:
        """CIS v8 framework has a non-empty disclaimer."""
        assert len(cis_v8.FRAMEWORK.disclaimer) > 50
        assert "cis controls" in cis_v8.FRAMEWORK.disclaimer.lower()

    def test_framework_registered_in_registry(self) -> None:
        """CIS v8 appears in the global framework registry."""
        assert "cis_v8" in get_all_framework_ids()
        fw = get_framework("cis_v8")
        assert fw is not None
        assert fw.name == cis_v8.FRAMEWORK.name


class TestCisV8ControlDefinitions:
    """Tests for CIS Controls v8 control definitions."""

    def test_total_control_count(self) -> None:
        """CIS v8 defines exactly 14 controls."""
        assert len(cis_v8.CONTROLS) == 14

    def test_registry_returns_all_controls(self) -> None:
        """Registry returns 14 controls for the cis_v8 framework."""
        controls = get_framework_controls("cis_v8")
        assert len(controls) == 14

    def test_all_control_ids_unique(self) -> None:
        """All control IDs are unique."""
        ids = [c.id for c in cis_v8.CONTROLS]
        assert len(ids) == len(set(ids))

    def test_all_controls_reference_cis_v8_framework(self) -> None:
        """Every control references the cis_v8 framework ID."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.framework_id == FrameworkId.cis_v8, (
                f"{ctrl.id} has framework_id={ctrl.framework_id}"
            )

    def test_all_check_types_are_valid(self) -> None:
        """Every control uses a valid check type."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.check_type.value in _VALID_CHECK_TYPES, (
                f"{ctrl.id} has invalid check_type={ctrl.check_type}"
            )

    def test_all_severities_are_valid(self) -> None:
        """Every control has a valid severity level."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.severity.value in _VALID_SEVERITIES, (
                f"{ctrl.id} has invalid severity={ctrl.severity}"
            )

    def test_all_controls_have_non_empty_name(self) -> None:
        """Every control has a non-empty name."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.name, f"{ctrl.id} has empty name"

    def test_all_controls_have_non_empty_description(self) -> None:
        """Every control has a non-empty description."""
        for ctrl in cis_v8.CONTROLS:
            assert len(ctrl.description) > 20, f"{ctrl.id} has too-short description"

    def test_all_controls_have_non_empty_remediation(self) -> None:
        """Every control has non-empty remediation guidance."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.remediation, f"{ctrl.id} has empty remediation"

    def test_all_controls_have_category(self) -> None:
        """Every control has a non-empty category."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.category, f"{ctrl.id} has empty category"

    def test_all_controls_lookup_by_id(self) -> None:
        """Every CIS v8 control is findable via get_control()."""
        for ctrl in cis_v8.CONTROLS:
            found = get_control(ctrl.id)
            assert found is not None, f"{ctrl.id} not found in registry"
            assert found.id == ctrl.id

    def test_control_ids_follow_naming_convention(self) -> None:
        """All control IDs start with CIS-."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.id.startswith("CIS-"), f"{ctrl.id} does not follow CIS- naming convention"

    def test_no_hipaa_type_set(self) -> None:
        """CIS v8 controls do not use HIPAA-specific fields."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.hipaa_type is None, f"{ctrl.id} should not have hipaa_type"

    def test_no_bsi_level_set(self) -> None:
        """CIS v8 controls do not use BSI-specific fields."""
        for ctrl in cis_v8.CONTROLS:
            assert ctrl.bsi_level is None, f"{ctrl.id} should not have bsi_level"

    def test_implementation_groups_mentioned_in_descriptions(self) -> None:
        """Every CIS v8 control mentions its Implementation Group in the description."""
        for ctrl in cis_v8.CONTROLS:
            has_ig = any(ig in ctrl.description for ig in ("IG1", "IG2", "IG3"))
            assert has_ig, f"{ctrl.id} does not mention an Implementation Group"


class TestCisV8CategoryDistribution:
    """Tests for correct control grouping by CIS Control number."""

    @staticmethod
    def _controls_in_category(substring: str) -> list[str]:
        """Return control IDs matching a category substring."""
        return [c.id for c in cis_v8.CONTROLS if substring in c.category]

    def test_control_1_has_2_safeguards(self) -> None:
        """Control 1 (Enterprise Asset Inventory) has 2 safeguards."""
        assert len(self._controls_in_category("Control 1 —")) == 2

    def test_control_2_has_6_safeguards(self) -> None:
        """Control 2 (Software Asset Inventory) has 6 safeguards."""
        assert len(self._controls_in_category("Control 2")) == 6

    def test_control_7_has_3_safeguards(self) -> None:
        """Control 7 (Vulnerability Management) has 3 safeguards."""
        assert len(self._controls_in_category("Control 7")) == 3

    def test_control_10_has_3_safeguards(self) -> None:
        """Control 10 (Malware Defenses) has 3 safeguards."""
        assert len(self._controls_in_category("Control 10")) == 3

    def test_exactly_4_categories(self) -> None:
        """CIS v8 uses exactly 4 distinct categories."""
        categories = {c.category for c in cis_v8.CONTROLS}
        assert len(categories) == 4


class TestCisV8CheckTypeUsage:
    """Tests that CIS v8 only uses existing check types."""

    def test_uses_only_existing_check_types(self) -> None:
        """CIS v8 controls only use the built-in check types."""
        used_types = {c.check_type for c in cis_v8.CONTROLS}
        assert used_types.issubset(set(CheckType))
