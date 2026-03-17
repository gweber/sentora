# ADR-0023: DORA Framework Implementation

## Status

Accepted

## Context

DORA (EU Regulation 2022/2554) — the Digital Operational Resilience Act — became fully applicable on 17 January 2025 for EU financial entities. It mandates ICT risk management, third-party oversight, incident reporting, and resilience testing.

Sentora's compliance module already supports 4 frameworks (SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz) using a shared check engine with 10 check types. Financial sector MSP customers need DORA compliance visibility for their endpoint software management.

## Decision

Add DORA as the 5th compliance framework by creating a new framework definition file (`dora.py`) that reuses the existing check types and engine infrastructure.

**Key design choices:**

1. **No new check types** — All 20 DORA controls map to existing check types (prohibited_app, required_app, agent_version, agent_online, app_version, sync_freshness, classification_coverage, unclassified_threshold, delta_detection).

2. **No new engine logic** — The compliance engine picks up DORA controls through the existing framework registry, identical to how SOC 2 / PCI / HIPAA / BSI controls are processed.

3. **No new collections** — Results stored in `compliance_results`. Violations appear in the existing unified violations endpoint.

4. **3 configurable controls** — `DORA-8.4-01` (critical ICT assets), `DORA-9.2-01` (EDR), and `DORA-9.2-02` (encryption) require tenant-specific configuration. They use the existing `required_app` check type with `required_apps: []` default, which returns `not_applicable` until configured — the same pattern used by `SOC2-CC6.8`.

5. **5 DORA article categories** — Art. 8 (Identification), Art. 9 (Protection), Art. 10 (Detection), Art. 11 (Continuity), Art. 28 (Third-Party Risk).

6. **Frontend auto-discovery** — The frontend compliance dashboard dynamically loads frameworks from the API. No frontend hardcoding needed beyond a subtitle text update.

## Consequences

- DORA controls reuse existing check types → zero engine changes required
- 20 new controls bring the total from 61 to 81 across 5 frameworks
- 3 controls require tenant-specific configuration before producing meaningful results
- Financial sector MSPs can enable DORA compliance monitoring immediately
- The framework definition pattern is validated as extensible — adding a 6th framework would follow the same steps
- DORA scope is limited to endpoint software management; the disclaimer clearly communicates what DORA requirements are outside Sentora's scope
