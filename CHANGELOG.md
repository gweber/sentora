# Changelog

All notable changes to Sentora are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- **Canonical data model** — Source-agnostic collections (`agents`, `installed_apps`, `groups`, `sites`, `source_tags`, `sync_runs`) replace all `s1_`-prefixed collections. Every document carries `source` and `source_id` fields for multi-EDR support. Deterministic UUID `_id` (uuid5) replaces MongoDB ObjectId for portable, deduplicated document identity.
- **Source Adapter architecture** — Abstract `SourceAdapter` base class and registry pattern enable pluggable EDR integrations. SentinelOne is the first registered adapter. Adding CrowdStrike, Defender, or CSV import requires only implementing the adapter interface — zero changes to compliance, enforcement, classification, dashboard, or export.
- **Normalised field names** — `agent_status` (online/offline/degraded) replaces `network_status` (connected/disconnected); `source_id` replaces `s1_agent_id`/`s1_group_id`/`s1_site_id`/`s1_tag_id`; `source_updated_at`/`source_created_at` replace `s1_updated_at`/`s1_created_at`.
- **Collection name constants** — All MongoDB collection names defined in `domains/sources/collections.py` as the single source of truth. No hardcoded collection strings in domain code.
- Frontend types and labels updated to canonical field names; SentinelOne-specific labels replaced with generic equivalents.

### Added

- **CrowdStrike Falcon integration** — Second EDR source adapter using FalconPy SDK
  - Scroll-based host sync (`QueryDevicesByFilterScroll` + `GetDeviceDetailsV2`)
  - Application inventory via Falcon Discover API (cursor-based pagination)
  - Host group resolution and caching
  - Full sync, incremental refresh (via `modified_timestamp` FQL filter), and resume-after-interruption
  - CrowdStrike-specific phase runners (`cs_groups`, `cs_agents`, `cs_apps`) integrated into SyncManager
  - Connection test with scope detection (Hosts, Discover, Host Groups)
  - Rate-limit-aware retry with exponential backoff
  - Frontend tabbed Integrations view (SentinelOne + CrowdStrike tabs)
  - New environment variables: `CS_CLIENT_ID`, `CS_CLIENT_SECRET`, `CS_BASE_URL`, `CS_MEMBER_CID`, `CS_SYNC_APPS`
- ISO/IEC 27001:2022 compliance framework with 16 controls across Annex A sections A.5 and A.8
  - 4 Organizational Controls (A.5): asset inventory, acceptable use, information transfer
  - 12 Technological Controls (A.8): endpoint devices, malware protection, vulnerability management, configuration management, monitoring, software installation, change management
  - Statement of Applicability (SoA) support: `disable_reason` field on control configuration for documenting exclusion justifications (available for all frameworks)
  - Dashboard now renders per-framework disclaimers on score cards
- NIST CSF 2.0 compliance framework with 15 controls (Identify, Protect, Detect functions)
- NIS2 (EU Directive 2022/2555) compliance framework with 13 controls (Article 21 measures a, d, e, h, i)
- CIS Controls v8 compliance framework with 14 safeguards (Controls 1, 2, 7, 10 with Implementation Group annotations)
  - Brings total to 142 controls across 9 compliance frameworks
- End-of-Life (EOL) software detection using endoflife.date lifecycle data
  - New `eol_software_check` compliance check type (11th check type)
  - EOL controls added to all 5 compliance frameworks (DORA, SOC 2, PCI DSS, HIPAA, BSI)
  - Two-layer matching: CPE-based (high confidence) + fuzzy name matching (review required)
  - endoflife.date library source with sync, product browser, and match review UI
  - Auto-matching runs after S1 sync and EOL sync
- CPE-enriched software inventory export API (`GET /api/v1/export/software-inventory`)
  - JSON and CSV formats with pagination and caching
  - Filterable by groups, tags, and classification status
  - Enriched with NIST CPE identifiers and EOL lifecycle data

### Fixed

- **classification_coverage scope bug**: Scope filter (tags/groups) was applied directly to `classification_results` collection which lacks those fields. Now resolves scoped agent IDs first via the `agents` collection, then counts matching classification results by `agent_id`. Affected all scoped classification_coverage controls (HIPAA-308a1, HIPAA-CLASS-COV, PCI-6.3.1, etc.)
- **custom_app_presence empty pattern**: Controls with unconfigured `app_pattern` (HIPAA-308a5, HIPAA-312e1, BSI-SYS.2.1.A4) returned `error` status instead of `not_applicable`. Now returns `not_applicable` with a clear configuration message, consistent with `required_app` behavior.
- Improved control descriptions and remediations across all 5 frameworks for clarity and actionability (specific UI navigation references added)

### Improved

- **Compliance engine check-result caching**: Controls sharing the same check type, parameters, and scope are now executed once with results remapped to all matching controls. Reduces ~84 MongoDB queries to ~25 unique queries in a full 5-framework compliance run.
- `docs/COMPLIANCE_HANDBOOK.md` — Complete operator handbook (1,858 lines) covering all frameworks, controls, check types, configuration guide, troubleshooting, audit evidence, and glossary
- `scripts/generate_compliance_handbook.py` — Idempotent handbook auto-generation from framework definitions + hand-written content sections
- `docs/compliance_controls_inventory.csv` — Machine-readable inventory of all 84 controls
- ADR-0025: Compliance Controls E2E Audit documenting all findings and decisions

### Changed

- DORA-8.7-01 (Legacy ICT System Assessment) now uses `eol_software_check` instead of `app_version_check` for more precise EOL detection

- DORA (EU 2022/2554) compliance framework with 20 controls across 5 categories
  - ICT Asset Identification (Art. 8): 6 controls
  - ICT Protection & Prevention (Art. 9): 7 controls
  - ICT Anomaly Detection (Art. 10): 2 controls
  - ICT Business Continuity (Art. 11): 2 controls
  - ICT Third-Party Software Risk (Art. 28): 3 controls

## [1.3.0] — 2026-03-15

### Added

- Initial public release
