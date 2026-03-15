# ADR-0014: MongoDB Replica Set Support

**Status**: Accepted
**Date**: 2026-03-15
**Decision Makers**: Development Team

## Context

Sentora uses a standalone MongoDB instance for development and initial deployments.
Enterprise customers require high availability, automatic failover, and data durability
guarantees that a standalone instance cannot provide. Additionally, horizontal scaling
(multi-worker deployments) depends on MongoDB change streams, which require a replica set.

## Decision

Support MongoDB replica set connections with configurable read preference, write concern,
and connection pool settings. The configuration is entirely via environment variables and
is backward compatible — standalone deployments work without changes.

## Consequences

### Positive
- Automatic failover when the primary is unavailable
- `w: majority` write concern ensures data is replicated before acknowledgement
- Enables change streams for cross-worker pub/sub (required for horizontal scaling)
- Read scaling via `secondaryPreferred` or `nearest` read preferences
- Health endpoints report replica set status

### Negative
- Increased infrastructure complexity for operators deploying replica sets
- Motor client initialization is slightly more complex with additional kwargs
- `docker-compose.ha.yml` adds 3 MongoDB containers for local HA testing

### Neutral
- No schema changes required — all existing collections and indexes work on replica sets
- Distributed locks (`distributed_lock.py`) work identically on replica sets
- Default settings (`primary` read preference, `majority` write concern) are safe for both standalone and replica set
