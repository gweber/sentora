"""Compliance domain entities.

Pure domain objects with no infrastructure dependencies.  These model
the compliance concepts (frameworks, controls, check results, violations)
independently of any persistence or transport layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class FrameworkId(StrEnum):
    """Supported compliance frameworks."""

    soc2 = "soc2"
    pci_dss = "pci_dss_4"
    hipaa = "hipaa"
    bsi = "bsi_grundschutz"


class ControlSeverity(StrEnum):
    """Severity level of a compliance control."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class CheckType(StrEnum):
    """Discriminator for the check implementation to invoke."""

    prohibited_app = "prohibited_app_check"
    required_app = "required_app_check"
    unclassified_threshold = "unclassified_threshold_check"
    agent_version = "agent_version_check"
    agent_online = "agent_online_check"
    app_version = "app_version_check"
    sync_freshness = "sync_freshness_check"
    classification_coverage = "classification_coverage_check"
    delta_detection = "delta_detection_check"
    custom_app_presence = "custom_app_presence_check"


class CheckStatus(StrEnum):
    """Outcome of a single control evaluation."""

    passed = "pass"
    failed = "fail"
    warning = "warning"
    error = "error"
    not_applicable = "not_applicable"


class HipaaType(StrEnum):
    """HIPAA safeguard classification."""

    required = "required"
    addressable = "addressable"


class BsiLevel(StrEnum):
    """BSI IT-Grundschutz requirement level."""

    basis = "basis"  # MUSS
    standard = "standard"  # SOLLTE
    elevated = "elevated"  # SOLLTE bei erhöhtem Schutzbedarf


# ---------------------------------------------------------------------------
# Domain entities
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComplianceFramework:
    """A compliance framework with its metadata.

    Attributes:
        id: Unique framework identifier (e.g. ``soc2``).
        name: Human-readable framework name (e.g. ``SOC 2 Type II``).
        version: Framework version string.
        description: Brief description of what the framework covers.
        disclaimer: Legal disclaimer shown in UI and reports.
    """

    id: FrameworkId
    name: str
    version: str
    description: str
    disclaimer: str


@dataclass(frozen=True, slots=True)
class ControlDefinition:
    """An immutable control definition shipped with a framework.

    This is the *template* for a control.  Tenant-specific overrides
    (enabled/disabled, custom thresholds, scope) are stored separately
    in ``ControlConfiguration``.

    Attributes:
        id: Unique control identifier (e.g. ``CC6.7`` or ``PCI-5.2.1``).
        framework_id: Parent framework.
        name: Short human-readable control name.
        description: Full description of what is checked.
        category: Grouping category within the framework.
        severity: Default severity level.
        check_type: Which check implementation evaluates this control.
        parameters: Default parameters passed to the check function.
        scope_tags: Default S1 tags to scope the check (empty = all).
        scope_groups: Default S1 group names to scope the check.
        hipaa_type: HIPAA-only: required vs addressable safeguard.
        bsi_level: BSI-only: basis/standard/elevated requirement level.
        remediation: Default remediation guidance.
    """

    id: str
    framework_id: FrameworkId
    name: str
    description: str
    category: str
    severity: ControlSeverity
    check_type: CheckType
    parameters: dict[str, Any] = field(default_factory=dict)
    scope_tags: list[str] = field(default_factory=list)
    scope_groups: list[str] = field(default_factory=list)
    hipaa_type: HipaaType | None = None
    bsi_level: BsiLevel | None = None
    remediation: str = ""


@dataclass(slots=True)
class ControlConfiguration:
    """Tenant-specific overrides for a control definition.

    Stored in MongoDB.  If a field is ``None`` the default from
    ``ControlDefinition`` applies.

    Attributes:
        control_id: References ``ControlDefinition.id``.
        framework_id: References ``ControlDefinition.framework_id``.
        enabled: Whether this control is active for the tenant.
        severity_override: Tenant-specific severity override.
        parameters_override: Merged over the definition's defaults.
        scope_tags_override: Replaces the default scope tags.
        scope_groups_override: Replaces the default scope groups.
        updated_at: Last modification timestamp.
        updated_by: Username of the last modifier.
    """

    control_id: str
    framework_id: str
    enabled: bool = True
    severity_override: ControlSeverity | None = None
    parameters_override: dict[str, Any] = field(default_factory=dict)
    scope_tags_override: list[str] | None = None
    scope_groups_override: list[str] | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


