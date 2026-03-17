"""DORA — Digital Operational Resilience Act control definitions.

DORA (EU Regulation 2022/2554) strengthens the digital resilience of
EU financial entities.  These controls map DORA articles to Sentora's
endpoint software management capabilities.  They cover ICT asset
identification (Art. 8), protection and prevention (Art. 9), detection
(Art. 10), business continuity (Art. 11), and third-party software
risk (Art. 28).  This module does not constitute legal advice.
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
    id=FrameworkId.dora,
    name="DORA — Digital Operational Resilience Act",
    version="EU 2022/2554",
    description=(
        "The Digital Operational Resilience Act (DORA) is an EU regulation "
        "that strengthens the digital resilience of financial entities by "
        "standardizing ICT risk management, third-party oversight, incident "
        "reporting, and resilience testing. Sentora covers the endpoint "
        "software management aspects of DORA — specifically ICT asset "
        "identification (Art. 8), protection and prevention (Art. 9), "
        "detection (Art. 10), business continuity (Art. 11), and "
        "third-party software risk (Art. 28)."
    ),
    disclaimer=(
        "Sentora evaluates DORA compliance exclusively from the perspective "
        "of endpoint software inventory, classification, and enforcement. "
        "DORA encompasses broader requirements including ICT incident "
        "reporting (Art. 17-19), digital operational resilience testing "
        "(Art. 24-27), ICT third-party contractual arrangements (Art. 28-30), "
        "and information sharing (Art. 45) that are outside Sentora's scope. "
        "This module does not constitute legal advice. Financial entities "
        "should consult qualified legal and compliance professionals for "
        "full DORA compliance assessment."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── ICT Asset Identification (Art. 8) ────────────────────────────────
    ControlDefinition(
        id="DORA-8.1-01",
        framework_id=FrameworkId.dora,
        name="ICT Asset Inventory Completeness",
        description=(
            "Art. 8(1) requires financial entities to identify, classify, "
            "and document all ICT assets. This control verifies that the "
            "classification engine has processed all managed endpoints, "
            "ensuring no ICT assets remain unidentified in the inventory."
        ),
        category="ICT Asset Identification (Art. 8)",
        severity=ControlSeverity.critical,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        remediation=(
            "Run the classification engine on all unprocessed agents. "
            "Review the Agents view and filter by 'unclassified' to find "
            "endpoints missing classification results."
        ),
    ),
    ControlDefinition(
        id="DORA-8.1-02",
        framework_id=FrameworkId.dora,
        name="ICT Asset Classification Coverage",
        description=(
            "Art. 8(1) mandates that ICT assets are classified. This "
            "control checks that the percentage of unclassified "
            "applications per endpoint remains below the threshold, "
            "ensuring applications are properly categorized as part of "
            "the ICT asset register."
        ),
        category="ICT Asset Identification (Art. 8)",
        severity=ControlSeverity.high,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        remediation=(
            "Review unclassified applications on flagged endpoints. "
            "Use the taxonomy editor to classify unknown software or "
            "create fingerprints for recurring unclassified applications."
        ),
    ),
    ControlDefinition(
        id="DORA-8.4-01",
        framework_id=FrameworkId.dora,
        name="Critical ICT Asset Identification",
        description=(
            "Art. 8(4) requires financial entities to identify and map "
            "all information and ICT assets, with special attention to "
            "critical assets. This control verifies that configured "
            "critical ICT applications are present on all managed "
            "endpoints. Requires tenant-specific configuration of which "
            "applications constitute critical ICT assets."
        ),
        category="ICT Asset Identification (Art. 8)",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required critical ICT applications for this "
            "control in Compliance > Settings > DORA > DORA-8.4-01. "
            "Specify the application names that must be present on all "
            "endpoints (e.g. asset management agents, monitoring tools)."
        ),
    ),
    ControlDefinition(
        id="DORA-8.6-01",
        framework_id=FrameworkId.dora,
        name="ICT Inventory Freshness",
        description=(
            "Art. 8(6) requires maintained inventories to be updated "
            "periodically and after major changes. This control checks "
            "that the most recent data sync completed within the "
            "configured time window, ensuring the ICT asset inventory "
            "reflects the current state of managed endpoints."
        ),
        category="ICT Asset Identification (Art. 8)",
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
        id="DORA-8.2-01",
        framework_id=FrameworkId.dora,
        name="ICT Risk Source Detection",
        description=(
            "Art. 8(2) requires continuous identification of all sources "
            "of ICT risk. This control detects new or removed applications "
            "between sync windows, flagging changes in the ICT asset "
            "landscape that may introduce new risk sources."
        ),
        category="ICT Asset Identification (Art. 8)",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review newly detected applications in the Anomalies view. "
            "Classify new software and assess whether it introduces "
            "additional ICT risk. Investigate any unexpected removals."
        ),
    ),
    ControlDefinition(
        id="DORA-8.7-01",
        framework_id=FrameworkId.dora,
        name="Legacy ICT System Assessment",
        description=(
            "Art. 8(7) requires yearly ICT risk assessment on all legacy "
            "ICT systems. This control uses endoflife.date lifecycle data "
            "to detect End-of-Life software that qualifies as legacy ICT "
            "no longer receiving security patches."
        ),
        category="ICT Asset Identification (Art. 8)",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        remediation=(
            "Upgrade or replace End-of-Life software with supported "
            "alternatives. For legacy systems that cannot be updated, "
            "document compensating controls as required by Art. 8(7). "
            "See endoflife.date for supported version information."
        ),
    ),
    # ── ICT Protection & Prevention (Art. 9) ─────────────────────────────
    ControlDefinition(
        id="DORA-9.1-01",
        framework_id=FrameworkId.dora,
        name="Endpoint Security Monitoring Active",
        description=(
            "Art. 9(1) requires continuous monitoring and control of the "
            "security of ICT systems. This control verifies that all "
            "managed endpoints have checked in within the configured "
            "time window, ensuring security monitoring coverage is not "
            "interrupted by offline agents."
        ),
        category="ICT Protection & Prevention (Art. 9)",
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
        id="DORA-9.2-01",
        framework_id=FrameworkId.dora,
        name="EDR Protection on All Endpoints",
        description=(
            "Art. 9(2) requires deployment of ICT security tools that "
            "ensure resilience, continuity, and availability. This "
            "control verifies that the configured EDR solution is "
            "installed on all endpoints. Requires tenant-specific "
            "configuration of which EDR product to check."
        ),
        category="ICT Protection & Prevention (Art. 9)",
        severity=ControlSeverity.critical,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required EDR software for this control in "
            "Compliance > Settings > DORA > DORA-9.2-01. Specify the "
            "EDR product name (e.g. 'SentinelOne'). Then deploy the "
            "EDR agent to all endpoints missing it."
        ),
    ),
    ControlDefinition(
        id="DORA-9.2-02",
        framework_id=FrameworkId.dora,
        name="Encryption Software Present",
        description=(
            "Art. 9(2) requires ICT security tools ensuring "
            "confidentiality of data. This control verifies that the "
            "configured encryption software is installed on all "
            "endpoints. Requires tenant-specific configuration of which "
            "encryption tool to check."
        ),
        category="ICT Protection & Prevention (Art. 9)",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required encryption software for this control "
            "in Compliance > Settings > DORA > DORA-9.2-02. Specify the "
            "encryption product name (e.g. 'BitLocker', 'FileVault'). "
            "Then deploy encryption to all endpoints missing it."
        ),
    ),
    ControlDefinition(
        id="DORA-9.3-01",
        framework_id=FrameworkId.dora,
        name="Unauthorized Software Restriction",
        description=(
            "Art. 9(3c) requires limiting access to ICT assets to what "
            "is required for approved functions. This control detects "
            "any applications classified as Prohibited on managed "
            "endpoints, enforcing software authorization policies."
        ),
        category="ICT Protection & Prevention (Art. 9)",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited applications from affected endpoints "
            "immediately. Review the taxonomy to ensure the prohibited "
            "classification is current. Investigate how unauthorized "
            "software was installed."
        ),
    ),
    ControlDefinition(
        id="DORA-9.3-02",
        framework_id=FrameworkId.dora,
        name="ICT Change Detection",
        description=(
            "Art. 9(3e) requires implementation of ICT change management. "
            "This control detects software changes between sync windows, "
            "supporting change management by flagging new installations "
            "and removals for review."
        ),
        category="ICT Protection & Prevention (Art. 9)",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review detected software changes in the Anomalies view. "
            "Verify that all changes were authorized through the "
            "organization's change management process."
        ),
    ),
    ControlDefinition(
        id="DORA-9.4-01",
        framework_id=FrameworkId.dora,
        name="Security Agent Version Currency",
        description=(
            "Art. 9(4) requires implementation of patch and update "
            "management. This control checks that the SentinelOne agent "
            "version is current across all managed endpoints, ensuring "
            "the security platform itself is not running outdated or "
            "vulnerable versions."
        ),
        category="ICT Protection & Prevention (Art. 9)",
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
        id="DORA-9.4-02",
        framework_id=FrameworkId.dora,
        name="Software Patch Currency",
        description=(
            "Art. 9(4) requires patch and update management for all ICT "
            "systems. This control checks that installed application "
            "versions are current against the library baseline, detecting "
            "endpoints running outdated software that may contain known "
            "vulnerabilities."
        ),
        category="ICT Protection & Prevention (Art. 9)",
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
    # ── ICT Anomaly Detection (Art. 10) ──────────────────────────────────
    ControlDefinition(
        id="DORA-10.1-01",
        framework_id=FrameworkId.dora,
        name="Software Change Anomaly Detection",
        description=(
            "Art. 10(1) requires implementation of tools to detect "
            "anomalous activities and allocate resources to monitor "
            "user behavior and ICT anomalies. This control detects "
            "new or removed software between sync windows as potential "
            "anomalous changes in the ICT environment."
        ),
        category="ICT Anomaly Detection (Art. 10)",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review all software changes detected in the Anomalies view. "
            "Investigate unexpected installations or removals. Escalate "
            "anomalous changes per the organization's incident response "
            "procedures."
        ),
    ),
    ControlDefinition(
        id="DORA-10.1-02",
        framework_id=FrameworkId.dora,
        name="Unclassified Software Anomaly",
        description=(
            "Art. 10(1) requires monitoring for ICT anomalies. "
            "Unclassified software on endpoints represents potentially "
            "anomalous or unauthorized applications. This control flags "
            "endpoints where the proportion of unclassified applications "
            "exceeds the acceptable threshold."
        ),
        category="ICT Anomaly Detection (Art. 10)",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        remediation=(
            "Classify unknown applications on flagged endpoints. "
            "Investigate whether unclassified software is authorized. "
            "Create fingerprints for legitimate applications to prevent "
            "future false positives."
        ),
    ),
    # ── ICT Business Continuity (Art. 11) ────────────────────────────────
    ControlDefinition(
        id="DORA-11.1-01",
        framework_id=FrameworkId.dora,
        name="Endpoint Monitoring Continuity",
        description=(
            "Art. 11(1) requires ICT business continuity policies that "
            "ensure monitoring capabilities remain operational. This "
            "control checks that all agents have checked in within "
            "a wider tolerance window, detecting endpoints that have "
            "lost connectivity to the management platform."
        ),
        category="ICT Business Continuity (Art. 11)",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 7},
        remediation=(
            "Investigate endpoints offline for more than 7 days. "
            "Verify whether the endpoint is decommissioned, has "
            "connectivity issues, or requires agent reinstallation. "
            "Update the agent inventory to reflect current state."
        ),
    ),
    ControlDefinition(
        id="DORA-11.2-01",
        framework_id=FrameworkId.dora,
        name="Data Collection Continuity",
        description=(
            "Art. 11(2) requires backup policies and data restoration "
            "methods. This control verifies that data collection "
            "(sync) has completed within the configured window, "
            "ensuring continuous visibility into the endpoint fleet "
            "is maintained for business continuity purposes."
        ),
        category="ICT Business Continuity (Art. 11)",
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
    # ── ICT Third-Party Software Risk (Art. 28) ─────────────────────────
    ControlDefinition(
        id="DORA-28.1-01",
        framework_id=FrameworkId.dora,
        name="Third-Party Software Inventory",
        description=(
            "Art. 28(1) requires managing ICT third-party risk as an "
            "integral part of the ICT risk framework. This control "
            "verifies that the classification engine has processed all "
            "endpoints, ensuring third-party software is identified and "
            "inventoried across the managed fleet."
        ),
        category="ICT Third-Party Software Risk (Art. 28)",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation=(
            "Run the classification engine on all unprocessed agents "
            "to ensure third-party software is identified. Review "
            "classification results and update taxonomy categories "
            "for accurate third-party software tracking."
        ),
    ),
    ControlDefinition(
        id="DORA-28.1-02",
        framework_id=FrameworkId.dora,
        name="Unapproved Third-Party Software",
        description=(
            "Art. 28(1) requires managing third-party ICT risk. This "
            "control detects prohibited third-party software on managed "
            "endpoints, enforcing the organization's approved software "
            "policy for third-party applications."
        ),
        category="ICT Third-Party Software Risk (Art. 28)",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited third-party applications from "
            "affected endpoints. Review the organization's approved "
            "software list and update the taxonomy to reflect current "
            "third-party software policies."
        ),
    ),
    ControlDefinition(
        id="DORA-28.3-01",
        framework_id=FrameworkId.dora,
        name="Third-Party Software Documentation",
        description=(
            "Art. 28(3) requires maintaining a register of all "
            "contractual arrangements with ICT third-party providers. "
            "This control checks that the proportion of unclassified "
            "applications is minimized, ensuring third-party software "
            "is documented and categorized in the taxonomy."
        ),
        category="ICT Third-Party Software Risk (Art. 28)",
        severity=ControlSeverity.high,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 3},
        remediation=(
            "Classify all unclassified applications on flagged "
            "endpoints. Map third-party software to their providers "
            "in the taxonomy. Ensure the software register aligns "
            "with the contractual arrangements register."
        ),
    ),
]
