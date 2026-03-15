"""HIPAA Security Rule (45 CFR Part 164) — control definitions.

HIPAA defines Administrative, Physical, and Technical Safeguards.
Sentora covers the Technical Safeguards related to endpoint software
management.  Each safeguard is marked as Required or Addressable per
the HIPAA specification.

HIPAA compliance is determined by the U.S. Department of Health and
Human Services.  Sentora provides technical safeguard monitoring, not
compliance determination.
"""

from __future__ import annotations

from domains.compliance.entities import (
    CheckType,
    ComplianceFramework,
    ControlDefinition,
    ControlSeverity,
    FrameworkId,
    HipaaType,
)

FRAMEWORK = ComplianceFramework(
    id=FrameworkId.hipaa,
    name="HIPAA Security Rule",
    version="45 CFR 164",
    description=(
        "Health Insurance Portability and Accountability Act — "
        "Security Rule for electronic Protected Health Information (ePHI)"
    ),
    disclaimer=(
        "HIPAA compliance is determined by the U.S. Department of Health "
        "and Human Services. Sentora provides technical safeguard "
        "monitoring for endpoint software management."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── §164.308 Administrative Safeguards ─────────────────────────────
    ControlDefinition(
        id="HIPAA-308a1",
        framework_id=FrameworkId.hipaa,
        name="Risk Analysis — Software Inventory",
        description=(
            "A complete software inventory on ePHI endpoints is required "
            "input for the HIPAA risk analysis process."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Complete software inventory and classification on ePHI systems.",
    ),
    ControlDefinition(
        id="HIPAA-308a1-SYNC",
        framework_id=FrameworkId.hipaa,
        name="Risk Analysis — Data Currency",
        description=(
            "Software inventory data must be current to support ongoing "
            "risk analysis."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        hipaa_type=HipaaType.required,
        remediation="Ensure regular data syncs are running.",
    ),
    ControlDefinition(
        id="HIPAA-308a5",
        framework_id=FrameworkId.hipaa,
        name="Security Awareness — Training Software",
        description=(
            "Verify that security awareness training software is installed "
            "on endpoints where configured as required."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.low,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation="Install the configured security awareness training agent.",
    ),
    ControlDefinition(
        id="HIPAA-308a6",
        framework_id=FrameworkId.hipaa,
        name="Security Incident — EDR Active",
        description=(
            "EDR protection must be active on ePHI endpoints to detect "
            "and respond to security incidents."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Restore SentinelOne agent connectivity on ePHI endpoints.",
    ),
    # ── §164.312 Technical Safeguards ──────────────────────────────────
    ControlDefinition(
        id="HIPAA-312a1",
        framework_id=FrameworkId.hipaa,
        name="Access Control — Authorised Software Only",
        description=(
            "Only authorised software may be installed on systems that "
            "process ePHI.  No prohibited or unclassified applications."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Remove prohibited software from ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-312a1-UNCL",
        framework_id=FrameworkId.hipaa,
        name="Access Control — Unclassified Threshold",
        description=(
            "The percentage of unclassified applications on ePHI endpoints "
            "must be below the configured threshold."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Classify all software on ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-312a2iv",
        framework_id=FrameworkId.hipaa,
        name="Encryption Software Installed",
        description=(
            "Full-disk encryption software (BitLocker, FileVault, "
            "VeraCrypt) must be installed on all ePHI endpoints."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.critical,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "BitLocker*", "must_exist": True},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation="Install full-disk encryption on ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-312b",
        framework_id=FrameworkId.hipaa,
        name="Audit Controls — Software Change Tracking",
        description=(
            "An audit trail of software inventory changes must be "
            "maintained for ePHI endpoints."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Ensure regular syncs are running to maintain change audit trail.",
    ),
    ControlDefinition(
        id="HIPAA-312c1",
        framework_id=FrameworkId.hipaa,
        name="Integrity Controls — Unauthorised Changes",
        description=(
            "Detect unauthorised software modifications on ePHI endpoints "
            "through delta detection."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 12},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation="Review and approve all software changes on ePHI systems.",
    ),
    ControlDefinition(
        id="HIPAA-312e1",
        framework_id=FrameworkId.hipaa,
        name="Transmission Security — VPN Software",
        description=(
            "VPN or secure communication software must be installed on "
            "remote endpoints that access ePHI."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.medium,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation="Install VPN client on remote ePHI endpoints.",
    ),
    # ── Additional endpoint-specific controls ──────────────────────────
    ControlDefinition(
        id="HIPAA-312d",
        framework_id=FrameworkId.hipaa,
        name="Person Authentication — EDR Version",
        description=(
            "SentinelOne agent must be at the current version on ePHI "
            "endpoints to ensure full identity-based threat detection."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Update SentinelOne agent on ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-AVAIL-1",
        framework_id=FrameworkId.hipaa,
        name="ePHI System Availability",
        description=(
            "Endpoints processing ePHI must be online and reporting. "
            "Stale agents indicate potential availability gaps."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 3},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Investigate offline ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-SW-CURR",
        framework_id=FrameworkId.hipaa,
        name="ePHI Software Currency",
        description=(
            "Software on ePHI endpoints must be reasonably current "
            "to mitigate known vulnerabilities."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.medium,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation="Update outdated software on ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-REQ-SW",
        framework_id=FrameworkId.hipaa,
        name="Required Security Software on ePHI",
        description=(
            "All ePHI endpoints must have mandatory security software "
            "installed (configured via required_apps list)."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Install required security software on ePHI endpoints.",
    ),
    ControlDefinition(
        id="HIPAA-CLASS-COV",
        framework_id=FrameworkId.hipaa,
        name="ePHI Classification Coverage",
        description=(
            "Classification coverage on ePHI endpoints must meet a "
            "higher threshold than the general fleet."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation="Achieve 95%+ classification coverage on ePHI endpoints.",
    ),
]
