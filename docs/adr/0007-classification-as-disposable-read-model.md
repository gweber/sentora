# ADR-0007: Classification as Disposable Read Model

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

A classification verdict for an agent is computed from two independently changing upstream datasets: the agent's current installed application list (updated on every S1 sync) and the fingerprint definitions (updated whenever a user edits markers or weights). Any change to either dataset can invalidate existing classification results. Building incremental update logic — detecting which agents are affected by a fingerprint edit, or which fingerprints are affected by a changed app list — requires bidirectional change tracking across two bounded contexts, introducing coupling and additional failure modes. Classification results have no independent business value beyond their current accuracy; there is no requirement to query historical verdicts.

## Decision

Classification results are a fully disposable read model. On any triggering event (sync completion, fingerprint save, user-requested reclassification), Sentora drops and recomputes the entire `classifications` collection. Results are stored in their own MongoDB collection so they can be served quickly without recomputing on every API request. The classification bounded context owns only its output collection; it reads from `agents` and `fingerprints` as inputs.

## Consequences

### Positive
- Classification results are always consistent with current agent and fingerprint data — no staleness from partial updates.
- The classification engine is a pure function over two input collections; it is trivially testable with fixture data.
- No change detection logic, no event subscriptions, no coupling between the sync and fingerprint bounded contexts.
- Dropping and recreating the collection is an atomic, idempotent operation — safe to retry on failure.
- Performance is bounded and predictable: 10,000 agents × 10 fingerprints × 20 markers ≈ 2 million comparisons, completing in seconds on commodity hardware.

### Negative
- During recomputation, the `classifications` collection may be momentarily empty or stale. The API must communicate this state to the UI.
- Full recomputation is wasteful if only one fingerprint changed out of many.
- As agent or fingerprint counts grow significantly, recomputation time will increase linearly.

### Risks
- If a recomputation is triggered while a sync is in progress, the classification will be computed against a partially updated `agents` collection. A sync-level lock should prevent concurrent recomputation triggers.
- Users who observe a verdict, then immediately edit a fingerprint and re-query, may see an intermediate stale result if the recomputation has not yet completed.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Incremental updates (recompute only affected agents/fingerprints) | Requires reliable change detection across two bounded contexts; increases coupling and introduces partial-consistency failure modes |
| Compute classification on every API request | Unacceptable latency for dashboards showing all agents; 10k agents × classification logic per request is prohibitive |
| Event-sourced projection rebuild | Adds event store infrastructure for a dataset that is cheaply recomputable from live source data (see ADR-0002) |
| Cache with invalidation keys | Cache invalidation correctness is harder to reason about than full recomputation; same consistency guarantees require tracking all invalidation paths |
