"""Framework registry — aggregates all built-in framework definitions.

Provides lookup functions used by the engine, commands, and queries.
"""

from __future__ import annotations

from domains.compliance.entities import ComplianceFramework, ControlDefinition, FrameworkId
from domains.compliance.frameworks import bsi, hipaa, pci_dss, soc2

#: All built-in frameworks keyed by ID.
_FRAMEWORKS: dict[str, ComplianceFramework] = {
    soc2.FRAMEWORK.id: soc2.FRAMEWORK,
    pci_dss.FRAMEWORK.id: pci_dss.FRAMEWORK,
    hipaa.FRAMEWORK.id: hipaa.FRAMEWORK,
    bsi.FRAMEWORK.id: bsi.FRAMEWORK,
}

#: All built-in controls keyed by framework ID.
_CONTROLS: dict[str, list[ControlDefinition]] = {
    soc2.FRAMEWORK.id: soc2.CONTROLS,
    pci_dss.FRAMEWORK.id: pci_dss.CONTROLS,
    hipaa.FRAMEWORK.id: hipaa.CONTROLS,
    bsi.FRAMEWORK.id: bsi.CONTROLS,
}

#: Flat lookup of all controls by control ID.
_CONTROLS_BY_ID: dict[str, ControlDefinition] = {}
for _controls in _CONTROLS.values():
    for _ctrl in _controls:
        _CONTROLS_BY_ID[_ctrl.id] = _ctrl


def get_all_frameworks() -> list[ComplianceFramework]:
    """Return all built-in frameworks.

    Returns:
        List of all registered ``ComplianceFramework`` objects.
    """
    return list(_FRAMEWORKS.values())


def get_framework(framework_id: str) -> ComplianceFramework | None:
    """Look up a framework by ID.

    Args:
        framework_id: Framework identifier string.

    Returns:
        The framework, or ``None`` if not found.
    """
    return _FRAMEWORKS.get(framework_id)


def get_framework_controls(framework_id: str) -> list[ControlDefinition]:
    """Return all built-in controls for a framework.

    Args:
        framework_id: Framework identifier string.

    Returns:
        List of controls, or empty list if the framework is unknown.
    """
    return _CONTROLS.get(framework_id, [])


def get_control(control_id: str) -> ControlDefinition | None:
    """Look up a built-in control by its ID.

    Args:
        control_id: The control identifier string.

    Returns:
        The control definition, or ``None`` if not found.
    """
    return _CONTROLS_BY_ID.get(control_id)


def get_all_framework_ids() -> list[str]:
    """Return all known framework IDs.

    Returns:
        List of framework ID strings.
    """
    return list(_FRAMEWORKS.keys())


def is_valid_framework(framework_id: str) -> bool:
    """Check whether a framework ID is known.

    Args:
        framework_id: The framework identifier to validate.

    Returns:
        True if the framework exists.
    """
    return framework_id in _FRAMEWORKS
