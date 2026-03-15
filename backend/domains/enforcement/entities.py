"""Enforcement domain entities.

Pure domain objects modelling enforcement rules, check results, and
violations.  No infrastructure dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RuleType(StrEnum):
    """The enforcement mode of a rule."""

    required = "required"
    forbidden = "forbidden"
    allowlist = "allowlist"


class Severity(StrEnum):
    """Severity level of an enforcement rule."""

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class CheckStatus(StrEnum):
    """Outcome of evaluating a single rule."""

    passed = "pass"
    failed = "fail"


@dataclass(slots=True)
class EnforcementRule:
    """A policy rule linking a taxonomy category to an enforcement mode.

    Attributes:
        id: Auto-generated unique identifier.
        name: Human-readable rule name.
        description: Optional description for reports.
        taxonomy_category_id: Key of the taxonomy category to enforce.
        type: Enforcement mode (required/forbidden/allowlist).
        severity: How critical violations of this rule are.
        enabled: Whether the rule is active.
        scope_groups: S1 group names to scope (empty = all).
        scope_tags: Agent tags to scope (empty = all).
        labels: Optional framework labels for reporting (e.g. ``PCI-DSS 5.2.1``).
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
        created_by: Creator username.
        updated_by: Last modifier username.
    """

    id: str
    name: str
    taxonomy_category_id: str
    type: RuleType
    severity: Severity
    description: str | None = None
    enabled: bool = True
    scope_groups: list[str] = field(default_factory=list)
    scope_tags: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None


@dataclass(slots=True)
class EnforcementViolation:
    """A single non-compliant finding.

    Attributes:
        agent_id: SentinelOne agent ID.
        agent_hostname: Hostname for display.
        violation_detail: Human-readable violation description.
        app_name: The offending application (forbidden/allowlist) or
            the missing category (required).
        app_version: Application version if applicable.
    """

    agent_id: str
    agent_hostname: str
    violation_detail: str
    app_name: str | None = None
    app_version: str | None = None


@dataclass(slots=True)
class EnforcementResult:
    """Outcome of evaluating a single enforcement rule.

    Attributes:
        rule_id: The evaluated rule.
        rule_name: Human-readable rule name.
        rule_type: required/forbidden/allowlist.
        severity: Rule severity level.
        checked_at: When the check ran.
        status: pass or fail.
        total_agents: Endpoints in scope.
        compliant_agents: Endpoints that passed.
        non_compliant_agents: Endpoints that failed.
        violations: Per-endpoint findings.
    """

    rule_id: str
    rule_name: str
    rule_type: str
    severity: str
    checked_at: datetime
    status: CheckStatus
    total_agents: int
    compliant_agents: int
    non_compliant_agents: int
    violations: list[EnforcementViolation]
