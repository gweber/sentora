# ADR-0002: CQRS Without Event Sourcing

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

Classification results in Sentora are derived from two upstream datasets — synced agent/app data and user-defined fingerprints — that evolve independently. A classification verdict for an agent is not an immutable business fact; it is a computed projection that must always reflect the current state of both inputs. Full event sourcing would require storing every sync delta and fingerprint edit as events, then replaying them to reconstruct current state. This adds significant infrastructure complexity (event store, projection rebuilds, snapshot management) for a dataset that is cheaply recomputable from its two source collections at any time.

## Decision

Sentora implements CQRS with separate command and query paths but without an event store. Write operations (sync, fingerprint edits, taxonomy changes) mutate source collections directly. Classification results are maintained as a read-side projection in a dedicated `classifications` collection, recomputed on demand from the current state of `agents` and `fingerprints`.

## Consequences

### Positive
- Classification results are always consistent with current source data — no stale projection risk from missed events.
- Command handlers (sync, fingerprint CRUD) are simple write-through operations with no event publishing overhead.
- The query path (classification reads) can be optimised independently of the write path.
- Recomputation is deterministic and fully testable without an event log.
- Eliminates the need to version event schemas as the domain model evolves.

### Negative
- Classification results are not available immediately after a write until recomputation completes; there is a brief window of stale reads.
- No audit trail of how classifications changed over time — history is lost on each recomputation.
- If recomputation performance degrades (agent count grows significantly), incremental updates would require retrofitting change detection.

### Risks
- A recomputation triggered mid-sync could produce partially consistent results if not coordinated with the sync lock.
- Without an event log, debugging "why did this agent's verdict change?" requires comparing snapshots manually.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Full event sourcing | Adds event store infrastructure, projection rebuild tooling, and schema versioning with no benefit — classification history has no business value in v1 |
| Traditional CRUD (single model) | Blurs command and query concerns; makes it harder to optimise reads independently and harder to test classification logic in isolation |
| Incremental projection updates | Requires reliable change detection on both `agents` and `fingerprints` collections; increases coupling between bounded contexts and adds failure modes |
| Kafka / message broker | Introduces distributed systems complexity inappropriate for a single-process tool that runs inside a corporate network |
