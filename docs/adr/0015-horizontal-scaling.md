# ADR-0015: Horizontal Scaling (Multi-Worker Support)

**Status**: Accepted
**Date**: 2026-03-15
**Decision Makers**: Development Team

## Context

Sentora runs as a single uvicorn worker by default. The sync scheduler, fingerprint
proposal lock, and classification manager all rely on `asyncio.Lock`, which is per-process
and provides no cross-worker protection. To scale the backend horizontally (multiple
uvicorn workers behind a single port), we need coordination primitives that work across
OS processes.

The existing `distributed_lock.py` already provides cross-process mutual exclusion via
MongoDB. This ADR extends that foundation with leader election (so only one worker runs
the sync scheduler) and a pub/sub mechanism (so workers can broadcast events to each other).

## Decision

Introduce three new coordination primitives, all backed by MongoDB:

1. **Leader Election** (`utils/leader_election.py`) -- ensures exactly one worker runs
   the background sync scheduler at a time. Uses a `leader_election` MongoDB collection
   with TTL-based expiry and periodic heartbeats. If the leader crashes, another worker
   takes over after the TTL expires.

2. **Pub/Sub** (`utils/pubsub.py`) -- enables cross-worker message passing via a MongoDB
   capped collection. Subscribers use tailable cursors (with a polling fallback for
   standalone MongoDB). This allows events like "sync completed" or "config changed" to
   propagate to all workers.

3. **Enhanced Distributed Lock** -- the existing `distributed_lock.py` gains an `owner_id`
   field for ownership tracking and a `try_acquire_with_retry()` method with exponential
   backoff for transient contention.

The number of workers is controlled by the `WORKERS` environment variable (default: 1).
Multi-worker mode requires `ENABLE_DISTRIBUTED_LOCKS=true`.

## Consequences

### Positive
- Backend can scale horizontally by increasing `WORKERS` (up to 16)
- Sync scheduler runs on exactly one worker via leader election with automatic failover
- Cross-worker messaging enables future features (cache invalidation, real-time config reload)
- Fully backward compatible -- single-worker deployments work unchanged
- All coordination uses MongoDB (no additional infrastructure like Redis)

### Negative
- Leader election adds a small amount of MongoDB traffic (heartbeats every ~45s)
- Capped collection pub/sub has higher latency than dedicated message brokers (~500ms polling)
- Distributed locks add ~1-2ms overhead per acquisition compared to `asyncio.Lock`

### Neutral
- `WORKERS=1` remains the default; operators must explicitly opt in to multi-worker
- The `leader_election` and `_pubsub_messages` collections are created automatically
- Existing tests continue to pass since they run with a single worker
