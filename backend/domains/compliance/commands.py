"""Compliance domain — command handlers (CQRS write side).

All state-mutating operations go through this module.  Each function
validates input, applies business rules, and delegates persistence to
the repository.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from domains.compliance.checks.registry import is_valid_check_type
from domains.compliance.entities import (
    CheckResult,
    CheckType,
    ComplianceSchedule,
    ControlConfiguration,
    ControlSeverity,
    CustomControlDefinition,
)
from domains.compliance.engine import run_compliance_checks
from domains.compliance.frameworks.registry import (
    get_control,
    get_framework,
    is_valid_framework,
)
from domains.compliance.repository import (
    get_custom_control,
    insert_custom_control,
    set_framework_enabled,
    upsert_control_config,
    upsert_schedule,
)
from errors import (
    ComplianceRunInProgressError,
    ControlNotFoundError,
    CustomControlAlreadyExistsError,
    FrameworkNotFoundError,
    InvalidCheckTypeError,
)
from utils.dt import utc_now


async def enable_framework(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str,
    *,
    actor: str,
) -> None:
    """Enable a compliance framework for the tenant.

    Args:
        db: Motor database handle.
        framework_id: The framework to enable.
        actor: Username performing the action.

    Raises:
        FrameworkNotFoundError: If the framework ID is unknown.
    """
    if not is_valid_framework(framework_id):
        raise FrameworkNotFoundError(f"Unknown framework: {framework_id}")

    await set_framework_enabled(db, framework_id, enabled=True, actor=actor)
    await audit(
        db,
        domain="compliance",
        action="compliance.framework.enabled",
        actor=actor,
        summary=f"Enabled compliance framework: {framework_id}",
    )


async def disable_framework(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str,
    *,
    actor: str,
) -> None:
    """Disable a compliance framework for the tenant.

    Args:
        db: Motor database handle.
        framework_id: The framework to disable.
        actor: Username performing the action.

    Raises:
        FrameworkNotFoundError: If the framework ID is unknown.
    """
    if not is_valid_framework(framework_id):
        raise FrameworkNotFoundError(f"Unknown framework: {framework_id}")

    await set_framework_enabled(db, framework_id, enabled=False, actor=actor)
    await audit(
        db,
        domain="compliance",
        action="compliance.framework.disabled",
        actor=actor,
        summary=f"Disabled compliance framework: {framework_id}",
    )


async def configure_control(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    control_id: str,
    *,
    actor: str,
    enabled: bool | None = None,
    severity_override: str | None = None,
    parameters_override: dict[str, Any] | None = None,
    scope_tags_override: list[str] | None = None,
    scope_groups_override: list[str] | None = None,
) -> ControlConfiguration:
    """Update a control's tenant-specific configuration.

    Args:
        db: Motor database handle.
        control_id: The control to configure.
        actor: Username performing the action.
        enabled: Override enabled state.
        severity_override: Override severity level.
        parameters_override: Override check parameters.
        scope_tags_override: Override scope tags.
        scope_groups_override: Override scope groups.

    Returns:
        The updated control configuration.

    Raises:
        ControlNotFoundError: If the control ID is unknown.
    """
    # Resolve the control (built-in or custom)
    defn = get_control(control_id)
    custom = await get_custom_control(db, control_id) if defn is None else None

    if defn is None and custom is None:
        raise ControlNotFoundError(f"Unknown control: {control_id}")

    framework_id = defn.framework_id if defn else custom.framework_id  # type: ignore[union-attr]

    # Validate severity if provided
    parsed_severity: ControlSeverity | None = None
    if severity_override is not None:
        parsed_severity = ControlSeverity(severity_override)

    now = utc_now()
    config = ControlConfiguration(
        control_id=control_id,
        framework_id=framework_id,
        enabled=enabled if enabled is not None else True,
        severity_override=parsed_severity,
        parameters_override=parameters_override or {},
        scope_tags_override=scope_tags_override,
        scope_groups_override=scope_groups_override,
        updated_at=now,
        updated_by=actor,
    )

    await upsert_control_config(db, config)
    await audit(
        db,
        domain="compliance",
        action="compliance.control.configured",
        actor=actor,
        summary=f"Configured control {control_id}",
        details={
            "control_id": control_id,
            "enabled": config.enabled,
            "severity_override": severity_override,
        },
    )

    return config


async def create_custom_control(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    actor: str,
    control_id: str,
    framework_id: str,
    name: str,
    description: str,
    category: str,
    severity: str,
    check_type: str,
    parameters: dict[str, Any],
    scope_tags: list[str],
    scope_groups: list[str],
    remediation: str,
) -> CustomControlDefinition:
    """Create a new tenant-specific custom control.

    Args:
        db: Motor database handle.
        actor: Username performing the action.
        control_id: Must start with ``custom-``.
        framework_id: Which framework this control belongs to.
        name: Human-readable control name.
        description: What this control checks.
        category: Grouping category.
        severity: Severity level string.
        check_type: Which check implementation to use.
        parameters: Check parameters.
        scope_tags: S1 tags to scope.
        scope_groups: S1 group names to scope.
        remediation: Remediation guidance.

    Returns:
        The created custom control.

    Raises:
        FrameworkNotFoundError: If the framework is unknown.
        InvalidCheckTypeError: If the check type is invalid.
        CustomControlAlreadyExistsError: If the ID already exists.
    """
    if not is_valid_framework(framework_id):
        raise FrameworkNotFoundError(f"Unknown framework: {framework_id}")

    if not is_valid_check_type(check_type):
        raise InvalidCheckTypeError(f"Unknown check type: {check_type}")

    # Check for duplicates (built-in or custom)
    if get_control(control_id) is not None:
        raise CustomControlAlreadyExistsError(
            f"Control ID '{control_id}' conflicts with a built-in control"
        )
    existing = await get_custom_control(db, control_id)
    if existing is not None:
        raise CustomControlAlreadyExistsError(
            f"Custom control '{control_id}' already exists"
        )

    now = utc_now()
    custom = CustomControlDefinition(
        id=control_id,
        framework_id=framework_id,
        name=name,
        description=description,
        category=category,
        severity=ControlSeverity(severity),
        check_type=CheckType(check_type),
        parameters=parameters,
        scope_tags=scope_tags,
        scope_groups=scope_groups,
        remediation=remediation,
        created_at=now,
        created_by=actor,
    )

    await insert_custom_control(db, custom)
    await audit(
        db,
        domain="compliance",
        action="compliance.control.custom_created",
        actor=actor,
        summary=f"Created custom control: {control_id}",
        details={"control_id": control_id, "framework_id": framework_id},
    )

    return custom


async def trigger_compliance_run(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    actor: str,
    framework_id: str | None = None,
) -> tuple[str, list[CheckResult], int]:
    """Trigger a compliance check run.

    After evaluation, dispatches webhook events for:
    - ``compliance.check.completed`` — summary of the run
    - ``compliance.violation.new`` — newly detected violations
    - ``compliance.violation.resolved`` — violations no longer present
    - ``compliance.score.degraded`` — framework score dropped below threshold

    Args:
        db: Motor database handle.
        actor: Username triggering the run.
        framework_id: Optional filter to a single framework.

    Returns:
        Tuple of (run_id, results, duration_ms).
    """
    from domains.compliance.repository import get_latest_results

    # Capture previous state for delta detection
    prev_results = await get_latest_results(db, framework_id)
    prev_violation_keys: set[str] = set()
    prev_scores: dict[str, tuple[int, int]] = {}  # fw_id → (passed, total)
    for r in prev_results:
        fw = r.get("framework_id", "")
        status = r.get("status", "")
        p, t = prev_scores.get(fw, (0, 0))
        prev_scores[fw] = (p + (1 if status == "pass" else 0), t + 1)
        if status == "fail":
            for v in r.get("violations", []):
                prev_violation_keys.add(
                    f"{r.get('control_id', '')}:{v.get('agent_id', v.get('hostname', ''))}"
                )

    run_id, results, duration_ms = await run_compliance_checks(db, framework_id)

    # Compute run summary
    passed = sum(1 for r in results if r.status == CheckStatus.passed)
    failed = sum(1 for r in results if r.status == CheckStatus.failed)
    warning = sum(1 for r in results if r.status == CheckStatus.warning)

    # Detect new and resolved violations
    new_violation_keys: set[str] = set()
    for r in results:
        if r.status == CheckStatus.failed:
            for v in r.violations:
                key = f"{r.control_id}:{v.agent_id if hasattr(v, 'agent_id') else getattr(v, 'hostname', '')}"
                new_violation_keys.add(key)

    new_violations = new_violation_keys - prev_violation_keys
    resolved_violations = prev_violation_keys - new_violation_keys

    await audit(
        db,
        domain="compliance",
        action="compliance.run.completed",
        actor=actor,
        summary=(
            f"Compliance run {run_id}: {len(results)} controls evaluated "
            f"in {duration_ms}ms"
        ),
        details={
            "run_id": run_id,
            "controls_evaluated": len(results),
            "duration_ms": duration_ms,
            "new_violations": len(new_violations),
            "resolved_violations": len(resolved_violations),
        },
    )

    # Dispatch webhooks (fire-and-forget, never block the response)
    await _dispatch_compliance_webhooks(
        db,
        results=results,
        run_id=run_id,
        passed=passed,
        failed=failed,
        warning=warning,
        new_violations=new_violations,
        resolved_violations=resolved_violations,
        prev_scores=prev_scores,
    )

    return run_id, results, duration_ms


#: Default compliance score threshold (percent) below which degradation fires.
_DEFAULT_SCORE_THRESHOLD = 80


async def _dispatch_compliance_webhooks(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    results: list[CheckResult],
    run_id: str,
    passed: int,
    failed: int,
    warning: int,
    new_violations: set[str],
    resolved_violations: set[str],
    prev_scores: dict[str, tuple[int, int]],
) -> None:
    """Dispatch all compliance webhook events after a check run.

    Args:
        db: Motor database handle.
        results: Check results from the current run.
        run_id: Unique run identifier.
        passed: Number of controls that passed.
        failed: Number of controls that failed.
        warning: Number of controls with warnings.
        new_violations: Violation keys that are new since the previous run.
        resolved_violations: Violation keys that were resolved since the previous run.
        prev_scores: Per-framework (passed, total) from the previous run.
    """
    try:
        from domains.webhooks.service import dispatch_event

        # 1. compliance.check.completed
        await dispatch_event(db, "compliance.check.completed", {
            "run_id": run_id,
            "controls_evaluated": len(results),
            "controls_passed": passed,
            "controls_failed": failed,
            "controls_warning": warning,
            "new_violations": len(new_violations),
            "resolved_violations": len(resolved_violations),
            "source": "compliance",
        })

        # 2. compliance.violation.new — aggregated by control
        if new_violations:
            by_control: dict[str, list[str]] = {}
            for key in new_violations:
                ctrl_id, agent_ref = key.split(":", 1)
                by_control.setdefault(ctrl_id, []).append(agent_ref)

            for ctrl_id, agents in by_control.items():
                ctrl_result = next((r for r in results if r.control_id == ctrl_id), None)
                await dispatch_event(db, "compliance.violation.new", {
                    "framework": ctrl_result.framework_id if ctrl_result else "",
                    "control_id": ctrl_id,
                    "control_name": ctrl_result.control_name if ctrl_result else ctrl_id,
                    "severity": ctrl_result.severity if ctrl_result else "medium",
                    "affected_agents": len(agents),
                    "summary": ctrl_result.evidence_summary if ctrl_result else "",
                    "source": "compliance",
                })

        # 3. compliance.violation.resolved — aggregated by control
        if resolved_violations:
            by_control_resolved: dict[str, list[str]] = {}
            for key in resolved_violations:
                ctrl_id, agent_ref = key.split(":", 1)
                by_control_resolved.setdefault(ctrl_id, []).append(agent_ref)

            for ctrl_id, agents in by_control_resolved.items():
                await dispatch_event(db, "compliance.violation.resolved", {
                    "control_id": ctrl_id,
                    "previously_affected": len(agents),
                    "source": "compliance",
                })

        # 4. compliance.score.degraded — per-framework score drop detection
        cur_scores: dict[str, tuple[int, int]] = {}
        for r in results:
            p, t = cur_scores.get(r.framework_id, (0, 0))
            cur_scores[r.framework_id] = (
                p + (1 if r.status == CheckStatus.passed else 0),
                t + 1,
            )

        for fw_id, (cur_passed, cur_total) in cur_scores.items():
            if cur_total == 0:
                continue
            cur_score = int(cur_passed / cur_total * 100)
            prev_passed, prev_total = prev_scores.get(fw_id, (0, 0))
            prev_score = int(prev_passed / prev_total * 100) if prev_total else 100

            if cur_score < _DEFAULT_SCORE_THRESHOLD <= prev_score:
                await dispatch_event(db, "compliance.score.degraded", {
                    "framework": fw_id,
                    "previous_score": prev_score,
                    "current_score": cur_score,
                    "threshold": _DEFAULT_SCORE_THRESHOLD,
                    "source": "compliance",
                })

    except Exception as exc:
        from loguru import logger

        logger.warning("Failed to dispatch compliance webhooks: {}", exc)


async def update_schedule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    actor: str,
    run_after_sync: bool | None = None,
    cron_expression: str | None = None,
    enabled: bool | None = None,
) -> ComplianceSchedule:
    """Update the compliance check schedule.

    Args:
        db: Motor database handle.
        actor: Username performing the action.
        run_after_sync: Whether to run after each sync.
        cron_expression: Cron schedule expression.
        enabled: Whether the schedule is active.

    Returns:
        The updated schedule configuration.
    """
    from domains.compliance.repository import get_schedule

    current = await get_schedule(db)

    now = utc_now()
    updated = ComplianceSchedule(
        run_after_sync=(
            run_after_sync if run_after_sync is not None else current.run_after_sync
        ),
        cron_expression=(
            cron_expression if cron_expression is not None else current.cron_expression
        ),
        enabled=enabled if enabled is not None else current.enabled,
        updated_at=now,
        updated_by=actor,
    )

    await upsert_schedule(db, updated)
    await audit(
        db,
        domain="compliance",
        action="compliance.schedule.updated",
        actor=actor,
        summary="Updated compliance check schedule",
        details={
            "run_after_sync": updated.run_after_sync,
            "cron_expression": updated.cron_expression,
            "enabled": updated.enabled,
        },
    )

    return updated
