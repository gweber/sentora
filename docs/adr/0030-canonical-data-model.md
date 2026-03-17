# ADR-0030: Canonical Data Model and Source Adapter Architecture

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Engineering
**Supersedes:** None

---

## Context

Sentora was built as a SentinelOne-specific compliance monitoring platform. All MongoDB
collections used `s1_` prefixes (`s1_agents`, `s1_installed_apps`, `s1_groups`, `s1_sites`,
`s1_tags`, `s1_sync_runs`), all field names were SentinelOne-specific (`s1_agent_id`,
`network_status` with `connected`/`disconnected` values), and the sync pipeline was
tightly coupled to the S1 API.

This created three problems:

1. **Vendor lock-in risk.** 100% of the data model was S1-specific. Adding a second EDR
   source (CrowdStrike, Defender, or CSV import) would have required touching every
   downstream consumer — compliance checks, enforcement engine, classification,
   dashboard, export, and frontend.

2. **Technical debt.** S1-specific field names leaked through every layer of the stack,
   from MongoDB indexes through Python domain code to TypeScript frontend types.

## Decision

Introduce a **source-agnostic canonical data model** with:

- **Canonical collections:** `agents`, `installed_apps`, `groups`, `sites`, `source_tags`,
  `sync_runs`, `sync_meta`, `sync_checkpoint` (replacing all `s1_`-prefixed collections).

- **Source tracking on every document:** `source` (string, e.g. `"sentinelone"`) and
  `source_id` (original ID in the source system) on every canonical document.

- **Deterministic UUID `_id`:** Documents use `uuid5(SENTORA_NS, "{source}:{source_id}")`
  as `_id` instead of MongoDB ObjectId. This enables natural deduplication via `_id`-based
  upserts and makes IDs portable across databases.

- **Normalised field names:** `agent_status` (online/offline/degraded) instead of
  `network_status` (connected/disconnected), `source_updated_at` instead of
  `s1_updated_at`, etc.

- **Source Adapter interface:** Abstract base class (`SourceAdapter`) and registry pattern
  (matching the compliance framework registry) for pluggable EDR integrations.

- **Collection name constants:** Single source of truth in
  `domains/sources/collections.py` — all modules import collection names from there.

- **Greenfield approach:** No migration scripts, no legacy collections kept as backup.
  Data is reloaded via full sync from the source.

## Consequences

### Positive

- CrowdStrike or Defender adapter becomes a ~2-week project: implement `SourceAdapter`,
  write a normalizer, register the adapter. Zero changes needed in compliance, enforcement,
  classification, dashboard, or export.

- CSV import becomes trivial (~3-5 days): parse CSV rows into canonical format, write to
  canonical collections.

- S1 vendor dependency drops from 100% of the codebase to a single adapter module
  (`domains/sources/sentinelone/` + `domains/sync/`).

- All downstream consumers (11 compliance checks, enforcement engine, classification,
  dashboard, export, fingerprint matching, tag management) are now source-agnostic.

### Negative

- One-time refactor touches ~60+ backend files and ~20+ frontend files.

- Full sync required after deployment to populate new collections (30-60 min).

- All existing tests must be updated to use canonical field names.

### Neutral

- `app_summaries` retained as a materialized read-model (CQRS query-side projection).
  Live aggregation over 1.5M `installed_apps` rows is too slow for the apps list page.

- `classification_results` retained as a separate collection. It has its own lifecycle
  (runs, acknowledgment, history) and is not a property of installed apps.

## Alternatives Considered

1. **Abstraction layer (repository) over old collections.** Rejected — adds indirection
   without removing the debt. The `s1_` prefixes would still exist in MongoDB,
   confusing future developers and making the codebase lie about its capabilities.

2. **Rename collections only, keep field names.** Rejected — `s1_agent_id` and
   `network_status` with `connected`/`disconnected` values are SentinelOne-specific.
   A CrowdStrike agent has an AID, not an `s1_agent_id`. Normalised field names
   (`source_id`, `agent_status`) are necessary for a truly source-agnostic model.
