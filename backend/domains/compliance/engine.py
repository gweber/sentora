"""Compliance check engine — orchestrates control evaluation.

The engine resolves the active controls for enabled frameworks, merges
tenant overrides, dispatches to the appropriate check executor, and
collects results.  It is the single entry point for running compliance
checks.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
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


def _cache_key(check_type: str, parameters: dict[str, Any], scope_filter: dict[str, Any]) -> str:
    """Build a deterministic cache key for check deduplication.

    Controls that share the same check type, parameters, and scope will
    produce identical query results.  This key allows the engine to
    execute the query once and map the result to all matching controls.

    Args:
        check_type: The check type string.
        parameters: Merged check parameters.
        scope_filter: Pre-built MongoDB scope filter.

    Returns:
        A hex digest string uniquely identifying this query.
    """
    raw = json.dumps(
        {"t": check_type, "p": parameters, "s": scope_filter},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _remap_result(source: CheckResult, ctrl: ResolvedControl) -> CheckResult:
    """Create a copy of a check result remapped to a different control.

    Used when a cached check result needs to be attributed to another
    control that shares the same check type, parameters, and scope.

    Args:
        source: The original check result to copy data from.
        ctrl: The target control to remap to.

    Returns:
        A new CheckResult with the target control's identity.
    """
    return CheckResult(
        control_id=ctrl.control_id,
        framework_id=ctrl.framework_id,
        status=source.status,
        checked_at=source.checked_at,
        total_endpoints=source.total_endpoints,
        compliant_endpoints=source.compliant_endpoints,
        non_compliant_endpoints=source.non_compliant_endpoints,
        violations=list(source.violations),
        evidence_summary=source.evidence_summary,
        severity=ctrl.severity,
        category=ctrl.category,
        control_name=ctrl.name,
    )


async def run_compliance_checks(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> tuple[str, list[CheckResult], int]:
    """Execute all active compliance checks and persist results.

    Implements check-result caching: controls that share the same
    check type, parameters, and scope are only executed once.  The
    result is then remapped to each duplicate control with the
    correct control identity metadata.

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

    # Group controls by cache key to deduplicate identical queries.
    # Only the first control per key is executed; results are remapped.
    cache_key_map: dict[str, list[ResolvedControl]] = {}
    primary_controls: list[ResolvedControl] = []

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
        key = _cache_key(ctrl.check_type, ctrl.parameters, scope_filter)

        if key not in cache_key_map:
            cache_key_map[key] = [ctrl]
            primary_controls.append(ctrl)
        else:
            cache_key_map[key].append(ctrl)

    deduplicated = len(controls) - len(primary_controls)
    if deduplicated > 0:
        logger.info(
            "Check deduplication: {} unique queries for {} controls ({} cached)",
            len(primary_controls),
            len(controls),
            deduplicated,
        )

    # Execute unique checks concurrently.  Track the cache key for each
    # primary control so we can map results back correctly.
    tasks = []
    primary_keys: list[str] = []
    for ctrl in primary_controls:
        executor = get_executor(ctrl.check_type)
        assert executor is not None  # Already validated above  # noqa: S101
        sf = build_scope_filter(ctrl.scope_tags, ctrl.scope_groups)
        key = _cache_key(ctrl.check_type, ctrl.parameters, sf)
        primary_keys.append(key)
        tasks.append(_execute_check(executor, db, ctrl=ctrl, scope_filter=sf))

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Map results back to all controls (including duplicates)
    results: list[CheckResult] = []
    for idx, result in enumerate(raw_results):
        ctrl = primary_controls[idx]
        key = primary_keys[idx]

        if isinstance(result, BaseException):
            logger.error("Check {} failed with error: {}", ctrl.control_id, result)
            error_result = CheckResult(
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
            results.append(error_result)
            # Remap error to duplicates
            for dup_ctrl in cache_key_map[key][1:]:
                results.append(_remap_result(error_result, dup_ctrl))
        else:
            results.append(result)
            # Remap successful result to duplicates
            for dup_ctrl in cache_key_map[key][1:]:
                results.append(_remap_result(result, dup_ctrl))

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
