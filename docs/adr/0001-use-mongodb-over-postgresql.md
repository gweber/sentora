# ADR-0001: Use MongoDB over PostgreSQL

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

The SentinelOne API returns agent and application data as deeply nested JSON, including a variable-length list of installed applications per agent. Agents can have hundreds of installed apps, and each app carries publisher, version, and platform metadata. There are no cross-bounded-context joins required: sync, fingerprint, classification, and taxonomy each operate on their own data. Storing this data in a relational model would require either wide JSONB columns (negating the relational benefit) or a normalised `installed_apps` table requiring expensive aggregation queries for every fingerprint comparison. The system must handle 10,000+ agents without prohibitive query complexity.

## Decision

Sentora uses MongoDB 7 as its primary datastore, accessed via the Motor async driver. Each agent is stored as a single document containing its full list of installed applications as an embedded array. Fingerprints, classification results, and taxonomy entries each have their own collection.

## Consequences

### Positive
- S1 API payloads map directly to MongoDB documents with no transformation overhead.
- Embedded app arrays allow per-agent installed-app queries with a single document read.
- Schema flexibility accommodates S1 API changes (new fields on apps, agents) without migrations.
- Motor's async interface integrates natively with FastAPI's async request handling.
- Horizontal scaling via sharding is available if agent counts grow into the millions.

### Negative
- No referential integrity enforcement — orphaned classification results must be managed in application code.
- Aggregation pipelines for cross-agent queries (e.g., "all agents with WinCC installed") are less readable than SQL.
- MongoDB transactions across collections carry a performance overhead compared to single-collection operations.
- Developers unfamiliar with document modelling may denormalize incorrectly.

### Risks
- Atlas or self-hosted MongoDB licensing changes could increase operational cost.
- Aggregation pipeline complexity could become a maintenance burden as reporting requirements grow.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| PostgreSQL with JSONB | JSONB columns for app arrays remove the relational benefit while adding ORM complexity; indexing nested JSONB requires manual expression indexes |
| PostgreSQL with normalised `installed_apps` table | Every fingerprint comparison becomes a multi-table join or subquery; 10k agents × 200 apps = 2M rows with significant query planner overhead |
| SQLite | Single-file database does not support concurrent async writes from Motor and does not scale beyond a single process for 10k+ agents |
| DynamoDB / Cosmos DB | Managed document stores with higher operational cost and vendor lock-in without meaningful capability advantage for this workload |
