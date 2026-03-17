#!/usr/bin/env python3
"""Generate the Sentora Compliance Handbook from framework definitions.

Reads all framework and check type definitions, merges with hand-written
content from ``docs/handbook_content/``, and outputs a complete operator
handbook to ``docs/COMPLIANCE_HANDBOOK.md``.

Idempotent: running twice produces identical output.  No timestamps,
no random ordering.

Usage:
    python scripts/generate_compliance_handbook.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

# Ensure backend is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_frameworks() -> list[dict[str, Any]]:
    """Load all framework definitions and their controls.

    Returns:
        List of framework dicts with keys: id, name, version,
        description, disclaimer, controls (list of control dicts).
    """
    frameworks = []
    for module_name in ["soc2", "pci_dss", "hipaa", "bsi", "dora"]:
        mod = importlib.import_module(f"domains.compliance.frameworks.{module_name}")
        fw = mod.FRAMEWORK
        controls = []
        for ctrl in mod.CONTROLS:
            controls.append(
                {
                    "id": ctrl.id,
                    "name": ctrl.name,
                    "description": ctrl.description,
                    "category": ctrl.category,
                    "severity": ctrl.severity.value,
                    "check_type": ctrl.check_type.value,
                    "parameters": dict(ctrl.parameters),
                    "scope_tags": list(ctrl.scope_tags),
                    "scope_groups": list(ctrl.scope_groups),
                    "remediation": ctrl.remediation,
                    "hipaa_type": ctrl.hipaa_type.value if ctrl.hipaa_type else None,
                    "bsi_level": ctrl.bsi_level.value if ctrl.bsi_level else None,
                    "requires_configuration": _requires_config(ctrl),
                }
            )
        frameworks.append(
            {
                "id": fw.id.value if hasattr(fw.id, "value") else fw.id,
                "name": fw.name,
                "version": fw.version,
                "description": fw.description,
                "disclaimer": fw.disclaimer,
                "controls": controls,
            }
        )
    return frameworks


def _requires_config(ctrl: Any) -> bool:
    """Determine if a control requires tenant configuration before it works.

    Args:
        ctrl: A ControlDefinition instance.

    Returns:
        True if the control needs configuration to produce real results.
    """
    check = ctrl.check_type.value
    params = ctrl.parameters
    if check == "required_app_check" and not params.get("required_apps"):
        return True
    if check == "custom_app_presence_check" and not params.get("app_pattern"):
        return True
    return False


def _load_check_types() -> list[dict[str, Any]]:
    """Load check type metadata from implementation modules.

    Returns:
        List of check type dicts with keys: id, module, description,
        parameters, scope_behavior.
    """
    check_types = [
        {
            "id": "prohibited_app_check",
            "name": "Prohibited Application Check",
            "module": "backend/domains/compliance/checks/prohibited_app.py",
            "description": (
                "Detects applications classified as Prohibited on managed endpoints. "
                "Uses the installed_apps collection filtered by risk_level='prohibited', "
                "cross-referenced with the scoped agent set."
            ),
            "parameters": "None required. Uses classification data from the taxonomy.",
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "No agents in scope have prohibited applications installed.",
            "fail_condition": "One or more agents have prohibited apps — each app/agent pair generates a violation.",
            "empty_scope": "Returns not_applicable with 'No agents in scope'.",
            "data_sources": "agents, installed_apps (risk_level field), classification_results",
        },
        {
            "id": "required_app_check",
            "name": "Required Application Check",
            "module": "backend/domains/compliance/checks/required_app.py",
            "description": (
                "Verifies that all scoped endpoints have specific applications installed. "
                "Uses case-insensitive substring matching against the agent's installed_app_names."
            ),
            "parameters": (
                "- `required_apps` (list[str], required): Application name patterns to check. "
                "Empty list returns not_applicable."
            ),
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "All agents in scope have every required application installed.",
            "fail_condition": "One or more agents are missing a required application.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents (installed_app_names field)",
        },
        {
            "id": "agent_online_check",
            "name": "Agent Online Check",
            "module": "backend/domains/compliance/checks/agent_online.py",
            "description": (
                "Identifies agents that have not checked in within a configurable number of days. "
                "Compares last_active timestamp against the configured threshold."
            ),
            "parameters": "- `max_offline_days` (int, default 7): Maximum days since last check-in.",
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "All agents in scope checked in within max_offline_days.",
            "fail_condition": "One or more agents have not checked in within the threshold.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents (last_active field)",
        },
        {
            "id": "agent_version_check",
            "name": "Agent Version Check",
            "module": "backend/domains/compliance/checks/agent_version.py",
            "description": (
                "Compares EDR agent versions against either a configured minimum version "
                "or the most common version in the fleet (auto-detected baseline)."
            ),
            "parameters": (
                "- `min_version` (str, optional): Explicit minimum version string. "
                "If absent, the most common version across scoped agents is used as the baseline."
            ),
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "All agents at or above the baseline version.",
            "fail_condition": "One or more agents running a version below the baseline.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents (agent_version field)",
        },
        {
            "id": "app_version_check",
            "name": "Application Version Check",
            "module": "backend/domains/compliance/checks/app_version.py",
            "description": (
                "Identifies endpoints running outdated application versions by comparing "
                "installed versions against the most common version per application (fleet standard)."
            ),
            "parameters": (
                "- `max_outdated_percent` (float, default 20): Percentage threshold. "
                "Below this, the check warns; above, it fails."
            ),
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "No endpoints have outdated application versions.",
            "fail_condition": "Outdated percentage exceeds max_outdated_percent threshold.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents, installed_apps (normalized_name, version fields)",
        },
        {
            "id": "sync_freshness_check",
            "name": "Sync Freshness Check",
            "module": "backend/domains/compliance/checks/sync_freshness.py",
            "description": (
                "Verifies that the most recent completed data sync is within the configured "
                "time window. This is a global check — it evaluates the last sync run, not "
                "per-agent freshness."
            ),
            "parameters": "- `max_hours_since_sync` (int, default 24): Maximum hours since last completed sync.",
            "scope_behavior": "Global check. Scope filter only affects agent count in evidence summary.",
            "pass_condition": "Last completed sync is within max_hours_since_sync.",
            "fail_condition": "No completed syncs, or last sync exceeds the time window.",
            "empty_scope": "Still evaluates (global check). Returns fail if no syncs exist.",
            "data_sources": "sync_runs (status, completed_at fields)",
        },
        {
            "id": "classification_coverage_check",
            "name": "Classification Coverage Check",
            "module": "backend/domains/compliance/checks/classification_coverage.py",
            "description": (
                "Verifies that a sufficient percentage of scoped agents have classification "
                "results. Agents without classification represent unknown risk."
            ),
            "parameters": (
                "- `min_classified_percent` (float, default 90): Minimum coverage percentage. "
                "Below 80% of threshold = fail; between 80%-100% of threshold = warning; above = pass."
            ),
            "scope_behavior": "Resolves scoped agent IDs via agents, then counts matching classification_results.",
            "pass_condition": "Classification coverage meets or exceeds min_classified_percent.",
            "fail_condition": "Coverage is below 80% of the threshold.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents, classification_results (agent_id field)",
        },
        {
            "id": "unclassified_threshold_check",
            "name": "Unclassified Threshold Check",
            "module": "backend/domains/compliance/checks/unclassified_threshold.py",
            "description": (
                "Monitors the percentage of unclassified applications per endpoint. "
                "Uses app_summaries to determine which applications have been classified."
            ),
            "parameters": (
                "- `max_unclassified_percent` (float, default 10): Maximum allowed percentage "
                "of unclassified apps per endpoint."
            ),
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "All endpoints have unclassified app percentage below threshold.",
            "fail_condition": "One or more endpoints exceed the unclassified threshold.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents (installed_app_names), app_summaries (normalized_name, category)",
        },
        {
            "id": "delta_detection_check",
            "name": "Delta Detection Check",
            "module": "backend/domains/compliance/checks/delta_detection.py",
            "description": (
                "Detects new application installations within a configurable lookback window. "
                "New apps are identified by last_synced_at timestamp on installed_apps."
            ),
            "parameters": "- `lookback_hours` (int, default 24): Window to check for new installations.",
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "No new applications detected in the lookback window.",
            "fail_condition": "N/A — this check returns warning (not fail) when changes are detected.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents, installed_apps (last_synced_at field)",
        },
        {
            "id": "custom_app_presence_check",
            "name": "Custom Application Presence Check",
            "module": "backend/domains/compliance/checks/custom_app_presence.py",
            "description": (
                "Verifies that a specific application (by glob-style pattern) is present or absent "
                "on scoped endpoints. Supports both must-exist and must-not-exist modes."
            ),
            "parameters": (
                "- `app_pattern` (str, required): Glob-style pattern (e.g. 'BitLocker*'). "
                "Empty pattern returns not_applicable.\n"
                "- `must_exist` (bool, default True): If True, app must be present; "
                "if False, app must be absent."
            ),
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "All endpoints match the presence/absence requirement.",
            "fail_condition": "One or more endpoints violate the presence/absence requirement.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents (installed_app_names field)",
        },
        {
            "id": "eol_software_check",
            "name": "End-of-Life Software Check",
            "module": "backend/domains/compliance/checks/eol_software.py",
            "description": (
                "Identifies applications that have reached End-of-Life status using "
                "pre-computed EOL match data from the endoflife.date lifecycle database. "
                "Only considers CPE and manual matches above the confidence threshold."
            ),
            "parameters": (
                "- `flag_security_only` (bool, default True): Also flag apps in security-only phase.\n"
                "- `min_match_confidence` (float, default 0.8): Minimum match confidence threshold.\n"
                "- `exclude_products` (list[str], optional): Product IDs to skip."
            ),
            "scope_behavior": "Respects scope_tags and scope_groups via agents filter.",
            "pass_condition": "No EOL software detected on scoped endpoints.",
            "fail_condition": "One or more scoped endpoints have EOL software installed.",
            "empty_scope": "Returns not_applicable.",
            "data_sources": "agents, installed_apps, app_summaries (eol_match field)",
        },
    ]
    return check_types


def _load_handbook_section(name: str) -> str:
    """Load a hand-written handbook section from docs/handbook_content/.

    Args:
        name: Section filename (without .md extension).

    Returns:
        File contents, or a placeholder comment if the file doesn't exist.
    """
    path = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "handbook_content"
        / f"{name}.md"
    )
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"<!-- TODO: Write {name} section in docs/handbook_content/{name}.md -->"


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def _severity_badge(severity: str) -> str:
    """Format a severity label for markdown.

    Args:
        severity: Severity level string.

    Returns:
        Formatted severity string.
    """
    icons = {
        "critical": "**CRITICAL**",
        "high": "**HIGH**",
        "medium": "MEDIUM",
        "low": "low",
    }
    return icons.get(severity, severity)


def _params_display(params: dict[str, Any]) -> str:
    """Format control parameters for display.

    Args:
        params: Parameters dictionary.

    Returns:
        Human-readable parameters string.
    """
    if not params:
        return "None"
    parts = []
    for k, v in sorted(params.items()):
        parts.append(f"`{k}`: `{v}`")
    return ", ".join(parts)


def _generate_framework_section(fw: dict[str, Any]) -> str:
    """Generate the handbook section for a single framework.

    Args:
        fw: Framework dict from _load_frameworks().

    Returns:
        Markdown string for the framework section.
    """
    lines: list[str] = []
    fw_name = fw["name"]
    fw_id = fw["id"]

    lines.append(f"### {fw_name}")
    lines.append("")
    lines.append(f"**Version:** {fw['version']}")
    lines.append("")
    lines.append(fw["description"])
    lines.append("")

    # Disclaimer
    lines.append("> **Disclaimer**")
    lines.append(f"> {fw['disclaimer']}")
    lines.append("")

    # Hand-written intro
    section_name = f"framework_{fw_id}"
    intro = _load_handbook_section(section_name)
    lines.append(intro)
    lines.append("")

    # Controls table
    lines.append("#### Controls")
    lines.append("")
    lines.append("| Control ID | Title | Check Type | Severity | Config Required |")
    lines.append("|---|---|---|---|---|")
    for ctrl in fw["controls"]:
        config = "Yes" if ctrl["requires_configuration"] else "No"
        lines.append(
            f"| `{ctrl['id']}` | {ctrl['name']} | "
            f"`{ctrl['check_type']}` | {_severity_badge(ctrl['severity'])} | {config} |"
        )
    lines.append("")

    # Detailed control descriptions
    lines.append("#### Control Details")
    lines.append("")

    # Group by category
    categories: dict[str, list[dict[str, Any]]] = {}
    for ctrl in fw["controls"]:
        categories.setdefault(ctrl["category"], []).append(ctrl)

    for category, ctrls in categories.items():
        lines.append(f"##### {category}")
        lines.append("")

        for ctrl in ctrls:
            lines.append(f"###### `{ctrl['id']}` — {ctrl['name']}")
            lines.append("")
            lines.append(f"**Severity:** {_severity_badge(ctrl['severity'])}")
            if ctrl.get("hipaa_type"):
                lines.append(f" | **HIPAA Type:** {ctrl['hipaa_type'].title()}")
            if ctrl.get("bsi_level"):
                level_map = {
                    "basis": "Basis (MUSS)",
                    "standard": "Standard (SOLLTE)",
                    "elevated": "Erhöht (SOLLTE)",
                }
                lines.append(
                    f" | **BSI Level:** {level_map.get(ctrl['bsi_level'], ctrl['bsi_level'])}"
                )
            lines.append("")

            lines.append(f"**What it checks:** {ctrl['description']}")
            lines.append("")
            lines.append(f"**Parameters:** {_params_display(ctrl['parameters'])}")
            if ctrl["scope_tags"]:
                lines.append(f"**Scope:** Tags: `{', '.join(ctrl['scope_tags'])}`")
            if ctrl["scope_groups"]:
                lines.append(f"**Scope:** Groups: `{', '.join(ctrl['scope_groups'])}`")
            lines.append("")

            if ctrl["requires_configuration"]:
                lines.append(
                    "> **Configuration required:** This control needs tenant-specific "
                    "configuration before it produces results. Until configured, it "
                    "returns `not_applicable`."
                )
                lines.append("")

            if ctrl["remediation"]:
                lines.append(f"**How to fix a failure:** {ctrl['remediation']}")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def _generate_check_type_section(check_types: list[dict[str, Any]]) -> str:
    """Generate the Check Type Reference section.

    Args:
        check_types: List of check type dicts from _load_check_types().

    Returns:
        Markdown string for the check type reference.
    """
    lines: list[str] = []
    lines.append("## Check Type Reference")
    lines.append("")

    for ct in check_types:
        lines.append(f"### `{ct['id']}` — {ct['name']}")
        lines.append("")
        lines.append(f"**Implementation:** `{ct['module']}`")
        lines.append("")
        lines.append(ct["description"])
        lines.append("")
        lines.append("**Parameters:**")
        lines.append("")
        for param_line in ct["parameters"].split("\n"):
            lines.append(param_line)
        lines.append("")
        lines.append(f"**Scope behavior:** {ct['scope_behavior']}")
        lines.append("")
        lines.append(f"**Pass:** {ct['pass_condition']}")
        lines.append("")
        lines.append(f"**Fail:** {ct['fail_condition']}")
        lines.append("")
        lines.append(f"**0 agents in scope:** {ct['empty_scope']}")
        lines.append("")
        lines.append(f"**Data sources:** `{ct['data_sources']}`")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_handbook() -> str:
    """Generate the complete compliance handbook markdown.

    Returns:
        The full handbook as a markdown string.
    """
    frameworks = _load_frameworks()
    check_types = _load_check_types()

    total_controls = sum(len(fw["controls"]) for fw in frameworks)
    config_required = sum(
        1 for fw in frameworks for c in fw["controls"] if c["requires_configuration"]
    )

    sections: list[str] = []

    # Title
    sections.append("# Sentora Compliance Handbook")
    sections.append("")
    sections.append(
        f"> Complete operator reference for Sentora's compliance module. "
        f"Covers {len(frameworks)} frameworks, {total_controls} controls, "
        f"and {len(check_types)} check types."
    )
    sections.append("")

    # How Compliance Works
    sections.append("## How Compliance Works in Sentora")
    sections.append("")
    sections.append(_load_handbook_section("how_compliance_works"))
    sections.append("")

    # Getting Started
    sections.append("## Getting Started")
    sections.append("")
    sections.append(_load_handbook_section("getting_started"))
    sections.append("")

    # Framework Reference
    sections.append("## Framework Reference")
    sections.append("")
    sections.append(
        f"Sentora monitors {total_controls} controls across "
        f"{len(frameworks)} compliance frameworks. "
        f"{config_required} controls require tenant-specific configuration "
        f"before they produce results."
    )
    sections.append("")

    for fw in frameworks:
        sections.append(_generate_framework_section(fw))

    # Check Type Reference
    sections.append(_generate_check_type_section(check_types))

    # Configuration Guide
    sections.append("## Configuration Guide")
    sections.append("")
    sections.append(_load_handbook_section("configuration_guide"))
    sections.append("")

    # Troubleshooting
    sections.append("## Troubleshooting")
    sections.append("")
    sections.append(_load_handbook_section("troubleshooting"))
    sections.append("")

    # Audit & Evidence
    sections.append("## Audit & Evidence")
    sections.append("")
    sections.append(_load_handbook_section("audit_evidence"))
    sections.append("")

    # Glossary
    sections.append("## Glossary")
    sections.append("")
    sections.append(_load_handbook_section("glossary"))
    sections.append("")

    return "\n".join(sections)


def main() -> None:
    """Generate the handbook and write to docs/COMPLIANCE_HANDBOOK.md."""
    output_path = (
        Path(__file__).resolve().parent.parent / "docs" / "COMPLIANCE_HANDBOOK.md"
    )
    content = generate_handbook()
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated {output_path} ({len(content):,} bytes)")


if __name__ == "__main__":
    main()
