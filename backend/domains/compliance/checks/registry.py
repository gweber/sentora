"""Check type registry.

Maps ``CheckType`` enum values to their executor modules.  The engine
uses this registry to dispatch control evaluations.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from domains.compliance.checks import (
    agent_online,
    agent_version,
    app_version,
    classification_coverage,
    custom_app_presence,
    delta_detection,
    eol_software,
    prohibited_app,
    required_app,
    sync_freshness,
    unclassified_threshold,
)
from domains.compliance.entities import CheckType

#: Maps each ``CheckType`` to its executor function.
_REGISTRY: dict[str, Any] = {
    CheckType.prohibited_app: prohibited_app.execute,
    CheckType.required_app: required_app.execute,
    CheckType.agent_version: agent_version.execute,
    CheckType.agent_online: agent_online.execute,
    CheckType.app_version: app_version.execute,
    CheckType.sync_freshness: sync_freshness.execute,
    CheckType.classification_coverage: classification_coverage.execute,
    CheckType.unclassified_threshold: unclassified_threshold.execute,
    CheckType.delta_detection: delta_detection.execute,
    CheckType.custom_app_presence: custom_app_presence.execute,
    CheckType.eol_software: eol_software.execute,
}


def get_executor(
    check_type: str,
) -> Callable[..., Any] | None:
    """Look up the executor function for a check type.

    Args:
        check_type: The ``CheckType`` value string.

    Returns:
        The executor callable, or ``None`` if the type is unknown.
    """
    return _REGISTRY.get(check_type)


def is_valid_check_type(check_type: str) -> bool:
    """Return whether the given check type has a registered executor.

    Args:
        check_type: The check type string to validate.

    Returns:
        True if the check type is known.
    """
    return check_type in _REGISTRY
