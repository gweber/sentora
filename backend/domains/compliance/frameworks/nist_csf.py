"""NIST Cybersecurity Framework 2.0 control definitions.

The NIST Cybersecurity Framework (CSF) 2.0, published February 2024,
provides a taxonomy of high-level cybersecurity outcomes organized into
six Functions: Govern, Identify, Protect, Detect, Respond, and Recover.

Sentora evaluates the subset of CSF 2.0 subcategories that can be
meaningfully validated through endpoint software inventory data sourced
from SentinelOne.  This covers selected subcategories within Identify
(asset management), Protect (platform security, data security,
infrastructure resilience), and Detect (continuous monitoring).

Govern, Respond, and Recover functions require organizational
governance, incident management, and recovery processes that are
outside the scope of endpoint software monitoring.

This module does not constitute a NIST CSF assessment.
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
    id=FrameworkId.nist_csf,
    name="NIST CSF 2.0",
    version="2.0 (2024)",
    description=(
        "The NIST Cybersecurity Framework 2.0 is the de-facto cybersecurity "
        "standard in the United States, applicable to organizations of all "
        "sizes and sectors. Sentora evaluates the endpoint software management "
        "aspects of CSF 2.0 — specifically asset management (ID.AM), platform "
        "security (PR.PS), data security (PR.DS), infrastructure resilience "
        "(PR.IR), and continuous monitoring (DE.CM)."
    ),
    disclaimer=(
        "This framework provides automated endpoint evidence collection for "
        "selected NIST CSF 2.0 subcategories. It does not constitute a "
        "complete NIST CSF assessment. Full CSF implementation requires "
        "organizational governance, risk management, incident response "
        "capabilities, and recovery planning beyond endpoint monitoring."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── Identify (ID) ────────────────────────────────────────────────────
    ControlDefinition(
        id="NIST-ID.AM-01",
        framework_id=FrameworkId.nist_csf,
        name="Asset Inventory Completeness",
        description=(
            "ID.AM-01: Inventories of hardware managed by the organization "
            "are maintained. This control verifies that the software "
            "classification engine has processed all managed endpoints, "
            "ensuring the endpoint asset inventory is comprehensive."
        ),
        category="Identify (ID)",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation=(
            "Run the classification engine on all unprocessed agents. "
            "Navigate to Apps Overview and filter by 'unclassified' to "
            "identify endpoints missing classification results."
        ),
    ),
    ControlDefinition(
        id="NIST-ID.AM-01-SYNC",
        framework_id=FrameworkId.nist_csf,
        name="Asset Inventory Currency",
        description=(
            "ID.AM-01: Asset inventories must be maintained and kept "
            "current. This control checks that the most recent data sync "
            "completed within the configured time window, ensuring the "
            "asset inventory reflects the actual state of endpoints."
        ),
        category="Identify (ID)",
        severity=ControlSeverity.medium,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation=(
            "Ensure sync schedules are active and completing successfully. "
            "Check the Sync view for errors or stalled sync runs. "
            "Verify the SentinelOne API connection is functional."
        ),
    ),
    ControlDefinition(
        id="NIST-ID.AM-02",
        framework_id=FrameworkId.nist_csf,
        name="Software Inventory Classification",
        description=(
            "ID.AM-02: Inventories of software, services, and systems "
            "managed by the organization are maintained. This control "
            "verifies that the proportion of unclassified software per "
            "endpoint remains below the threshold, ensuring software "
            "assets are properly categorized."
        ),
        category="Identify (ID)",
        severity=ControlSeverity.high,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        remediation=(
            "Classify unknown applications on flagged endpoints. Use "
            "the taxonomy editor to categorize unidentified software. "
            "Create fingerprints for recurring unclassified applications."
        ),
    ),
    ControlDefinition(
        id="NIST-ID.AM-02-EOL",
        framework_id=FrameworkId.nist_csf,
        name="Software Lifecycle Tracking",
        description=(
            "ID.AM-02: Software inventories should include lifecycle "
            "status. This control detects End-of-Life software that no "
            "longer receives security patches, ensuring the asset "
            "inventory includes lifecycle risk information."
        ),
        category="Identify (ID)",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        remediation=(
            "Upgrade or replace End-of-Life software with supported "
            "alternatives. For legacy systems that cannot be updated, "
            "document compensating controls. See Library Sources > "
            "endoflife.date for supported version information."
        ),
    ),
    # ── Protect (PR) ─────────────────────────────────────────────────────
    ControlDefinition(
        id="NIST-PR.DS-01",
        framework_id=FrameworkId.nist_csf,
        name="Data-at-Rest Protection — Encryption Software",
        description=(
            "PR.DS-01: The confidentiality, integrity, and availability "
            "of data-at-rest are protected. This control checks whether "
            "configured encryption software is present on managed "
            "endpoints. Requires tenant-specific configuration of which "
            "encryption tool to check."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.high,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        remediation=(
            "Configure the encryption software pattern for this control "
            "in Compliance > Settings > NIST CSF 2.0 > NIST-PR.DS-01. "
            "Specify the encryption product name pattern (e.g. "
            "'BitLocker*', 'FileVault*'). Then deploy encryption to "
            "all endpoints missing it."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.IR-01",
        framework_id=FrameworkId.nist_csf,
        name="Infrastructure Resilience — Endpoints Protected",
        description=(
            "PR.IR-01: Networks and environments are protected from "
            "unauthorized logical access and usage. This control "
            "verifies that all managed endpoints have their security "
            "agent online and reporting, ensuring endpoint protection "
            "coverage is not interrupted."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 3},
        remediation=(
            "Investigate offline endpoints immediately. Check network "
            "connectivity, verify the SentinelOne agent service is "
            "running, and restore communication with the management "
            "console. Offline endpoints cannot be monitored or protected."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.IR-01-VER",
        framework_id=FrameworkId.nist_csf,
        name="Infrastructure Resilience — Agent Currency",
        description=(
            "PR.IR-01: Infrastructure protection requires current "
            "security tooling. This control verifies that the "
            "SentinelOne agent version is current across all managed "
            "endpoints, ensuring the endpoint protection platform is "
            "not running outdated or vulnerable versions."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation=(
            "Update the SentinelOne agent to the current fleet baseline "
            "version on all non-compliant endpoints. Use the SentinelOne "
            "console to schedule agent upgrades."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.PS-01",
        framework_id=FrameworkId.nist_csf,
        name="Platform Security — Configuration Management",
        description=(
            "PR.PS-01: The configuration of organizational systems is "
            "managed. This control detects software changes between "
            "sync windows, flagging unauthorized configuration changes "
            "on managed endpoints."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review detected software changes in the Anomalies view. "
            "Verify that all changes were authorized through the "
            "organization's change management process. Investigate "
            "unexpected installations or removals."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.PS-02",
        framework_id=FrameworkId.nist_csf,
        name="Platform Security — Software Maintenance",
        description=(
            "PR.PS-02: Software is maintained, replaced, and removed "
            "in alignment with risk. This control checks that installed "
            "application versions are current against the library "
            "baseline, detecting outdated software that may contain "
            "known vulnerabilities."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.medium,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 15},
        remediation=(
            "Update outdated applications to their current versions. "
            "Prioritize updates for applications with known "
            "vulnerabilities. Use the Library view to compare installed "
            "versions against the baseline."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.PS-02-EOL",
        framework_id=FrameworkId.nist_csf,
        name="Platform Security — EOL Software Removal",
        description=(
            "PR.PS-02: Software must be replaced or removed when no "
            "longer supported. This control detects End-of-Life "
            "software that should be removed or replaced to reduce "
            "the attack surface."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        remediation=(
            "Remove or replace all End-of-Life software on affected "
            "endpoints. Prioritize software with critical or high "
            "severity vulnerabilities. Document compensating controls "
            "for legacy systems that cannot be updated."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.PS-05",
        framework_id=FrameworkId.nist_csf,
        name="Platform Security — Authorized Software Only",
        description=(
            "PR.PS-05: Installation and execution of unauthorized "
            "software is prevented or restricted. This control detects "
            "applications classified as Prohibited on managed endpoints, "
            "enforcing the organization's software authorization policy."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited applications from affected endpoints "
            "immediately. Review the taxonomy to ensure prohibited "
            "classifications are current. Investigate how unauthorized "
            "software was installed."
        ),
    ),
    ControlDefinition(
        id="NIST-PR.PS-05-REQ",
        framework_id=FrameworkId.nist_csf,
        name="Platform Security — Required Security Software",
        description=(
            "PR.PS-05: Authorized software must be present on managed "
            "systems. This control verifies that configured required "
            "security applications are installed. Requires tenant-"
            "specific configuration of which security tools must be "
            "present."
        ),
        category="Protect (PR)",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required security applications for this "
            "control in Compliance > Settings > NIST CSF 2.0 > "
            "NIST-PR.PS-05-REQ. Specify the application names that "
            "must be present (e.g. EDR agent, DLP tool). Then deploy "
            "to all endpoints missing them."
        ),
    ),
    # ── Detect (DE) ──────────────────────────────────────────────────────
    ControlDefinition(
        id="NIST-DE.CM-01",
        framework_id=FrameworkId.nist_csf,
        name="Continuous Monitoring — Endpoint Coverage",
        description=(
            "DE.CM-01: Networks and network services are monitored to "
            "find potentially adverse events. This control verifies "
            "that all managed endpoints have active security monitoring "
            "by checking agent online status within a strict window."
        ),
        category="Detect (DE)",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        remediation=(
            "Investigate endpoints offline for more than 24 hours "
            "immediately. These endpoints lack active monitoring. "
            "Check network connectivity, verify the SentinelOne agent "
            "service is running, and restore communication."
        ),
    ),
    ControlDefinition(
        id="NIST-DE.CM-06",
        framework_id=FrameworkId.nist_csf,
        name="Continuous Monitoring — Security Agent Currency",
        description=(
            "DE.CM-06: External service provider activities and "
            "services are monitored. This control verifies that the "
            "SentinelOne security agent version is current, ensuring "
            "endpoint monitoring capabilities include the latest "
            "detection signatures and behavioral analysis."
        ),
        category="Detect (DE)",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation=(
            "Update the SentinelOne agent on all non-compliant "
            "endpoints. Use the SentinelOne console to schedule "
            "agent upgrades to the latest version."
        ),
    ),
    ControlDefinition(
        id="NIST-DE.CM-09",
        framework_id=FrameworkId.nist_csf,
        name="Continuous Monitoring — Vulnerability Awareness",
        description=(
            "DE.CM-09: Computing hardware and software, runtime "
            "environments, and their data are monitored to find "
            "potentially adverse events. This control detects "
            "End-of-Life software with known vulnerability exposure "
            "across the managed fleet."
        ),
        category="Detect (DE)",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        remediation=(
            "Review all End-of-Life software flagged by this control. "
            "Prioritize remediation based on vulnerability severity. "
            "See Library Sources > endoflife.date for lifecycle details."
        ),
    ),
]
