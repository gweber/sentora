"""ISO/IEC 27001:2022 — Information Security Management System controls.

ISO 27001:2022 is the internationally recognized standard for information
security management systems (ISMS).  Annex A defines 93 controls across
four themes: Organizational (A.5), People (A.6), Physical (A.7), and
Technological (A.8).

Sentora evaluates the subset of Annex A controls that can be meaningfully
validated through endpoint software inventory data sourced from SentinelOne.
This covers primarily the Technological Controls (A.8) and selected
Organizational Controls (A.5) where software inventory provides direct
evidence.  Controls requiring procedural, physical, or human-resource
evidence (A.6, A.7, and most of A.5) are outside Sentora's scope.

Organizations pursuing ISO 27001 certification define their own Statement
of Applicability (SoA).  Controls that are not applicable to a tenant can
be disabled with a justification via the ``disable_reason`` field — this
justification is preserved in the audit log for auditor review.

This module does not constitute certification advice.
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
    id=FrameworkId.iso27001,
    name="ISO/IEC 27001:2022",
    version="2022",
    description=(
        "ISO/IEC 27001:2022 is the international standard for information "
        "security management systems (ISMS). Sentora evaluates the endpoint "
        "software management aspects of Annex A — specifically asset "
        "management (A.5.9-A.5.14), malware protection (A.8.7), "
        "vulnerability management (A.8.8), configuration management "
        "(A.8.9), software installation control (A.8.19), and change "
        "management (A.8.32). These 16 controls provide automated, "
        "continuous evidence for the technical controls most commonly "
        "assessed during certification audits."
    ),
    disclaimer=(
        "Sentora evaluates ISO 27001 compliance exclusively from the "
        "perspective of endpoint software inventory, classification, and "
        "enforcement. ISO 27001 certification requires a complete ISMS "
        "encompassing risk assessment, policies, procedures, people "
        "controls, physical security, supplier management, and management "
        "review — all of which are outside Sentora's scope. Sentora's "
        "controls provide supporting evidence for a subset of Annex A "
        "requirements; they do not replace a formal certification audit. "
        "Organizations should consult accredited certification bodies for "
        "full ISO 27001 compliance assessment."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── A.5 Organizational Controls ──────────────────────────────────────
    ControlDefinition(
        id="ISO-A.5.9",
        framework_id=FrameworkId.iso27001,
        name="Inventory of Information and Associated Assets",
        description=(
            "A.5.9 requires that an inventory of information and other "
            "associated assets is identified, maintained, and kept current. "
            "This control verifies that the software classification engine "
            "has processed a sufficient percentage of managed endpoints, "
            "ensuring the software asset inventory is comprehensive."
        ),
        category="A.5 Organizational Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation=(
            "Run the classification engine on all unprocessed agents. "
            "Navigate to the Apps Overview and filter by 'unclassified' "
            "to identify endpoints missing classification results. "
            "Create fingerprints or taxonomy entries for recurring "
            "unclassified applications."
        ),
    ),
    ControlDefinition(
        id="ISO-A.5.9-SYNC",
        framework_id=FrameworkId.iso27001,
        name="Asset Inventory Currency",
        description=(
            "A.5.9 requires that asset inventories are kept current. "
            "This control checks that the most recent data sync completed "
            "within the configured time window, ensuring the software "
            "inventory reflects the actual state of managed endpoints."
        ),
        category="A.5 Organizational Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation=(
            "Ensure sync schedules are active and completing successfully. "
            "Check the Sync view for errors or stalled sync runs. "
            "Verify the SentinelOne API connection is functional."
        ),
    ),
    ControlDefinition(
        id="ISO-A.5.10",
        framework_id=FrameworkId.iso27001,
        name="Acceptable Use of Information and Assets",
        description=(
            "A.5.10 requires rules for acceptable use of information and "
            "assets. This control detects applications classified as "
            "Prohibited across the entire managed fleet, enforcing the "
            "organization's acceptable use policy for software."
        ),
        category="A.5 Organizational Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited applications from affected endpoints. "
            "Review the taxonomy to ensure prohibited classifications "
            "align with the organization's acceptable use policy. "
            "Investigate how unauthorized software was installed."
        ),
    ),
    ControlDefinition(
        id="ISO-A.5.14",
        framework_id=FrameworkId.iso27001,
        name="Information Transfer — Data Sync Continuity",
        description=(
            "A.5.14 requires rules and procedures for information transfer. "
            "This control verifies that the data collection pipeline "
            "(SentinelOne sync) completes within an extended window, "
            "ensuring continuous information flow between the endpoint "
            "fleet and the compliance monitoring platform."
        ),
        category="A.5 Organizational Controls",
        severity=ControlSeverity.medium,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 48},
        remediation=(
            "Check the Sync view for errors or stalled sync runs. "
            "Ensure sync schedules are configured and the SentinelOne "
            "API connection is healthy. If syncs are failing, consult "
            "the troubleshooting guide."
        ),
    ),
    # ── A.8 Technological Controls ───────────────────────────────────────
    ControlDefinition(
        id="ISO-A.8.1",
        framework_id=FrameworkId.iso27001,
        name="User Endpoint Devices — Protection Active",
        description=(
            "A.8.1 requires that information stored on, processed by, or "
            "accessible via user endpoint devices is protected. This "
            "control checks that all managed endpoints have checked in "
            "within a 7-day window, detecting devices that may have lost "
            "their security monitoring coverage."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 7},
        remediation=(
            "Investigate endpoints offline for more than 7 days. "
            "Verify whether the endpoint is decommissioned, has "
            "connectivity issues, or requires agent reinstallation. "
            "Update the agent inventory to reflect the current state."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.1-VER",
        framework_id=FrameworkId.iso27001,
        name="User Endpoint Devices — Agent Currency",
        description=(
            "A.8.1 requires endpoint device protection. This control "
            "verifies that the SentinelOne agent version is current "
            "across all managed endpoints, ensuring the endpoint "
            "protection platform itself is not running outdated or "
            "vulnerable versions."
        ),
        category="A.8 Technological Controls",
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
        id="ISO-A.8.7",
        framework_id=FrameworkId.iso27001,
        name="Protection Against Malware — Agent Active",
        description=(
            "A.8.7 requires protection against malware. This control "
            "verifies that all managed endpoints have their security "
            "agent online and reporting within a strict 1-day window, "
            "ensuring malware protection is continuously active."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        remediation=(
            "Investigate endpoints offline for more than 24 hours "
            "immediately. These endpoints lack active malware protection. "
            "Check network connectivity, verify the SentinelOne agent "
            "service is running, and restore communication with the "
            "management console."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.8",
        framework_id=FrameworkId.iso27001,
        name="Management of Technical Vulnerabilities — EOL Software",
        description=(
            "A.8.8 requires timely identification and remediation of "
            "technical vulnerabilities. This control detects End-of-Life "
            "software that no longer receives security patches, "
            "representing unmitigatable vulnerability exposure."
        ),
        category="A.8 Technological Controls",
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
    ControlDefinition(
        id="ISO-A.8.8-VER",
        framework_id=FrameworkId.iso27001,
        name="Management of Technical Vulnerabilities — Patch Currency",
        description=(
            "A.8.8 requires that technical vulnerabilities are remediated "
            "in a timely manner. This control checks that installed "
            "application versions are current against the library "
            "baseline, detecting endpoints running outdated software "
            "that may contain known vulnerabilities."
        ),
        category="A.8 Technological Controls",
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
        id="ISO-A.8.9",
        framework_id=FrameworkId.iso27001,
        name="Configuration Management — Change Detection",
        description=(
            "A.8.9 requires that configurations are established, "
            "documented, and monitored. This control detects new or "
            "removed software between sync windows, flagging "
            "unauthorized configuration changes on managed endpoints."
        ),
        category="A.8 Technological Controls",
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
        id="ISO-A.8.9-UNCL",
        framework_id=FrameworkId.iso27001,
        name="Configuration Management — Known Software State",
        description=(
            "A.8.9 requires documented configurations. This control "
            "checks that the proportion of unclassified applications "
            "per endpoint remains below the threshold, ensuring the "
            "software configuration state is known and documented."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        remediation=(
            "Classify unknown applications on flagged endpoints. "
            "Use the taxonomy editor to categorize unidentified "
            "software. Create fingerprints for legitimate applications "
            "to prevent future false positives."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.19",
        framework_id=FrameworkId.iso27001,
        name="Installation of Software — Authorized Only",
        description=(
            "A.8.19 requires procedures to control software installation "
            "on operational systems. This control enforces that only "
            "authorized software is present by detecting applications "
            "classified as Prohibited on production endpoints."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        scope_groups=["Production"],
        remediation=(
            "Remove all prohibited applications from production "
            "endpoints immediately. Review the taxonomy to ensure "
            "prohibited classifications are current. Investigate how "
            "unauthorized software was installed on production systems."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.19-REQ",
        framework_id=FrameworkId.iso27001,
        name="Installation of Software — Required Security Tools",
        description=(
            "A.8.19 requires controlled software installation. This "
            "control verifies that configured required security "
            "applications are installed on all managed endpoints. "
            "Requires tenant-specific configuration of which security "
            "tools must be present."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required security applications for this "
            "control in Compliance > Settings > ISO 27001 > "
            "ISO-A.8.19-REQ. Specify the application names that must "
            "be present (e.g. EDR agent, encryption software, DLP "
            "agent). Then deploy to all endpoints missing them."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.16",
        framework_id=FrameworkId.iso27001,
        name="Monitoring Activities — Endpoint Visibility",
        description=(
            "A.8.16 requires that networks, systems, and applications "
            "are monitored for anomalous behaviour. This control verifies "
            "that classification coverage meets the threshold, ensuring "
            "sufficient visibility into endpoint software for meaningful "
            "monitoring and anomaly detection."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 80},
        remediation=(
            "Run the classification engine on all unprocessed agents. "
            "Increase classification coverage to ensure monitoring "
            "activities have sufficient context about installed software."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.25",
        framework_id=FrameworkId.iso27001,
        name="Secure Development — Software Asset Classification",
        description=(
            "A.8.25 requires rules for secure development of software "
            "and systems. This control verifies that software assets "
            "are classified to a high standard, ensuring development "
            "and operational tools are identified and categorized for "
            "appropriate security controls. Note: this provides evidence "
            "of software asset visibility, not of development practices."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        remediation=(
            "Increase classification coverage by running the "
            "classification engine and creating fingerprints for "
            "unclassified development tools and applications."
        ),
    ),
    ControlDefinition(
        id="ISO-A.8.32",
        framework_id=FrameworkId.iso27001,
        name="Change Management — Software Change Tracking",
        description=(
            "A.8.32 requires that changes to information processing "
            "facilities and systems are subject to change management "
            "procedures. This control detects software changes over an "
            "extended 48-hour window, providing visibility into changes "
            "that should have been processed through formal change "
            "management. Note: endpoint data validates that changes "
            "occurred; approval workflows require separate tooling."
        ),
        category="A.8 Technological Controls",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 48},
        remediation=(
            "Review all detected software changes in the Anomalies "
            "view. Cross-reference changes against approved change "
            "requests. Escalate unauthorized changes per the "
            "organization's change management procedures."
        ),
    ),
]
