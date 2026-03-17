"""NIS2 — EU Directive 2022/2555 control definitions.

NIS2 (Network and Information Security Directive 2) is the EU directive
that establishes cybersecurity obligations for essential and important
entities across 18 sectors.  National transposition was due by October
2024.  Article 21 defines minimum technical and organizational measures.

Sentora evaluates the subset of Article 21(2) measures that can be
validated through endpoint software inventory data: risk analysis and
IT system security (a), supply chain security (d), acquisition,
development and maintenance security (e), basic cyber hygiene (h), and
cryptography and encryption (i).

Measures covering incident handling (b), business continuity (c),
effectiveness assessment (f), incident reporting (g), and multi-factor
authentication (j) require capabilities outside endpoint software
monitoring.

This module does not constitute legal advice.  National implementations
of NIS2 may vary.
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
    id=FrameworkId.nis2,
    name="NIS2 — EU Directive 2022/2555",
    version="2022/2555",
    description=(
        "NIS2 is the EU directive establishing cybersecurity obligations for "
        "essential and important entities. Sentora evaluates the endpoint "
        "software management aspects of Article 21(2) — specifically risk "
        "analysis and IT system security (a), supply chain security (d), "
        "acquisition, development and maintenance security (e), basic cyber "
        "hygiene practices (h), and cryptography and encryption (i)."
    ),
    disclaimer=(
        "Sentora evaluates NIS2 compliance exclusively from the perspective "
        "of endpoint software inventory, classification, and enforcement. "
        "NIS2 compliance requires comprehensive risk management, incident "
        "reporting to national CSIRTs within 24/72 hours, supply chain "
        "security assessments, business continuity planning, and governance "
        "measures beyond endpoint monitoring. National implementations of "
        "NIS2 may impose additional requirements. This module does not "
        "constitute legal advice. Organizations should consult qualified "
        "legal and compliance professionals for full NIS2 compliance."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── Art. 21(2)(a) — Risk analysis and IT system security ─────────────
    ControlDefinition(
        id="NIS2-21.2a-1",
        framework_id=FrameworkId.nis2,
        name="IT System Security — Endpoint Protection Active",
        description=(
            "Art. 21(2)(a) requires policies on risk analysis and "
            "information system security. This control verifies that all "
            "managed endpoints have their security agent online and "
            "reporting, ensuring continuous security monitoring coverage."
        ),
        category="Policies on risk analysis (Art. 21.2a)",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 3},
        remediation=(
            "Investigate offline endpoints. Check network connectivity, "
            "verify the SentinelOne agent service is running, and "
            "restore communication with the management console. "
            "Offline endpoints cannot be monitored or protected."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2a-2",
        framework_id=FrameworkId.nis2,
        name="IT System Security — EDR Agent Currency",
        description=(
            "Art. 21(2)(a) requires information system security measures. "
            "This control verifies that the SentinelOne agent version is "
            "current across all managed endpoints, ensuring the security "
            "platform is not running outdated versions with known issues."
        ),
        category="Policies on risk analysis (Art. 21.2a)",
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
        id="NIS2-21.2a-3",
        framework_id=FrameworkId.nis2,
        name="Risk Analysis — EOL Software Exposure",
        description=(
            "Art. 21(2)(a) requires risk analysis for information systems. "
            "This control detects End-of-Life software that no longer "
            "receives security patches, representing unmitigatable risk "
            "exposure on managed endpoints."
        ),
        category="Policies on risk analysis (Art. 21.2a)",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        remediation=(
            "Upgrade or replace End-of-Life software with supported "
            "alternatives. For legacy systems that cannot be updated, "
            "document compensating controls and risk acceptance."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2a-INV",
        framework_id=FrameworkId.nis2,
        name="Risk Analysis — Asset Inventory Completeness",
        description=(
            "Art. 21(2)(a) requires risk analysis which presupposes "
            "a complete asset inventory. This control verifies that "
            "the classification engine has processed all managed "
            "endpoints, ensuring the software asset inventory is "
            "comprehensive for risk assessment purposes."
        ),
        category="Policies on risk analysis (Art. 21.2a)",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation=(
            "Run the classification engine on all unprocessed agents. "
            "Navigate to Apps Overview and filter by 'unclassified' "
            "to identify endpoints missing classification results."
        ),
    ),
    # ── Art. 21(2)(d) — Supply chain security ────────────────────────────
    ControlDefinition(
        id="NIS2-21.2d-1",
        framework_id=FrameworkId.nis2,
        name="Supply Chain — Software Patch Currency",
        description=(
            "Art. 21(2)(d) requires supply chain security measures "
            "including security aspects of supplier relationships. "
            "This control checks that installed application versions "
            "are current, ensuring third-party software patches are "
            "applied in a timely manner."
        ),
        category="Supply chain security (Art. 21.2d)",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 15},
        remediation=(
            "Update outdated applications to their current versions. "
            "Prioritize updates for third-party software with known "
            "vulnerabilities. Use the Library view to compare installed "
            "versions against the baseline."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2d-2",
        framework_id=FrameworkId.nis2,
        name="Supply Chain — Third-Party EOL Software",
        description=(
            "Art. 21(2)(d) requires addressing security in supplier "
            "relationships. This control detects End-of-Life third-party "
            "software that no longer receives vendor support, indicating "
            "supply chain risk from unsupported products."
        ),
        category="Supply chain security (Art. 21.2d)",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        remediation=(
            "Replace End-of-Life third-party software with supported "
            "alternatives. Contact vendors for migration paths. "
            "Document compensating controls for products that cannot "
            "be replaced immediately."
        ),
    ),
    # ── Art. 21(2)(e) — Acquisition, development, maintenance ───────────
    ControlDefinition(
        id="NIS2-21.2e-1",
        framework_id=FrameworkId.nis2,
        name="Acquisition Security — No Unauthorized Software",
        description=(
            "Art. 21(2)(e) requires security in network and information "
            "system acquisition, development, and maintenance, including "
            "vulnerability handling. This control detects applications "
            "classified as Prohibited on managed endpoints."
        ),
        category="Acquisition, development, maintenance (Art. 21.2e)",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited applications from affected endpoints. "
            "Review the taxonomy to ensure prohibited classifications "
            "align with the organization's acquisition security policy."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2e-2",
        framework_id=FrameworkId.nis2,
        name="Maintenance Security — Required Security Software",
        description=(
            "Art. 21(2)(e) requires system maintenance security. This "
            "control verifies that configured required security "
            "applications are installed on all managed endpoints. "
            "Requires tenant-specific configuration."
        ),
        category="Acquisition, development, maintenance (Art. 21.2e)",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required security applications for this "
            "control in Compliance > Settings > NIS2 > NIS2-21.2e-2. "
            "Specify the application names that must be present. "
            "Then deploy to all endpoints missing them."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2e-3",
        framework_id=FrameworkId.nis2,
        name="Acquisition Security — Software Classification",
        description=(
            "Art. 21(2)(e) requires vulnerability handling and "
            "disclosure. This control verifies that software assets "
            "are classified, enabling vulnerability management by "
            "ensuring all software is identified and categorized."
        ),
        category="Acquisition, development, maintenance (Art. 21.2e)",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 80},
        remediation=(
            "Increase classification coverage by running the "
            "classification engine and creating fingerprints for "
            "unclassified applications."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2e-CHG",
        framework_id=FrameworkId.nis2,
        name="Maintenance Security — Change Detection",
        description=(
            "Art. 21(2)(e) requires security during maintenance. This "
            "control detects software changes between sync windows, "
            "flagging unauthorized installations or removals that may "
            "introduce vulnerabilities during maintenance activities."
        ),
        category="Acquisition, development, maintenance (Art. 21.2e)",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review detected software changes in the Anomalies view. "
            "Verify that all changes were authorized through the "
            "organization's change management process."
        ),
    ),
    # ── Art. 21(2)(h) — Basic cyber hygiene ──────────────────────────────
    ControlDefinition(
        id="NIS2-21.2h-1",
        framework_id=FrameworkId.nis2,
        name="Cyber Hygiene — Software Inventory Known",
        description=(
            "Art. 21(2)(h) requires basic cyber hygiene practices. "
            "A fundamental hygiene measure is knowing what software is "
            "installed. This control verifies that the proportion of "
            "unclassified applications remains below the threshold."
        ),
        category="Cyber hygiene practices (Art. 21.2h)",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        remediation=(
            "Classify unknown applications on flagged endpoints. "
            "Use the taxonomy editor to categorize unidentified "
            "software. Basic cyber hygiene requires knowing what "
            "software runs on your endpoints."
        ),
    ),
    ControlDefinition(
        id="NIS2-21.2h-2",
        framework_id=FrameworkId.nis2,
        name="Cyber Hygiene — Data Freshness",
        description=(
            "Art. 21(2)(h) requires basic cyber hygiene practices. "
            "Maintaining current data is a hygiene fundamental. This "
            "control checks that the most recent data sync completed "
            "within the configured time window."
        ),
        category="Cyber hygiene practices (Art. 21.2h)",
        severity=ControlSeverity.medium,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 48},
        remediation=(
            "Check the Sync view for errors or stalled sync runs. "
            "Ensure sync schedules are configured and the SentinelOne "
            "API connection is healthy."
        ),
    ),
    # ── Art. 21(2)(i) — Cryptography and encryption ──────────────────────
    ControlDefinition(
        id="NIS2-21.2i-1",
        framework_id=FrameworkId.nis2,
        name="Cryptography — Encryption Software Present",
        description=(
            "Art. 21(2)(i) requires policies and procedures regarding "
            "the use of cryptography and encryption. This control "
            "checks whether configured encryption software is present "
            "on managed endpoints. Requires tenant-specific "
            "configuration."
        ),
        category="Cryptography and encryption (Art. 21.2i)",
        severity=ControlSeverity.high,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        remediation=(
            "Configure the encryption software pattern for this control "
            "in Compliance > Settings > NIS2 > NIS2-21.2i-1. Specify "
            "the encryption product name pattern (e.g. 'BitLocker*', "
            "'FileVault*'). Then deploy encryption to all endpoints."
        ),
    ),
]