@dataclass(slots=True)
class ComplianceViolation:
    """A single non-compliant finding on an endpoint.

    Attributes:
        agent_id: SentinelOne agent ID.
        agent_hostname: Hostname for display.
        violation_detail: Human-readable description of the violation.
        app_name: Offending application name (if applicable).
        app_version: Offending application version (if applicable).
        remediation: Suggested remediation step.
    """

    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None
    remediation: str = ""


@dataclass(slots=True)
class CheckResult:
    """Outcome of evaluating a single control.

    Attributes:
        control_id: The evaluated control.
        framework_id: Parent framework.
        status: Pass/fail/warning/error/not_applicable.
        checked_at: When the check was executed.
        total_endpoints: Number of endpoints in scope.
        compliant_endpoints: Endpoints that passed.
        non_compliant_endpoints: Endpoints that failed.
        violations: Detailed per-endpoint findings.
        evidence_summary: Human-readable summary for audit evidence.
        severity: Effective severity (after any tenant override).
        category: Control category for grouping.
        control_name: Control display name.
    """

    control_id: str
    framework_id: str
    status: CheckStatus
    checked_at: datetime
    total_endpoints: int
    compliant_endpoints: int
    non_compliant_endpoints: int
    violations: list[ComplianceViolation]
    evidence_summary: str
    severity: ControlSeverity
    category: str
    control_name: str


@dataclass(frozen=True, slots=True)
class FrameworkScore:
    """Aggregated compliance posture for a single framework.

    Attributes:
        framework_id: The framework scored.
        total_controls: Number of evaluated controls.
        passed: Controls that passed.
        failed: Controls that failed.
        warning: Controls in warning state.
        error: Controls that errored during evaluation.
        not_applicable: Controls not applicable in scope.
        score_percent: Passing / applicable * 100.
    """

    framework_id: str
    total_controls: int
    passed: int
    failed: int
    warning: int
    error: int
    not_applicable: int
    score_percent: float


@dataclass(slots=True)
class ComplianceSchedule:
    """Compliance check schedule configuration.

    Attributes:
        run_after_sync: Trigger checks after every successful sync.
        cron_expression: Optional cron schedule (e.g. ``0 6 * * *``).
        enabled: Whether the schedule is active.
        updated_at: Last modification timestamp.
        updated_by: Username of the last modifier.
    """

    run_after_sync: bool = True
    cron_expression: str | None = None
    enabled: bool = True
    updated_at: datetime | None = None
    updated_by: str | None = None


@dataclass(frozen=True, slots=True)
class CustomControlDefinition:
    """A tenant-created custom control.

    Stored in MongoDB alongside the built-in definitions.  Uses the
    same check types but allows fully custom parameters.

    Attributes:
        id: Unique control identifier (tenant-chosen, prefixed ``custom-``).
        framework_id: Which framework this control belongs to.
        name: Human-readable control name.
        description: What this control checks.
        category: Grouping category.
        severity: Severity level.
        check_type: Which check implementation to invoke.
        parameters: Parameters for the check function.
        scope_tags: S1 tags to scope the check.
        scope_groups: S1 group names to scope the check.
        remediation: Remediation guidance.
        created_at: Creation timestamp.
        created_by: Creator username.
    """

    id: str
    framework_id: str
    name: str
    description: str
    category: str
    severity: ControlSeverity
    check_type: CheckType
    parameters: dict[str, Any] = field(default_factory=dict)
    scope_tags: list[str] = field(default_factory=list)
    scope_groups: list[str] = field(default_factory=list)
    remediation: str = ""
    created_at: datetime | None = None
    created_by: str | None = None
