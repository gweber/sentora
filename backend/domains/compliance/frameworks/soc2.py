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
            "Maintain a complete inventory of all software assets across "
            "managed endpoints.  Detect agents without application data or "
            "with stale sync data."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        remediation="Ensure all agents are synced and application data is current.",
    ),
    ControlDefinition(
        id="SOC2-CC6.1-SW",
        framework_id=FrameworkId.soc2,
        name="Software Asset Classification",
        description=(
            "All installed applications must be classified as Approved, "
            "Flagged, or Prohibited.  Unclassified applications represent "
            "unknown risk."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 90},
        remediation="Run classification and review unclassified applications.",
    ),
    ControlDefinition(
        id="SOC2-CC6.6",
        framework_id=FrameworkId.soc2,
        name="EDR Protection on All Endpoints",
        description=(
            "SentinelOne agent must be running and current on all managed "
            "endpoints to ensure continuous EDR protection."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_version,
        parameters={},
        remediation="Update SentinelOne agent to the current version.",
    ),
    ControlDefinition(
        id="SOC2-CC6.7",
        framework_id=FrameworkId.soc2,
        name="No Prohibited Software",
        description=(
            "No applications classified as Prohibited may be installed "
            "on managed endpoints."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation="Remove all prohibited applications from affected endpoints.",
    ),
    ControlDefinition(
        id="SOC2-CC6.8",
        framework_id=FrameworkId.soc2,
        name="Required Software Installed",
        description=(
            "All endpoints must have required security software installed "
            "(e.g. encryption tools, VPN clients)."
        ),
        category="CC6 — Access Controls",
        severity=ControlSeverity.high,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        remediation="Install required security software on all endpoints.",
    ),
    # ── CC7: System Operations — Monitoring ────────────────────────────────
    ControlDefinition(
        id="SOC2-CC7.1",
        framework_id=FrameworkId.soc2,
        name="Endpoint Software Change Monitoring",
        description=(
            "Detect changes in the software inventory between syncs.  "
            "New or removed applications indicate potential unauthorised "
            "modifications."
        ),
        category="CC7 — System Operations",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        remediation="Review new installations and verify they are authorised.",
    ),
    ControlDefinition(
        id="SOC2-CC7.2",
        framework_id=FrameworkId.soc2,
        name="Classification Anomaly Detection",
        description=(
            "The classification engine must achieve adequate coverage "
            "to detect anomalous software installations."
        ),
        category="CC7 — System Operations",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 80},
        remediation="Increase classification coverage by reviewing unprocessed agents.",
    ),
    ControlDefinition(
        id="SOC2-CC7.3",
        framework_id=FrameworkId.soc2,
        name="Unclassified Application Threshold",
        description=(
            "The percentage of unclassified applications per endpoint "
            "must remain below a configurable threshold."
        ),
        category="CC7 — System Operations",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        remediation="Classify unknown applications on flagged endpoints.",
    ),
    # ── CC8: Change Management ─────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC8.1",
        framework_id=FrameworkId.soc2,
        name="Software Change Tracking",
        description=(
            "All software inventory changes must be detectable via "
            "Sentora's delta detection mechanism."
        ),
        category="CC8 — Change Management",
        severity=ControlSeverity.medium,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 48},
        remediation="Enable regular sync schedules to ensure change visibility.",
    ),
    # ── A1: Availability ──────────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-A1.1",
        framework_id=FrameworkId.soc2,
        name="Endpoint Availability",
        description=(
            "Monitor endpoint availability by tracking agent check-in "
            "status.  Stale agents indicate potential availability issues."
        ),
        category="A1 — Availability",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 7},
        remediation="Investigate offline endpoints and restore connectivity.",
    ),
    ControlDefinition(
        id="SOC2-A1.2",
        framework_id=FrameworkId.soc2,
        name="Data Freshness",
        description=(
            "Software inventory data must be refreshed within the "
            "configured sync window."
        ),
        category="A1 — Availability",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 48},
        remediation="Ensure sync schedules are active and completing successfully.",
    ),
    # ── CC3: Risk Assessment ───────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC3.1",
        framework_id=FrameworkId.soc2,
        name="Asset Classification Coverage",
        description=(
            "All managed endpoints must have classification results "
            "to support risk assessment."
        ),
        category="CC3 — Risk Assessment",
        severity=ControlSeverity.medium,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 70},
        remediation="Run classification on unprocessed agents.",
    ),
    ControlDefinition(
        id="SOC2-CC3.2",
        framework_id=FrameworkId.soc2,
        name="Software Version Currency",
        description=(
            "Installed software should be reasonably current.  Outdated "
            "versions may contain known vulnerabilities."
        ),
        category="CC3 — Risk Assessment",
        severity=ControlSeverity.medium,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 20},
        remediation="Update outdated applications to current versions.",
    ),
    # ── CC9: Risk Mitigation ──────────────────────────────────────────────
    ControlDefinition(
        id="SOC2-CC9.1",
        framework_id=FrameworkId.soc2,
        name="Endpoint Protection Currency",
        description=(
            "SentinelOne agent versions must be maintained at or above "
            "the fleet baseline to ensure consistent protection."
        ),
        category="CC9 — Risk Mitigation",
        severity=ControlSeverity.high,
        check_type=CheckType.agent_version,
        parameters={},
        remediation="Update SentinelOne agent to the fleet baseline version.",
    ),
    ControlDefinition(
        id="SOC2-CC9.2",
        framework_id=FrameworkId.soc2,
        name="Prohibited Software Enforcement",
        description=(
            "Continuous enforcement that no prohibited software is "
            "present on any managed endpoint."
        ),
        category="CC9 — Risk Mitigation",
        severity=ControlSeverity.critical,
        check_type=CheckType.prohibited_app,
        parameters={},
        remediation="Remove prohibited software immediately.",
    ),
]
