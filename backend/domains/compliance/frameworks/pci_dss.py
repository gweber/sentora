"""PCI DSS 4.0.1 — control definitions.

PCI DSS has 12 requirement domains with 500+ controls.  Sentora covers
the subset related to endpoint software management, particularly in the
Cardholder Data Environment (CDE).

PCI DSS compliance requires validation by a Qualified Security Assessor
(QSA).  Sentora provides evidence and monitoring, not certification.
"""

from __future__ import annotations

from domains.compliance.entities import (
    CheckType,
    ComplianceFramework,
    ControlDefinition,
    ControlSeverity,
    FrameworkId,
)

FRAMEWORK = ComplianceFramework(
    id=FrameworkId.pci_dss,
    name="PCI DSS 4.0.1",
    version="4.0.1",
    description=(
        "Payment Card Industry Data Security Standard — requirements for protecting cardholder data"
    ),
    disclaimer=(
        "PCI DSS compliance requires validation by a Qualified Security "
        "Assessor (QSA). Sentora provides evidence and monitoring for "
        "endpoint-related requirements, not certification."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── Requirement 2: Secure System Configurations ─────────────────────
    ControlDefinition(
        id="PCI-2.2.1",
        framework_id=FrameworkId.pci_dss,
        name="System Inventory Current",
        description=(
            "Maintain a current, accurate inventory of all system "
            "components including software.  Last sync must be recent."
        ),
        category="Req 2 — Secure Configurations",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation="Run a data sync to refresh the software inventory.",
    ),
    ControlDefinition(
        id="PCI-2.2.5",
        framework_id=FrameworkId.pci_dss,
        name="Only Authorised Software on CDE",
        description=(
            "Endpoints in the Cardholder Data Environment must only have "
            "authorised (Approved) applications installed."
        ),
        category="Req 2 — Secure Configurations",
        severity=ControlSeverity.critical,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 0},
        scope_tags=["PCI-CDE"],
        remediation="Remove unapproved software from CDE endpoints.",
    ),
    ControlDefinition(
        id="PCI-2.2.5-P",
        framework_id=FrameworkId.pci_dss,
        name="No Prohibited Software in CDE",
        description=("No prohibited applications may be present on CDE endpoints."),
        category="Req 2 — Secure Configurations",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        scope_tags=["PCI-CDE"],
        remediation="Immediately remove prohibited software from CDE systems.",
    ),
    # ── Requirement 5: Malware Protection ──────────────────────────────
    ControlDefinition(
        id="PCI-5.2.1",
        framework_id=FrameworkId.pci_dss,
        name="Anti-Malware on All Systems",
        description=(
            "SentinelOne agent must be active on all managed endpoints, particularly CDE systems."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        remediation="Ensure SentinelOne agent is active on all endpoints.",
    ),
    ControlDefinition(
        id="PCI-5.2.2",
        framework_id=FrameworkId.pci_dss,
        name="Anti-Malware Definitions Current",
        description=(
            "SentinelOne agent version must be at or above the fleet "
            "baseline to ensure current protection capabilities."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation="Update SentinelOne agent to current version.",
    ),
    ControlDefinition(
        id="PCI-5.2.3",
        framework_id=FrameworkId.pci_dss,
        name="Regular Security Scans",
        description=(
            "Data syncs must run on a regular schedule to ensure the "
            "software inventory reflects current state."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.medium,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 12},
        remediation="Configure and verify regular sync schedules.",
    ),
    ControlDefinition(
        id="PCI-5.3.1",
        framework_id=FrameworkId.pci_dss,
        name="Anti-Malware Active on CDE Systems",
        description=(
            "SentinelOne agent must be online and current specifically on CDE-tagged endpoints."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        scope_tags=["PCI-CDE"],
        remediation="Restore SentinelOne agent connectivity on CDE endpoints.",
    ),
    # ── Requirement 6: Secure Software ─────────────────────────────────
    ControlDefinition(
        id="PCI-6.3.1",
        framework_id=FrameworkId.pci_dss,
        name="Known Vulnerability Identification",
        description=(
            "Installed applications should be matched against known "
            "vulnerability databases via NIST CPE library matching."
        ),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        remediation="Ensure all apps have library matches for CVE coverage.",
    ),
    ControlDefinition(
        id="PCI-6.3.3",
        framework_id=FrameworkId.pci_dss,
        name="Security Patches Timely",
        description=(
            "Endpoints must not run outdated versions of known software.  "
            "Compares installed versions against fleet standards."
        ),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        remediation="Deploy security patches for outdated applications.",
    ),
    ControlDefinition(
        id="PCI-6.3.3-CDE",
        framework_id=FrameworkId.pci_dss,
        name="CDE Patch Currency",
        description=("CDE endpoints must have stricter patch currency requirements."),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.critical,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 0},
        scope_tags=["PCI-CDE"],
        remediation="Immediately patch all outdated software on CDE systems.",
    ),
    # ── Requirement 11: Regular Testing ────────────────────────────────
    ControlDefinition(
        id="PCI-11.5.1",
        framework_id=FrameworkId.pci_dss,
        name="Change Detection on CDE",
        description=(
            "A change-detection mechanism must identify new, changed, "
            "or removed software on CDE endpoints."
        ),
        category="Req 11 — Regular Testing",
        severity=ControlSeverity.critical,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        scope_tags=["PCI-CDE"],
        remediation="Review all software changes on CDE systems.",
    ),
    ControlDefinition(
        id="PCI-11.5.1-ALL",
        framework_id=FrameworkId.pci_dss,
        name="Fleet-Wide Change Detection",
        description=(
            "Change detection across all managed endpoints to identify "
            "unauthorised software installations."
        ),
        category="Req 11 — Regular Testing",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 48},
        remediation="Review fleet-wide software changes.",
    ),
    # ── Requirement 12: Information Security Policy ────────────────────
    ControlDefinition(
        id="PCI-12.5.1",
        framework_id=FrameworkId.pci_dss,
        name="Complete System Component Inventory",
        description=(
            "A complete, current software inventory with classification "
            "status for all managed endpoints."
        ),
        category="Req 12 — Security Policy",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation="Achieve >90% classification coverage.",
    ),
    ControlDefinition(
        id="PCI-12.5.1-UNCL",
        framework_id=FrameworkId.pci_dss,
        name="Unclassified Software Below Threshold",
        description=(
            "Unclassified applications must not exceed the configured threshold on any endpoint."
        ),
        category="Req 12 — Security Policy",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        remediation="Review and classify unknown applications.",
    ),
    ControlDefinition(
        id="PCI-12.5.2",
        framework_id=FrameworkId.pci_dss,
        name="Required Security Software",
        description=("All PCI-scoped endpoints must have mandatory security tools installed."),
        category="Req 12 — Security Policy",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        scope_tags=["PCI-CDE"],
        remediation="Install all required security software on PCI endpoints.",
    ),
]
