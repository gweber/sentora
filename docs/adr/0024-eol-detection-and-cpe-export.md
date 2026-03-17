# ADR-0024: EOL Software Detection and CPE-Enriched Export

## Status

Accepted

## Context

Sentora enriches software inventory with NIST CPE data but does not use it for
lifecycle or vulnerability assessments. Customers in regulated industries (DORA,
PCI DSS, SOC 2, HIPAA, BSI) need visibility into End-of-Life software. External
vulnerability management tools (Nucleus, Tenable, Qualys) need structured
software inventory data with CPE identifiers.

## Decision

1. **Add `eol_software_check` as the 11th compliance check type**, using
   endoflife.date as the lifecycle data source. This covers "is this software
   still supported?" — a compliance question, not a vulnerability question.

2. **Add a CPE-enriched software inventory export API** (JSON, CSV) that
   positions Sentora as a data source for external vulnerability management
   tools.

3. We explicitly **do NOT build** CVE lookups, CVSS scoring, or vulnerability
   prioritization. That remains the domain of dedicated vuln management tools.

### Technical decisions

- **Two-layer matching**: CPE-based (high confidence, static mapping table) and
  fuzzy name-based (lower confidence, requires human confirmation).
- **Fuzzy matches never auto-included in compliance results** — MSPs must
  confirm them via the Match Review UI.
- **DORA-8.7-01** control changed from `app_version_check` to
  `eol_software_check` — EOL detection is more precise for the "legacy ICT
  system" requirement.
- **EOL matching runs in the post-sync chain** — after `rebuild_app_summaries`
  but before compliance checks. Match results are persisted on app_summaries.
- **Export uses caching** with 1-hour TTL in an `export_cache` collection.

## Consequences

- New `domains/eol/` module with sync service, matching engine, and repository
- New `domains/export/` module with JSON and CSV export endpoints
- 11th check type registered in compliance engine
- EOL controls added to all 5 compliance frameworks (6 new controls total)
- DORA-8.7-01 control changes from `app_version_check` to `eol_software_check`
- endoflife.date appears as a new source in the Library Sources UI
- New `eol_products` and `export_cache` MongoDB collections
- Post-S1-sync chain now includes EOL matching step
