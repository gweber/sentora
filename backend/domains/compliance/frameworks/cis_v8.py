"""CIS Critical Security Controls v8 safeguard definitions.

The CIS Controls v8 (May 2021) define 18 prioritized security controls
with 153 safeguards, organized into three Implementation Groups:

- **IG1** (Basic): Essential cyber hygiene — the minimum standard.
- **IG2** (Foundational): Builds on IG1 for organizations managing
  enterprise IT infrastructure.
- **IG3** (Advanced): Comprehensive security for organizations
  handling sensitive data or facing sophisticated threats.

Sentora evaluates safeguards from CIS Controls 1 (Enterprise Asset
Inventory), 2 (Software Asset Inventory), 7 (Continuous Vulnerability
Management), and 10 (Malware Defenses).  These are the controls where
endpoint software inventory data provides direct, defensible evidence.

Controls 3-6, 8-9, and 11-18 cover access management, data protection,
email security, network monitoring, security awareness, and other areas
outside the scope of endpoint software inventory.

This module does not constitute a CIS Controls assessment.
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
    id=FrameworkId.cis_v8,
    name="CIS Controls v8",
    version="8.0 (2021)",
    description=(
        "The CIS Critical Security Controls v8 provide a prioritized set of "
        "actions to protect organizations from known cyber attack vectors. "
        "Sentora evaluates the endpoint software management safeguards — "
        "specifically Control 1 (Enterprise Asset Inventory), Control 2 "
        "(Software Asset Inventory), Control 7 (Continuous Vulnerability "
        "Management), and Control 10 (Malware Defenses). Implementation "
        "Group assignments (IG1/IG2/IG3) are noted per safeguard."
    ),
    disclaimer=(
        "This framework provides automated endpoint evidence collection for "
        "selected CIS Controls v8 Safeguards. Full CIS Controls "
        "implementation requires network-level controls, access management, "
        "data protection, security awareness training, and additional "
        "safeguards beyond endpoint software monitoring. Implementation "
        "Group assignments are advisory."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── Control 1: Inventory and Control of Enterprise Assets ────────────
    ControlDefinition(
        id="CIS-1.1",
        framework_id=FrameworkId.cis_v8,
        name="Establish and Maintain Enterprise Asset Inventory",
        description=(
            "CIS Safeguard 1.1 (IG1): Establish and maintain an accurate, "
            "detailed, and up-to-date inventory of all enterprise assets "
            "with the potential to store or process data. This control "
            "verifies that the classification engine has processed all "
            "managed endpoints, ensuring the asset inventory is complete."
        ),
        category="Control 1 — Inventory of Enterprise Assets",
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
        id="CIS-1.1-SYNC",
        framework_id=FrameworkId.cis_v8,
        name="Asset Inventory Currency",
        description=(
            "CIS Safeguard 1.1 (IG1): The asset inventory must be "
            "up-to-date. This control checks that the most recent data "
            "sync completed within the configured time window, ensuring "
            "the inventory reflects the current state of endpoints."
        ),
        category="Control 1 — Inventory of Enterprise Assets",
        severity=ControlSeverity.medium,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation=(
            "Ensure sync schedules are active and completing successfully. "
            "Check the Sync view for errors or stalled sync runs. "
            "Verify the SentinelOne API connection is functional."
        ),
    ),
    # ── Control 2: Inventory and Control of Software Assets ──────────────
    ControlDefinition(
        id="CIS-2.1",
        framework_id=FrameworkId.cis_v8,
        name="Establish and Maintain Software Inventory",
        description=(
            "CIS Safeguard 2.1 (IG1): Establish and maintain a detailed "
            "inventory of all licensed software installed on enterprise "
            "assets. This control checks that the proportion of "
            "unclassified software per endpoint remains below the "
            "threshold, ensuring the software inventory is known."
        ),
        category="Control 2 — Inventory of Software Assets",
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
        id="CIS-2.2",
        framework_id=FrameworkId.cis_v8,
        name="Ensure Authorized Software Is Currently Supported",
        description=(
            "CIS Safeguard 2.2 (IG1): Ensure that only currently "
            "supported software is designated as authorized in the "
            "software inventory. This control detects End-of-Life "
            "software that no longer receives security patches."
        ),
        category="Control 2 — Inventory of Software Assets",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        remediation=(
            "Upgrade or replace End-of-Life software with supported "
            "alternatives. For legacy systems that cannot be updated, "
            "document compensating controls and risk acceptance. "
            "See Library Sources > endoflife.date for lifecycle data."
        ),
    ),
    ControlDefinition(
        id="CIS-2.3",
        framework_id=FrameworkId.cis_v8,
        name="Address Unauthorized Software",
        description=(
            "CIS Safeguard 2.3 (IG1): Ensure that unauthorized software "
            "is either removed from use on enterprise assets or receives "
            "a documented exception. This control detects applications "
            "classified as Prohibited on managed endpoints."
        ),
        category="Control 2 — Inventory of Software Assets",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited applications from affected endpoints. "
            "If an exception is needed, document the business "
            "justification and disable this control for the scoped "
            "endpoints with a disable_reason."
        ),
    ),
    ControlDefinition(
        id="CIS-2.5",
        framework_id=FrameworkId.cis_v8,
        name="Allowlist Authorized Software",
        description=(
            "CIS Safeguard 2.5 (IG2): Use technical controls to ensure "
            "that only authorized software can execute or be accessed "
            "on enterprise assets. This control verifies that configured "
            "required security applications are installed. Requires "
            "tenant-specific configuration."
        ),
        category="Control 2 — Inventory of Software Assets",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required authorized applications for this "
            "control in Compliance > Settings > CIS Controls v8 > "
            "CIS-2.5. Specify the application names that must be "
            "present. Then deploy to all endpoints missing them."
        ),
    ),
    ControlDefinition(
        id="CIS-2.6",
        framework_id=FrameworkId.cis_v8,
        name="Allowlist Authorized Libraries — Change Detection",
        description=(
            "CIS Safeguard 2.6 (IG2): Use technical controls to ensure "
            "that only authorized libraries can load into a system "
            "process. This control detects software changes between "
            "sync windows, flagging unauthorized installations or "
            "removals."
        ),
        category="Control 2 — Inventory of Software Assets",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review detected software changes in the Anomalies view. "
            "Verify that all changes were authorized. Investigate "
            "unexpected installations or removals that may indicate "
            "unauthorized library loading."
        ),
    ),
    ControlDefinition(
        id="CIS-2.7",
        framework_id=FrameworkId.cis_v8,
        name="Allowlist Authorized Scripts — Software Classification",
        description=(
            "CIS Safeguard 2.7 (IG3): Use technical controls to ensure "
            "that only authorized scripts can execute. This control "
            "verifies that classification coverage is high, ensuring "
            "all software (including scripting environments) is "
            "identified and categorized."
        ),
        category="Control 2 — Inventory of Software Assets",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        remediation=(
            "Increase classification coverage by running the "
            "classification engine and creating fingerprints for "
            "unclassified scripting environments and development tools."
        ),
    ),
    # ── Control 7: Continuous Vulnerability Management ───────────────────
    ControlDefinition(
        id="CIS-7.1",
        framework_id=FrameworkId.cis_v8,
        name="Establish Vulnerability Management Process",
        description=(
            "CIS Safeguard 7.1 (IG1): Establish and maintain a "
            "documented vulnerability management process for enterprise "
            "assets. This control detects End-of-Life software with "
            "known vulnerability exposure across the managed fleet."
        ),
        category="Control 7 — Continuous Vulnerability Management",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        remediation=(
            "Review all End-of-Life software flagged by this control. "
            "Remove or replace unsupported software. Document "
            "compensating controls for legacy systems."
        ),
    ),
    ControlDefinition(
        id="CIS-7.3",
        framework_id=FrameworkId.cis_v8,
        name="Perform Automated Operating System Patch Management",
        description=(
            "CIS Safeguard 7.3 (IG1): Perform operating system updates "
            "on enterprise assets through automated patch management. "
            "This control verifies that the SentinelOne agent version "
            "is current, serving as a proxy for OS-level patching "
            "discipline across the fleet."
        ),
        category="Control 7 — Continuous Vulnerability Management",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation=(
            "Update the SentinelOne agent to the current fleet baseline "
            "version. Use the SentinelOne console to schedule agent "
            "upgrades. Agent version currency correlates with OS patch "
            "management discipline."
        ),
    ),
    ControlDefinition(
        id="CIS-7.4",
        framework_id=FrameworkId.cis_v8,
        name="Perform Automated Application Patch Management",
        description=(
            "CIS Safeguard 7.4 (IG1): Perform application updates on "
            "enterprise assets through automated patch management. "
            "This control checks that installed application versions "
            "are current against the library baseline."
        ),
        category="Control 7 — Continuous Vulnerability Management",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        remediation=(
            "Update outdated applications to their current versions. "
            "Prioritize updates for applications with known "
            "vulnerabilities. Use the Library view to compare installed "
            "versions against the baseline."
        ),
    ),
    # ── Control 10: Malware Defenses ─────────────────────────────────────
    ControlDefinition(
        id="CIS-10.1",
        framework_id=FrameworkId.cis_v8,
        name="Deploy and Maintain Anti-Malware Software",
        description=(
            "CIS Safeguard 10.1 (IG1): Deploy and maintain anti-malware "
            "software on all enterprise assets. This control verifies "
            "that all managed endpoints have their SentinelOne agent "
            "online and reporting within a strict window."
        ),
        category="Control 10 — Malware Defenses",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        remediation=(
            "Investigate endpoints offline for more than 24 hours "
            "immediately. These endpoints lack active anti-malware "
            "protection. Check network connectivity and verify the "
            "SentinelOne agent service is running."
        ),
    ),
    ControlDefinition(
        id="CIS-10.2",
        framework_id=FrameworkId.cis_v8,
        name="Configure Automatic Anti-Malware Signature Updates",
        description=(
            "CIS Safeguard 10.2 (IG1): Configure automatic updates for "
            "anti-malware signature files on all enterprise assets. "
            "This control verifies that the SentinelOne agent version "
            "is current, ensuring the latest detection capabilities."
        ),
        category="Control 10 — Malware Defenses",
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
        id="CIS-10.7",
        framework_id=FrameworkId.cis_v8,
        name="Use Behavior-Based Anti-Malware Software",
        description=(
            "CIS Safeguard 10.7 (IG2): Use behavior-based anti-malware "
            "software. SentinelOne is a behavior-based EDR platform. "
            "This control verifies that all managed endpoints have "
            "their SentinelOne agent online within a 7-day window, "
            "ensuring behavior-based detection coverage."
        ),
        category="Control 10 — Malware Defenses",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 7},
        remediation=(
            "Investigate endpoints offline for more than 7 days. "
            "Verify whether the endpoint is decommissioned, has "
            "connectivity issues, or requires agent reinstallation."
        ),
    ),
]
