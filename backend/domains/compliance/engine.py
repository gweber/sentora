"""Compliance check engine — orchestrates control evaluation.

The engine resolves the active controls for enabled frameworks, merges
tenant overrides, dispatches to the appropriate check executor, and
collects results.  It is the single entry point for running compliance
checks.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bson import ObjectId
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.base import build_scope_filter
from domains.compliance.checks.registry import get_executor
from domains.compliance.entities import (
    CheckResult,
    CheckStatus,
    ControlConfiguration,
    ControlSeverity,
)
from domains.compliance.frameworks.registry import (
    get_all_framework_ids,
    get_framework_controls,
)
from domains.compliance.repository import (
    get_all_control_configs,
    get_all_framework_configs,
    list_custom_controls,
    store_check_results,
)
from utils.dt import utc_now


@dataclass(slots=True)
class ResolvedControl:
    """A control with all overrides merged and ready to execute.

    Attributes:
        control_id: Unique control identifier.
        framework_id: Parent framework.
        name: Human-readable name.
        category: Grouping category.
        severity: Effective severity (after override).
        check_type: Which executor to dispatch to.
        parameters: Merged parameters.
        scope_tags: Effective scope tags.
        scope_groups: Effective scope groups.
    """

    control_id: str
    framework_id: str
    name: str
    category: str
    severity: ControlSeverity
    check_type: str
    parameters: dict[str, Any]
    scope_tags: list[str]
    scope_groups: list[str]


async def resolve_active_controls(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> list[ResolvedControl]:
    """Resolve all active controls with tenant overrides applied.

    Merges built-in control definitions with tenant-specific
    configurations (enabled/disabled, parameter overrides, scope
    overrides).

    Args:
        db: Motor database handle.
        framework_id: Optional filter to a single framework.

    Returns:
        List of controls ready for execution.
    """
    framework_configs = await get_all_framework_configs(db)

    # Determine which frameworks to evaluate
    framework_ids = [framework_id] if framework_id else get_all_framework_ids()

    # Load all control configs in one query
    control_configs = await get_all_control_configs(db, framework_id)
    config_map: dict[str, ControlConfiguration] = {
        f"{c.framework_id}:{c.control_id}": c for c in control_configs
    }

    resolved: list[ResolvedControl] = []

    for fw_id in framework_ids:
        # Skip disabled frameworks
        if not framework_configs.get(fw_id, False):
            continue

        # Built-in controls
        for defn in get_framework_controls(fw_id):
            config_key = f"{fw_id}:{defn.id}"
            config = config_map.get(config_key)

            # Skip disabled controls
            if config and not config.enabled:
                continue

            # Merge parameters
            merged_params = dict(defn.parameters)
            if config and config.parameters_override:
                merged_params.update(config.parameters_override)

            # Resolve severity
            severity = (
                config.severity_override if config and config.severity_override else defn.severity
            )

            # Resolve scope
            scope_tags = (
                config.scope_tags_override
                if config and config.scope_tags_override is not None
                else list(defn.scope_tags)
            )
            scope_groups = (
                config.scope_groups_override
                if config and config.scope_groups_override is not None
                else list(defn.scope_groups)
            )

            resolved.append(
                ResolvedControl(
                    control_id=defn.id,
                    framework_id=fw_id,
                    name=defn.name,
                    category=defn.category,
                    severity=severity,
                    check_type=defn.check_type,
                    parameters=merged_params,
                    scope_tags=scope_tags,
                    scope_groups=scope_groups,
                )
            )

        # Custom controls for this framework
        custom_controls = await list_custom_controls(db, fw_id)
        for custom in custom_controls:
            config_key = f"{fw_id}:{custom.id}"
            config = config_map.get(config_key)
            if config and not config.enabled:
                continue

            merged_params = dict(custom.parameters)
            if config and config.parameters_override:
                merged_params.update(config.parameters_override)

            severity = (
                config.severity_override if config and config.severity_override else custom.severity
            )
            scope_tags = (
                config.scope_tags_override
                if config and config.scope_tags_override is not None
                else list(custom.scope_tags)
            )
            scope_groups = (
                config.scope_groups_override
                if config and config.scope_groups_override is not None
                else list(custom.scope_groups)
            )

            resolved.append(
                ResolvedControl(
                    control_id=custom.id,
                    framework_id=fw_id,
                    name=custom.name,
                    category=custom.category,
                    severity=severity,
                    check_type=custom.check_type,
                    parameters=merged_params,
                    scope_tags=scope_tags,
                    scope_groups=scope_groups,
                )
            )

    return resolved


async def run_compliance_checks(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> tuple[str, list[CheckResult], int]:
    """Execute all active compliance checks and persist results.

    Args:
        db: Motor database handle.
        framework_id: Optional filter to a single framework.

    Returns:
        Tuple of (run_id, list of results, duration_ms).
    """
    run_id = str(ObjectId())
    start = time.monotonic()

    controls = await resolve_active_controls(db, framework_id)
    if not controls:
        logger.info("No active compliance controls to evaluate")
        return run_id, [], 0

    logger.info(
        "Running compliance checks: {} controls across {} framework(s)",
        len(controls),
        len({c.framework_id for c in controls}),
    )

    # Execute all checks concurrently
    tasks = []
    for ctrl in controls:
        executor = get_executor(ctrl.check_type)
        if executor is None:
            logger.warning(
                "No executor for check type '{}' (control {})",
                ctrl.check_type,
                ctrl.control_id,
            )
            continue

        scope_filter = build_scope_filter(ctrl.scope_tags, ctrl.scope_groups)
        tasks.append(
            _execute_check(
                executor,
                db,
                ctrl=ctrl,
                scope_filter=scope_filter,
            )
        )

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[CheckResult] = []
    for idx, result in enumerate(raw_results):
        if isinstance(result, Exception):
            ctrl = controls[idx]
            logger.error(
                "Check {} failed with error: {}",
                ctrl.control_id,
                result,
            )
            results.append(
                CheckResult(
                    control_id=ctrl.control_id,
                    framework_id=ctrl.framework_id,
                    status=CheckStatus.error,
                    checked_at=utc_now(),
                    total_endpoints=0,
                    compliant_endpoints=0,
                    non_compliant_endpoints=0,
                    violations=[],
                    evidence_summary=f"Check execution error: {result}",
                    severity=ctrl.severity,
                    category=ctrl.category,
                    control_name=ctrl.name,
                )
            )
        else:
            results.append(result)

    # Persist results
    await store_check_results(db, run_id, results)

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Compliance run {} completed: {} checks in {}ms",
        run_id,
        len(results),
        duration_ms,
    )

    return run_id, results, duration_ms


async def _execute_check(
    executor: Callable[..., Any],
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    ctrl: ResolvedControl,
    scope_filter: dict[str, Any],
) -> CheckResult:
    """Execute a single check with error boundary.

    Args:
        executor: The check executor function.
        db: Motor database handle.
        ctrl: The resolved control to evaluate.
        scope_filter: Pre-built MongoDB scope filter.

    Returns:
        The check result.
    """
    return await executor(
        db,
        control_id=ctrl.control_id,
        framework_id=ctrl.framework_id,
        control_name=ctrl.name,
        category=ctrl.category,
        severity=ctrl.severity.value,
        parameters=ctrl.parameters,
        scope_filter=scope_filter,
    )
