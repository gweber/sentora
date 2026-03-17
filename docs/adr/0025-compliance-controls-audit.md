# ADR-0025: Compliance Controls E2E Audit

| Field    | Value                          |
|----------|--------------------------------|
| Status   | Accepted                       |
| Date     | 2026-03-16                     |
| Author   | Sentora Engineering            |

## Context

Sentora ships 84 compliance controls across 5 frameworks (SOC 2, PCI DSS 4.0, HIPAA, BSI IT-Grundschutz, DORA) using 11 check types. These controls were implemented based on framework specifications but had never been verified end-to-end against real data patterns. No operator documentation existed for MSP technicians to understand, configure, or troubleshoot the compliance module.

## Decision

Conducted a full E2E audit of all 84 controls across all 5 frameworks. The audit traced each control from definition through engine execution to API response, identified issues, and produced an operator handbook.

## Findings Summary

### Bugs Fixed

1. **classification_coverage scope bug (P1)**: The check applied `scope_filter` (designed for the `agents` collection with `tags`/`group_name` fields) directly to the `classification_results` collection, which has a different document structure. Scope-filtered compliance runs for HIPAA or PCI-scoped controls could return incorrect classification counts. Fixed by resolving scoped agent IDs first, then counting classification results by `agent_id`.

2. **custom_app_presence empty pattern (P2)**: Three controls (HIPAA-308a5, HIPAA-312e1, BSI-SYS.2.1.A4) ship with empty `app_pattern` and returned `error` status, which confused MSPs. Changed to return `not_applicable` with a clear configuration message, aligning with `required_app` behavior.

### Performance Optimization

3. **Engine check-result caching**: Many controls across different frameworks (and within the same framework) use identical check types with identical parameters and scope. Before the fix, the engine ran each query separately — e.g., `prohibited_app_check` with no scope ran 6 times (once per control across SOC2, BSI, DORA). After the fix, the engine computes a cache key from `(check_type, parameters, scope_filter)`, executes each unique query once, and remaps results to all matching controls. For a typical 5-framework deployment with all controls enabled, this reduces ~84 MongoDB queries to ~25 unique queries.

### Redundancy Analysis

Intra-framework duplicates identified (same check type, parameters, and scope within one framework):

| Framework | Duplicate Pair | Check Type |
|-----------|---------------|------------|
| SOC 2 | CC6.7 = CC9.2 | prohibited_app |
| SOC 2 | CC6.6 = CC9.1 | agent_version |
| BSI | SYS.2.1.A42 = SYS.2.1.A9 | prohibited_app |
| BSI | SYS.2.1.A6 = OPS.1.1.3.A15-EDR | agent_version |
| DORA | 9.3-01 = 28.1-02 | prohibited_app |
| DORA | 8.2-01 = 9.3-02 = 10.1-01 | delta_detection |
| DORA | 9.2-01 = 9.2-02 | required_app |

These duplicates are **intentional**: each control maps to a different requirement within its framework (different TSC criteria, different DORA articles, different BSI Bausteine). The engine caching ensures no performance penalty.

### Configuration Gaps

10 controls require tenant-specific configuration before they produce meaningful results:
- 7 `required_app` controls with empty `required_apps` lists → return `not_applicable`
- 3 `custom_app_presence` controls with empty `app_pattern` → now return `not_applicable`

All 10 are correctly documented in the operator handbook with configuration instructions.

### Documentation

- **Operator Handbook** (`docs/COMPLIANCE_HANDBOOK.md`): 1,858 lines covering all frameworks, controls, check types, configuration guide, troubleshooting, audit evidence guide, and glossary.
- **Handbook Generation Script** (`scripts/generate_compliance_handbook.py`): Auto-generates structured sections from framework definitions; merges with hand-written content from `docs/handbook_content/`.
- **Control Inventory** (`docs/compliance_controls_inventory.csv`): Machine-readable inventory of all 84 controls.

## Consequences

- Compliance module confidence level: **high** for all check types
- Classification coverage scope filtering is now correct for all scoped frameworks
- Engine caching reduces query count by ~70% with no behavioral change
- Handbook must be regenerated when controls are added: `python scripts/generate_compliance_handbook.py`
- No controls were removed; all intra-framework duplicates retained for compliance mapping fidelity

## Alternatives Considered

1. **Remove intra-framework duplicates**: Rejected. Each control maps to a distinct compliance requirement. Removing one would leave a gap in the framework mapping that auditors would question.

2. **Add `requires_configuration` field to ControlDefinition**: Considered but rejected as over-engineering. The check implementations already handle unconfigured state correctly (`not_applicable` or `error`→`not_applicable`). The handbook documents which controls need configuration.

3. **Per-agent sync freshness instead of global**: Considered for `sync_freshness_check`. Rejected because the check verifies that Sentora's data pipeline is running, not per-agent connectivity (that's `agent_online_check`'s job).
