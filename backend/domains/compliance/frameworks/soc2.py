"""SOC 2 Trust Services Criteria — control definitions.

SOC 2 is principles-based, not prescriptive.  These controls represent
Sentora's interpretation of the Trust Services Criteria as they apply
to endpoint software management.  They support evidence collection for
SOC 2 audits but do not constitute SOC 2 certification.
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
    id=FrameworkId.soc2,
    name="SOC 2 Type II",
    version="2024",
    description=(
        "AICPA Trust Services Criteria for Security, Availability, "
        "Processing Integrity, Confidentiality, and Privacy"
    ),
    disclaimer=(
        "These checks support evidence collection for SOC 2 audits. "
        "They do not constitute SOC 2 certification. Full compliance "
        "requires assessment by a licensed CPA firm."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── CC6: Logical and Physical Access Controls ──────────────────────────
    ControlDefinition(
        id="SOC2-CC6.1",
        framework_id=FrameworkId.soc2,
        name="Complete Software Inventory",
        description=(
            "Verifies that all managed endpoints have synced application "
            "data within the configured time window (24 hours). Endpoints "
            "with stale or missing sync data represent gaps in the software "
            "asset inventory required by CC6.1."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation=(
            "Ensure all agents are syncing regularly. Check the Sync view "
            "for errors or stalled runs. If data is stale, trigger a manual "
            "sync from the Sync page."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC6.1-SW",
        framework_id=FrameworkId.soc2,
        name="Software Asset Classification",
        description=(
            "Checks that at least 90% of installed applications have been "
            "classified as Approved, Flagged, or Prohibited. Unclassified "
            "applications represent unknown risk that cannot be assessed "
            "for access control compliance."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation=(
            "Run the classification engine from the Classification view "
            "to classify unprocessed applications. Review unclassified "
            "applications in the App Overview and assign categories."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC6.6",
        framework_id=FrameworkId.soc2,
        name="EDR Protection on All Endpoints",
        description=(
            "Verifies all managed endpoints are running the SentinelOne "
            "agent at or above the fleet baseline version, ensuring "
            "continuous EDR protection coverage."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_version,
        parameters={},
        remediation=(
            "Update the SentinelOne agent to the fleet baseline version "
            "on all non-compliant endpoints. Check the Agent Detail view "
            "to identify outdated agents and use the SentinelOne console "
            "to schedule upgrades."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC6.7",
        framework_id=FrameworkId.soc2,
        name="No Prohibited Software",
        description=(
            "Detects unauthorized software by scanning all managed endpoints "
            "for applications classified as Prohibited in the taxonomy. "
            "Any prohibited application violates logical access controls."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove all prohibited applications from affected endpoints "
            "immediately. Review flagged endpoints in the Anomalies view "
            "and investigate how unauthorized software was installed."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC6.8",
        framework_id=FrameworkId.soc2,
        name="Required Software Installed",
        description=(
            "Verifies that configured mandatory security software is present "
            "on all managed endpoints (e.g. encryption tools, VPN clients). "
            "Requires tenant-specific configuration of which applications "
            "are required."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation=(
            "Configure the required applications for this control in "
            "Compliance > Settings > SOC 2 > SOC2-CC6.8. Specify the "
            "security software names that must be present on all endpoints "
            "(e.g. 'BitLocker', 'CrowdStrike'). Then deploy missing software."
        ),
    ),
    # ── CC7: System Operations — Monitoring ────────────────────────────────
    ControlDefinition(
        id="SOC2-CC7.1",
        framework_id=FrameworkId.soc2,
        name="Endpoint Software Change Monitoring",
        description=(
            "Detects new or removed applications between sync windows "
            "within a 24-hour lookback period. Changes in the software "
            "inventory may indicate unauthorized modifications or "
            "compromised endpoints."
        ),
        category="CC7 — System Operations",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation=(
            "Review detected software changes in the Anomalies view. "
            "Verify that all new installations were authorized. "
            "Investigate unexpected removals or additions."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC7.2",
        framework_id=FrameworkId.soc2,
        name="Classification Anomaly Detection",
        description=(
            "Checks that at least 80% of applications are classified, "
            "which is the minimum threshold needed to reliably detect "
            "anomalous software installations. Unclassified applications "
            "cannot be evaluated against the approved software policy."
        ),
        category="CC7 — System Operations",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 80},
        remediation=(
            "Run the classification engine from the Classification view "
            "to process unclassified applications. Review results in the "
            "App Overview and create fingerprints for recurring unknown "
            "applications."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC7.3",
        framework_id=FrameworkId.soc2,
        name="Unclassified Application Threshold",
        description=(
            "Flags endpoints where more than 10% of installed applications "
            "are unclassified. A high proportion of unclassified software "
            "undermines the ability to detect anomalous or unauthorized "
            "applications."
        ),
        category="CC7 — System Operations",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        remediation=(
            "Review unclassified applications on flagged endpoints in the "
            "App Overview. Use the Taxonomy Editor to classify unknown "
            "software or create fingerprints for recurring applications."
        ),
    ),
    # ── CC8: Change Management ─────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC8.1",
        framework_id=FrameworkId.soc2,
        name="Software Change Tracking",
        description=(
            "Detects software inventory changes over a 48-hour lookback "
            "window using Sentora's delta detection engine. Tracks new "
            "installations, removals, and version changes to support "
            "change management evidence collection."
        ),
        category="CC8 — Change Management",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 48},
        remediation=(
            "Ensure sync schedules are active and completing on time in "
            "the Sync view. Review detected changes in the Anomalies view "
            "and verify they align with approved change requests."
        ),
    ),
    # ── A1: Availability ──────────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-A1.1",
        framework_id=FrameworkId.soc2,
        name="Endpoint Availability",
        description=(
            "Checks that all managed endpoints have checked in within "
            "the last 7 days. Agents that have not reported in exceed "
            "the availability tolerance and may indicate decommissioned "
            "or unreachable systems."
        ),
        category="A1 — Availability",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 7},
        remediation=(
            "Investigate offline endpoints in the Agent Detail view. "
            "Verify network connectivity, check whether the endpoint is "
            "decommissioned, and restore the SentinelOne agent service "
            "if needed."
        ),
    ),
    ControlDefinition(
        id="SOC2-A1.2",
        framework_id=FrameworkId.soc2,
        name="Data Freshness",
        description=(
            "Verifies that the most recent data sync completed within "
            "the 48-hour window. Stale inventory data means compliance "
            "checks are evaluating outdated information, reducing the "
            "reliability of all other controls."
        ),
        category="A1 — Availability",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 48},
        remediation=(
            "Check the Sync view for errors or stalled sync runs. "
            "Verify the SentinelOne API connection is functional. "
            "If syncs are failing, trigger a manual sync from the "
            "Sync page."
        ),
    ),
    # ── CC3: Risk Assessment ───────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC3.1",
        framework_id=FrameworkId.soc2,
        name="Asset Classification Coverage",
        description=(
            "Checks that at least 70% of applications across managed "
            "endpoints have been classified. Classification results are "
            "the foundation for risk assessment -- unclassified software "
            "cannot be evaluated for risk."
        ),
        category="CC3 — Risk Assessment",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 70},
        remediation=(
            "Run the classification engine from the Classification view. "
            "Review unclassified applications in the App Overview and "
            "assign categories using the Taxonomy Editor."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC3.2",
        framework_id=FrameworkId.soc2,
        name="Software Version Currency",
        description=(
            "Checks that no more than 20% of installed applications are "
            "running outdated versions compared to the library baseline. "
            "Outdated software may contain known vulnerabilities that "
            "increase the organization's risk profile."
        ),
        category="CC3 — Risk Assessment",
        severity=ControlSeverity.medium,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 20},
        remediation=(
            "Review outdated applications in the Library Browser view. "
            "Prioritize updates for applications with known "
            "vulnerabilities. Deploy patches through your software "
            "distribution tooling."
        ),
    ),
    # ── CC6: EOL Software ──────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC6.1-EOL",
        framework_id=FrameworkId.soc2,
        name="End-of-Life Software Detection",
        description=(
            "End-of-Life software no longer receives security patches "
            "and represents an unmitigated risk. This control detects "
            "applications that have reached End-of-Life using "
            "endoflife.date lifecycle data."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        remediation=(
            "Upgrade End-of-Life software to a supported version. "
            "Review flagged applications in the App Overview filtered "
            "by EOL status. See endoflife.date for lifecycle information "
            "and supported version alternatives."
        ),
    ),
    # ── CC9: Risk Mitigation ──────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC9.1",
        framework_id=FrameworkId.soc2,
        name="Endpoint Protection Currency",
        description=(
            "Verifies SentinelOne agent versions are maintained at or "
            "above the fleet baseline to ensure consistent threat "
            "mitigation capabilities across the endpoint fleet."
        ),
        category="CC9 — Risk Mitigation",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation=(
            "Update the SentinelOne agent on non-compliant endpoints to "
            "the fleet baseline version. Use the Agent Detail view to "
            "identify outdated agents and schedule upgrades through the "
            "SentinelOne console."
        ),
    ),
    ControlDefinition(
        id="SOC2-CC9.2",
        framework_id=FrameworkId.soc2,
        name="Prohibited Software Enforcement",
        description=(
            "Provides continuous monitoring that no applications classified "
            "as Prohibited persist on any managed endpoint. Unlike CC6.7 "
            "(point-in-time detection), this control enforces ongoing "
            "compliance as part of risk mitigation."
        ),
        category="CC9 — Risk Mitigation",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation=(
            "Remove prohibited software from affected endpoints "
            "immediately. Review recurring violations in the Anomalies "
            "view and investigate root causes. Update the taxonomy in "
            "the Taxonomy Editor if classification rules need refinement."
        ),
    ),
]
