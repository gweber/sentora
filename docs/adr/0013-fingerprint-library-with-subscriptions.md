# ADR-0013: Fingerprint Library with Subscription-Based Marker Distribution

**Status**: Accepted
**Date**: 2026-03-15
**Deciders**: Architecture team

## Context

Sentora's fingerprint definitions are per-group — each S1 group has its own set of markers. In practice, many groups share common software fingerprints (e.g., "Google Chrome", "Microsoft Office"). Operators were duplicating markers across groups manually. Additionally, public databases like the NIST CPE Dictionary and MITRE ATT&CK contain thousands of software definitions that could bootstrap fingerprint creation.

We needed a way to:
1. Share reusable fingerprint templates across groups.
2. Ingest software definitions from public sources automatically.
3. Keep group fingerprints in sync when shared templates are updated.

## Decision

Introduce a **Library** bounded context with three concepts:

- **LibraryEntry** — A versioned, reusable fingerprint template containing glob-pattern markers. Entries have a lifecycle (`draft` → `pending_review` → `published` → `deprecated`) and a source (`manual`, `nist_cpe`, `mitre`, `chocolatey`, `homebrew`, `community`).

- **LibrarySubscription** — Links a library entry to an S1 group. When subscribed, the entry's markers are copied into the group's fingerprint with `source="library"` and `added_by="library:{entry_id}"` provenance. A `synced_version` field tracks which entry version was last synced.

- **IngestionRun** — Tracks source adapter executions with entry created/updated/skipped counts and error logs.

### Key design choices

**Subscription model (chosen) vs. direct reference model (rejected).**
A direct reference model would have fingerprints point to library entries at scoring time. This was rejected because:
- It couples the classification engine to the library domain, violating bounded context isolation.
- It adds a lookup per fingerprint per agent during classification, degrading performance.
- Operators lose the ability to customize library-sourced markers per group.

The subscription model copies markers into group fingerprints at subscribe time. This preserves the existing classification engine (which only reads `fingerprints` documents), maintains domain isolation, and allows per-group marker customization after subscription.

**Version-based stale detection (chosen) vs. timestamp-based (rejected).**
Each library entry has a monotonically increasing `version` integer, bumped on every update. Subscriptions record the `synced_version` they last copied. Stale detection is a simple integer comparison: `entry.version > subscription.synced_version`. This is cheaper and more reliable than timestamp comparison across distributed systems.

**Provenance tracking via `added_by` field.**
Library-sourced markers carry `added_by="library:{entry_id}"`. On unsubscribe, all markers with matching provenance are removed cleanly. This avoids accidental deletion of manually-added markers that happen to share the same pattern.

**Source adapter pattern.**
Adapters follow an abstract `SourceAdapter` base class with a `fetch()` async iterator method. This allows:
- Streaming large datasets (NIST CPE has 1M+ entries) without loading everything into memory.
- Per-adapter rate limiting (NVD API: 6s delay without key, 0.6s with key).
- Consistent upsert logic via `upstream_id` uniqueness constraint.

**Ingestion manager as singleton with asyncio.Lock.**
Matches the established `SyncManager` pattern. Prevents concurrent ingestion runs that could produce duplicate entries.

## Consequences

**Positive:**
- Groups can bootstrap fingerprints from public databases in minutes instead of hours of manual work.
- Shared templates reduce duplication and inconsistency across groups.
- Version-based sync ensures groups stay up-to-date with template changes.
- Clean unsubscribe: provenance tracking enables precise marker removal.
- Adapter pattern is extensible — new sources (WinGet, community feeds) can be added without changing core logic.

**Negative:**
- Marker copies mean storage duplication (each subscribed group gets its own copy of the markers).
- Stale subscriptions require periodic sync (manual trigger or scheduled).
- CPE-to-glob pattern mapping is heuristic — some generated patterns may be too broad or too narrow.

**Risks:**
- Large-scale ingestion (100k+ NIST CPE entries) could slow down the library browse UI. Mitigated by status filtering (only `published` entries shown by default) and pagination.
- Adapter API changes could break ingestion. Mitigated by error tracking per run and graceful degradation (failed adapters don't affect others).
