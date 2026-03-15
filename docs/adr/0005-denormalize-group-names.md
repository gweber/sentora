# ADR-0005: Denormalize Group Names

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

MongoDB does not support joins. Agent documents and Fingerprint documents each reference a SentinelOne group by its `group_id` (an opaque UUID assigned by S1). Displaying the human-readable group name in the Sentora UI — on agent lists, classification dashboards, and fingerprint management views — would require either a separate lookup against a `groups` collection on every render or a client-side cache that must be explicitly invalidated. Group names in SentinelOne are administrator-controlled labels that change infrequently; the cost of a brief staleness window is low.

## Decision

Sentora stores `group_name` alongside `group_id` directly on both `Agent` and `Fingerprint` documents. The sync process (bounded context: sync) refreshes `group_name` on every pull from the S1 API, so names are updated at sync frequency. The `group_id` remains the stable identifier used for filtering and aggregation; `group_name` is a display-only denormalized field.

## Consequences

### Positive
- Group name is available in any document query without an additional lookup or pipeline stage.
- Fingerprint lists and agent dashboards render in a single collection read.
- No `groups` collection to maintain, index, or keep consistent.
- Aligns with MongoDB document modelling best practices for read-heavy, low-cardinality reference data.

### Negative
- If a group is renamed in SentinelOne between syncs, agents and fingerprints will display the old name until the next sync completes.
- `group_name` is duplicated across potentially thousands of `Agent` documents — a minor storage overhead.
- A bulk rename requires a coordinated update across multiple collections rather than a single `groups` document update.

### Risks
- A sync failure mid-run could leave some documents with the new group name and others with the old name, producing an inconsistent display until the sync completes successfully.
- If group names are used for anything beyond display (e.g., exported reports), stale names could cause confusion in external tooling.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Separate `groups` collection with lookup in aggregation pipelines | Every query that needs to display a group name becomes a `$lookup` pipeline stage; adds complexity and latency to all list endpoints |
| Client-side group name cache (in Vue store) | Cache invalidation is a separate concern; requires an additional API call on load and explicit refresh logic on sync completion |
| Store only `group_id`, resolve names lazily via API | N+1 requests for group name resolution on list views; unacceptable for large agent lists |
| Reference a normalised `groups` collection and accept pipeline joins | Contradicts MongoDB's document model; `$lookup` is supported but incurs a performance penalty not justified for display-only data |
