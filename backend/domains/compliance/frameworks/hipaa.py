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
            "§164.308(a)(1) requires an accurate risk analysis of ePHI "
            "systems. This control verifies that the classification engine "
            "has processed at least 90% of applications on ePHI endpoints, "
            "ensuring the software inventory is complete enough for risk analysis."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Run the classification engine on all unprocessed ePHI endpoints. "
            "Review the Agents view and filter by scope tag 'HIPAA' to find "
            "endpoints with low classification coverage."
        ),
    ),
    ControlDefinition(
        id="HIPAA-308a1-SYNC",
        framework_id=FrameworkId.hipaa,
        name="Risk Analysis — Data Currency",
        description=(
            "§164.308(a)(1) requires ongoing risk analysis based on current "
            "data. This control checks that the most recent data sync "
            "completed within 24 hours, ensuring the software inventory "
            "reflects the current state of ePHI endpoints."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        hipaa_type=HipaaType.required,
        remediation=(
            "Check the Sync view for errors or stalled sync runs. "
            "Ensure sync schedules are active and the SentinelOne API "
            "connection is functional."
        ),
    ),
    ControlDefinition(
        id="HIPAA-308a5",
        framework_id=FrameworkId.hipaa,
        name="Security Awareness — Training Software",
        description=(
            "§164.308(a)(5) requires security awareness and training. "
            "This control checks whether the configured training software "
            "is installed on ePHI endpoints. Requires tenant-specific "
            "configuration of which training software to check."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.low,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation=(
            "Configure the training software name in Compliance > Settings "
            "> HIPAA > HIPAA-308a5. Specify the app_pattern (e.g. "
            "'KnowBe4*'). Until configured, this control shows "
            "not_applicable."
        ),
    ),
    ControlDefinition(
        id="HIPAA-308a6",
        framework_id=FrameworkId.hipaa,
        name="Security Incident — EDR Active",
        description=(
            "§164.308(a)(6) requires security incident procedures. This "
            "control verifies that the SentinelOne agent has checked in "
            "within 1 day on all ePHI endpoints, ensuring EDR-based "
            "incident detection is not interrupted by offline agents."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 1},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Investigate offline ePHI endpoints immediately. Check network "
            "connectivity, verify the SentinelOne agent service is running, "
            "and restore communication with the management console."
        ),
    ),
    # ── §164.312 Technical Safeguards ──────────────────────────────────
    ControlDefinition(
        id="HIPAA-312a1",
        framework_id=FrameworkId.hipaa,
        name="Access Control — Authorised Software Only",
        description=(
            "§164.312(a)(1) requires access controls for ePHI systems. "
            "This control detects any applications classified as Prohibited "
            "on ePHI endpoints, enforcing that only authorized software is "
            "installed on systems processing electronic health information."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Remove all prohibited applications from affected ePHI "
            "endpoints immediately. Review the taxonomy to ensure the "
            "prohibited classification is current. Investigate how "
            "unauthorized software was installed."
        ),
    ),
    ControlDefinition(
        id="HIPAA-312a1-UNCL",
        framework_id=FrameworkId.hipaa,
        name="Access Control — Unclassified Threshold",
        description=(
            "§164.312(a)(1) requires that only authorized persons access "
            "ePHI. This control checks that the percentage of unclassified "
            "applications per ePHI endpoint stays below 5%, ensuring all "
            "software is categorized and authorization status is known."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Review unclassified applications on flagged ePHI endpoints. "
            "Use the taxonomy editor to classify unknown software or "
            "create fingerprints for recurring unclassified applications."
        ),
    ),
    ControlDefinition(
        id="HIPAA-312a2iv",
        framework_id=FrameworkId.hipaa,
        name="Encryption Software Installed",
        description=(
            "§164.312(a)(2)(iv) addresses encryption of ePHI. This "
            "control checks whether full-disk encryption software matching "
            "the configured pattern is installed on all ePHI endpoints, "
            "defaulting to BitLocker detection."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.critical,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "BitLocker*", "must_exist": True},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation=(
            "Deploy BitLocker (Windows) or FileVault (macOS) on all ePHI "
            "endpoints. To check for FileVault instead, update the "
            "app_pattern in Compliance > Settings > HIPAA > HIPAA-312a2iv."
        ),
    ),
    ControlDefinition(
        id="HIPAA-312b",
        framework_id=FrameworkId.hipaa,
        name="Audit Controls — Software Change Tracking",
        description=(
            "§164.312(b) requires audit controls for ePHI systems. This "
            "control detects software additions and removals within the "
            "last 24 hours on ePHI endpoints, maintaining a change audit "
            "trail for compliance evidence."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Review detected software changes in the Anomalies view. "
            "Ensure sync schedules are active so the audit trail remains "
            "continuous. Investigate any unexpected changes on ePHI systems."
        ),
    ),
    ControlDefinition(
        id="HIPAA-312c1",
        framework_id=FrameworkId.hipaa,
        name="Integrity Controls — Unauthorised Changes",
        description=(
            "§164.312(c)(1) requires integrity controls for ePHI. This "
            "control detects unauthorized software modifications within "
            "a 12-hour window on ePHI endpoints, using a tighter lookback "
            "than the audit trail control to catch rapid changes."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 12},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation=(
            "Review all software changes on ePHI systems in the Anomalies "
            "view. Verify that changes were authorized. Escalate "
            "unauthorized modifications per incident response procedures."
        ),
    ),
    ControlDefinition(
        id="HIPAA-312e1",
        framework_id=FrameworkId.hipaa,
        name="Transmission Security — VPN Software",
        description=(
            "§164.312(e)(1) addresses transmission security for ePHI. "
            "This control checks whether the configured VPN or secure "
            "communication software is installed on remote ePHI endpoints. "
            "Requires tenant-specific configuration of which VPN client "
            "to check."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.medium,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation=(
            "Configure the VPN client name in Compliance > Settings "
            "> HIPAA > HIPAA-312e1. Specify the app_pattern (e.g. "
            "'Cisco AnyConnect*'). Until configured, this control shows "
            "not_applicable."
        ),
    ),
    ControlDefinition(
        id="HIPAA-312a1-EOL",
        framework_id=FrameworkId.hipaa,
        name="EOL Software Access Risk",
        description=(
            "End-of-Life software on ePHI endpoints represents an access "
            "control risk as it no longer receives security patches. "
            "This control detects EOL software using endoflife.date "
            "lifecycle data."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Replace End-of-Life software on ePHI endpoints with "
            "supported versions. EOL software cannot be patched and "
            "poses a risk to ePHI confidentiality and integrity."
        ),
    ),
    # ── Additional endpoint-specific controls ──────────────────────────
    ControlDefinition(
        id="HIPAA-312d",
        framework_id=FrameworkId.hipaa,
        name="Person Authentication — EDR Version",
        description=(
            "§164.312(d) requires person or entity authentication. This "
            "control checks that the SentinelOne agent version is current "
            "across all ePHI endpoints, ensuring the security platform "
            "provides up-to-date identity-based threat detection."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Update the SentinelOne agent to the current fleet baseline "
            "version on all ePHI endpoints. Use the SentinelOne console "
            "to schedule agent upgrades."
        ),
    ),
    ControlDefinition(
        id="HIPAA-AVAIL-1",
        framework_id=FrameworkId.hipaa,
        name="ePHI System Availability",
        description=(
            "HIPAA requires availability of ePHI. This control verifies "
            "that all ePHI endpoints have checked in within 3 days, "
            "detecting systems that may have lost connectivity and can "
            "no longer be monitored or protected."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 3},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Investigate ePHI endpoints offline for more than 3 days. "
            "Verify whether the endpoint is decommissioned, has "
            "connectivity issues, or requires agent reinstallation."
        ),
    ),
    ControlDefinition(
        id="HIPAA-SW-CURR",
        framework_id=FrameworkId.hipaa,
        name="ePHI Software Currency",
        description=(
            "Keeping software current on ePHI endpoints mitigates known "
            "vulnerabilities. This control checks that no more than 10% "
            "of installed applications are running outdated versions "
            "compared to the library baseline."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.medium,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.addressable,
        remediation=(
            "Update outdated applications on ePHI endpoints to their "
            "current versions. Use the Library view to compare installed "
            "versions against the baseline and prioritize updates for "
            "applications with known vulnerabilities."
        ),
    ),
    ControlDefinition(
        id="HIPAA-REQ-SW",
        framework_id=FrameworkId.hipaa,
        name="Required Security Software on ePHI",
        description=(
            "All ePHI endpoints must have mandatory security software "
            "installed. This control verifies that the configured required "
            "applications are present on all ePHI endpoints. Requires "
            "tenant-specific configuration of which applications to check."
        ),
        category="§164.312 — Technical Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Configure the required security software in Compliance > "
            "Settings > HIPAA > HIPAA-REQ-SW. Specify the application "
            "names that must be present on ePHI endpoints."
        ),
    ),
    ControlDefinition(
        id="HIPAA-CLASS-COV",
        framework_id=FrameworkId.hipaa,
        name="ePHI Classification Coverage",
        description=(
            "ePHI endpoints require a higher classification threshold "
            "than the general fleet. This control checks that at least "
            "95% of applications are classified on ePHI endpoints, "
            "ensuring near-complete visibility into the software landscape."
        ),
        category="§164.308 — Administrative Safeguards",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 95},
        scope_tags=["HIPAA"],
        hipaa_type=HipaaType.required,
        remediation=(
            "Run the classification engine on ePHI endpoints with low "
            "coverage. Use the taxonomy editor to classify unknown "
            "software or create fingerprints for recurring unclassified "
            "applications."
        ),
    ),
]
