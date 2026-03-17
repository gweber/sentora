"""Base protocol for compliance check executors.

Every check module must expose an ``execute`` function matching the
``CheckExecutor`` protocol.  The engine dispatches to the correct
module based on the ``CheckType`` discriminator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.entities import CheckResult, CheckStatus, ControlSeverity

MAX_VIOLATIONS = 10_000


class CheckExecutor(Protocol):
    """Callable protocol for a compliance check implementation.

    Args:
        db: Motor database handle (tenant-scoped).
        control_id: The control being evaluated.
        framework_id: The parent framework identifier.
        control_name: Human-readable control name.
        category: Control category for grouping.
        severity: Effective severity (after overrides).
        parameters: Merged parameters (defaults + overrides).
        scope_filter: Pre-built MongoDB filter for scoped agents.

    Returns:
        A fully populated ``CheckResult``.
    """

    async def __call__(
        self,
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        *,
        control_id: str,
        framework_id: str,
        control_name: str,
        category: str,
        severity: str,
        parameters: dict[str, Any],
        scope_filter: dict[str, Any],
    ) -> CheckResult: ...


def build_scope_filter(
    scope_tags: list[str],
    scope_groups: list[str],
) -> dict[str, Any]:
    """Build a MongoDB query filter from scope tags and groups.

    Delegates to the shared ``utils.scope.build_agent_scope_filter``
    utility.  Kept here for backward compatibility with the check
    executor call sites.

    Args:
        scope_tags: Tags to filter agents by.
        scope_groups: Group names to filter agents by.

    Returns:
        A MongoDB query filter dict.
    """
    from utils.scope import build_agent_scope_filter

    return build_agent_scope_filter(scope_tags=scope_tags, scope_groups=scope_groups)


def not_applicable_result(
    *,
    control_id: str,
    framework_id: str,
    control_name: str,
    category: str,
    severity: str,
    checked_at: datetime,
    evidence_summary: str = "No agents in scope",
) -> CheckResult:
    """Build a ``not_applicable`` CheckResult for empty-scope cases.

    Eliminates the repeated boilerplate across all 10 check modules.

    Args:
        control_id: The control being evaluated.
        framework_id: Parent framework.
        control_name: Human-readable control name.
        category: Control grouping category.
        severity: Effective severity level.
        checked_at: Evaluation timestamp.
        evidence_summary: Summary text (default: "No agents in scope").

    Returns:
        A ``CheckResult`` with ``not_applicable`` status and zero counts.
    """
    return CheckResult(
        control_id=control_id,
        framework_id=framework_id,
        status=CheckStatus.not_applicable,
        checked_at=checked_at,
        total_endpoints=0,
        compliant_endpoints=0,
        non_compliant_endpoints=0,
        violations=[],
        evidence_summary=evidence_summary,
        severity=ControlSeverity(severity),
        category=category,
        control_name=control_name,
    )
