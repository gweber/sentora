"""Platform compliance domain entities.

Lightweight entities for Sentora's own security posture evaluation.
Separate from the endpoint compliance entities to maintain clear
domain boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ControlStatus(StrEnum):
    """Health status of a platform compliance control."""

    passing = "passing"
    warning = "warning"
    failing = "failing"
    not_applicable = "not_applicable"


class Framework(StrEnum):
    """Supported platform compliance frameworks."""

    soc2 = "soc2"
    iso27001 = "iso27001"


@dataclass(slots=True)
class ControlResult:
    """Runtime evaluation of a single platform control.

    Attributes:
        control_id: Unique control identifier (e.g. ``soc2-cc6.1``).
        framework: Parent framework key.
        reference: Framework reference number (e.g. ``CC6.1``).
        title: Short human-readable control title.
        category: Grouping category within the framework.
        status: Evaluation outcome.
        evidence_summary: Human-readable evidence description.
        evidence_count: Numeric evidence count (e.g. user count).
        last_checked: ISO-8601 timestamp of evaluation.
    """

    control_id: str
    framework: str
    reference: str
    title: str
    category: str
    status: ControlStatus
    evidence_summary: str
    evidence_count: int = 0
    last_checked: str = ""


@dataclass(slots=True)
class ComplianceReport:
    """A generated platform compliance report snapshot.

    Attributes:
        id: Report identifier (ObjectId string).
        framework: Which framework was evaluated.
        generated_at: ISO-8601 timestamp.
        generated_by: Username who triggered the report.
        period_start: Evidence period start (ISO-8601).
        period_end: Evidence period end (ISO-8601).
        status: Report status (generating/completed/failed).
        total_controls: Total controls evaluated.
        passing_controls: Controls that passed.
        warning_controls: Controls in warning state.
        failing_controls: Controls that failed.
        controls: Full control result details.
    """

    id: str
    framework: str
    generated_at: str
    generated_by: str
    period_start: str
    period_end: str
    status: str
    total_controls: int = 0
    passing_controls: int = 0
    warning_controls: int = 0
    failing_controls: int = 0
    controls: list[dict] = field(default_factory=list)
