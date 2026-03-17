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
            "Verifies that the most recent data sync completed within "
            "24 hours, ensuring the software inventory reflects the "
            "current state of all system components as required by "
            "PCI DSS Requirement 2.2.1."
        ),
        category="Req 2 — Secure Configurations",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation=(
            "Check the Sync view for errors or stalled sync runs. "
            "If data is stale, trigger a manual sync from the Sync page. "
            "Verify the SentinelOne API connection is functional."
        ),
    ),
    ControlDefinition(
        id="PCI-2.2.5",
        framework_id=FrameworkId.pci_dss,
        name="Only Authorised Software on CDE",
        description=(
            "Checks that 0% of applications on CDE-tagged endpoints are "
            "unclassified, meaning every single application must be "
            "classified as Approved, Flagged, or Prohibited. Any "
            "unclassified application in the CDE is a compliance gap."
        ),
        category="Req 2 — Secure Configurations",
        severity=ControlSeverity.critical,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 0},
        scope_tags=["PCI-CDE"],
        remediation=(
            "Classify every application on PCI-CDE tagged endpoints. "
            "Use the Classification view filtered to PCI-CDE groups. "
            "Any unclassified application in the CDE is a compliance gap."
        ),
    ),
    ControlDefinition(
        id="PCI-2.2.5-P",
        framework_id=FrameworkId.pci_dss,
        name="No Prohibited Software in CDE",
        description=(
            "Scans all CDE-tagged endpoints for applications classified "
            "as Prohibited in the taxonomy. Any prohibited software in "
            "the Cardholder Data Environment is a critical PCI DSS "
            "violation."
        ),
        category="Req 2 — Secure Configurations",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        scope_tags=["PCI-CDE"],
        remediation=(
            "Remove prohibited software from CDE endpoints immediately. "
            "Review flagged endpoints in the Anomalies view filtered to "
            "PCI-CDE groups. Investigate how unauthorized software was "
            "installed."
        ),
    ),
    # ── Requirement 5: Malware Protection ──────────────────────────────
    ControlDefinition(
        id="PCI-5.2.1",
        framework_id=FrameworkId.pci_dss,
        name="Anti-Malware on All Systems",
        description=(
            "Verifies that all managed endpoints have checked in within "
            "the last 24 hours, confirming the SentinelOne agent is "
            "active and providing anti-malware protection as required "
            "by PCI DSS Requirement 5.2.1."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        remediation=(
            "Investigate offline endpoints in the Agent Detail view. "
            "Verify the SentinelOne agent service is running and "
            "restore connectivity. Offline endpoints lack anti-malware "
            "protection."
        ),
    ),
    ControlDefinition(
        id="PCI-5.2.2",
        framework_id=FrameworkId.pci_dss,
        name="Anti-Malware Definitions Current",
        description=(
            "Checks that the SentinelOne agent version on each endpoint "
            "is at or above the fleet baseline. Outdated agent versions "
            "may lack current threat detection capabilities required by "
            "PCI DSS Requirement 5.2.2."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation=(
            "Update the SentinelOne agent to the fleet baseline version "
            "on all non-compliant endpoints. Use the Agent Detail view "
            "to identify outdated agents and the SentinelOne console to "
            "schedule upgrades."
        ),
    ),
    ControlDefinition(
        id="PCI-5.2.3",
        framework_id=FrameworkId.pci_dss,
        name="Regular Security Scans",
        description=(
            "Verifies that data syncs have completed within a 12-hour "
            "window, ensuring the software inventory is fresh enough "
            "for timely malware and threat detection as required by "
            "PCI DSS Requirement 5.2.3."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.medium,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 12},
        remediation=(
            "Check the Sync view to verify sync schedules are active "
            "and completing on time. If syncs are failing, check the "
            "SentinelOne API connection and trigger a manual sync."
        ),
    ),
    ControlDefinition(
        id="PCI-5.3.1",
        framework_id=FrameworkId.pci_dss,
        name="Anti-Malware Active on CDE Systems",
        description=(
            "Verifies that all CDE-tagged endpoints have checked in "
            "within the last 24 hours, confirming active anti-malware "
            "protection specifically on systems that process or store "
            "cardholder data."
        ),
        category="Req 5 — Malware Protection",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        scope_tags=["PCI-CDE"],
        remediation=(
            "Investigate offline CDE endpoints immediately in the "
            "Agent Detail view filtered to PCI-CDE groups. Restore "
            "SentinelOne agent connectivity. CDE systems without active "
            "anti-malware are a critical PCI violation."
        ),
    ),
    # ── Requirement 6: Secure Software ─────────────────────────────────
    ControlDefinition(
        id="PCI-6.3.1",
        framework_id=FrameworkId.pci_dss,
        name="Known Vulnerability Identification",
        description=(
            "Checks that at least 95% of installed applications are "
            "classified and matched against the NIST CPE library. "
            "Unmatched applications cannot be evaluated for known "
            "vulnerabilities (CVEs)."
        ),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        remediation=(
            "Run the classification engine from the Classification view "
            "to process unmatched applications. Review results in the "
            "Library Browser to verify CPE matches. Create fingerprints "
            "for applications that cannot be auto-matched."
        ),
    ),
    ControlDefinition(
        id="PCI-6.3.3",
        framework_id=FrameworkId.pci_dss,
        name="Security Patches Timely",
        description=(
            "Checks that no more than 10% of installed applications are "
            "running outdated versions compared to the library baseline. "
            "Outdated software may contain known vulnerabilities that "
            "violate PCI DSS patch management requirements."
        ),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        remediation=(
            "Review outdated applications in the Library Browser view. "
            "Prioritize patching applications with known CVEs. Deploy "
            "updates through your software distribution tooling."
        ),
    ),
    ControlDefinition(
        id="PCI-6.3.3-CDE",
        framework_id=FrameworkId.pci_dss,
        name="CDE Patch Currency",
        description=(
            "Enforces a 0% tolerance for outdated application versions "
            "on CDE-tagged endpoints. Every application in the Cardholder "
            "Data Environment must be running the current baseline version "
            "with no exceptions."
        ),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.critical,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 0},
        scope_tags=["PCI-CDE"],
        remediation=(
            "Patch all outdated software on CDE endpoints immediately. "
            "Review the Library Browser filtered to PCI-CDE groups to "
            "identify version gaps. Any outdated application in the CDE "
            "is a critical compliance violation."
        ),
    ),
    ControlDefinition(
        id="PCI-6.3.3-EOL",
        framework_id=FrameworkId.pci_dss,
        name="End-of-Life Software Patching",
        description=(
            "End-of-Life software cannot be patched and violates PCI DSS "
            "patch management requirements. This control detects "
            "applications past their End-of-Life date using "
            "endoflife.date lifecycle data."
        ),
        category="Req 6 — Secure Software",
        severity=ControlSeverity.critical,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        remediation=(
            "Replace End-of-Life software immediately. Review flagged "
            "applications in the App Overview filtered by EOL status. "
            "EOL software cannot receive security patches and violates "
            "PCI DSS Requirement 6.3.3. Prioritize CDE endpoints."
        ),
    ),
    # ── Requirement 11: Regular Testing ────────────────────────────────
    ControlDefinition(
        id="PCI-11.5.1",
        framework_id=FrameworkId.pci_dss,
        name="Change Detection on CDE",
        description=(
            "Detects new, changed, or removed software on CDE-tagged "
            "endpoints within a 24-hour lookback window using Sentora's "
            "delta detection engine. Any unauthorized change in the CDE "
            "may compromise cardholder data security."
        ),
        category="Req 11 — Regular Testing",
        severity=ControlSeverity.critical,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        scope_tags=["PCI-CDE"],
        remediation=(
            "Review all software changes on CDE systems in the Anomalies "
            "view filtered to PCI-CDE groups. Verify each change was "
            "authorized through the change management process. Escalate "
            "unauthorized changes immediately."
        ),
    ),
    ControlDefinition(
        id="PCI-11.5.1-ALL",
        framework_id=FrameworkId.pci_dss,
        name="Fleet-Wide Change Detection",
        description=(
            "Detects new, changed, or removed software across all managed "
            "endpoints within a 48-hour lookback window. Fleet-wide "
            "change detection catches unauthorized installations that "
            "may eventually reach the CDE."
        ),
        category="Req 11 — Regular Testing",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 48},
        remediation=(
            "Review fleet-wide software changes in the Anomalies view. "
            "Verify that all detected changes were authorized. "
            "Investigate unexpected installations or removals."
        ),
    ),
    # ── Requirement 12: Information Security Policy ────────────────────
    ControlDefinition(
        id="PCI-12.5.1",
        framework_id=FrameworkId.pci_dss,
        name="Complete System Component Inventory",
        description=(
            "Checks that at least 90% of applications across all managed "
            "endpoints have been classified. A complete, classified "
            "software inventory is the foundation for PCI DSS security "
            "policy enforcement."
        ),
        category="Req 12 — Security Policy",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation=(
            "Run the classification engine from the Classification view "
            "to process unclassified applications. Review results in "
            "the App Overview and assign categories using the Taxonomy "
            "Editor."
        ),
    ),
    ControlDefinition(
        id="PCI-12.5.1-UNCL",
        framework_id=FrameworkId.pci_dss,
        name="Unclassified Software Below Threshold",
        description=(
            "Flags endpoints where more than 5% of installed applications "
            "are unclassified. Unclassified software represents unknown "
            "risk that cannot be assessed against the organization's "
            "security policy."
        ),
        category="Req 12 — Security Policy",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        remediation=(
            "Review unclassified applications on flagged endpoints in "
            "the App Overview. Use the Taxonomy Editor to classify "
            "unknown software or create fingerprints for recurring "
            "applications."
        ),
    ),
    ControlDefinition(
        id="PCI-12.5.2",
        framework_id=FrameworkId.pci_dss,
        name="Required Security Software",
        description=(
            "Verifies that configured mandatory security tools are "
            "installed on all PCI-CDE tagged endpoints. Requires "
            "tenant-specific configuration of which security applications "
            "are mandatory for PCI compliance."
        ),
        category="Req 12 — Security Policy",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        scope_tags=["PCI-CDE"],
        remediation=(
            "Configure the required applications for this control in "
            "Compliance > Settings > PCI DSS > PCI-12.5.2. Specify the "
            "security software names that must be present on all CDE "
            "endpoints (e.g. 'BitLocker', 'CrowdStrike'). Then deploy "
            "missing software."
        ),
    ),
]
