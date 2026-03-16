# Scaling Guide

Performance tuning for Sentora deployments with 10,000+ agents.

---

## Overview

The default configuration is tuned for development and small-to-medium environments (up to ~2,000 agents). For large environments, several configuration areas need explicit attention: MongoDB indexing, S1 API rate limiting, sync batching strategy, and container resource limits.

---

## Environment Size Reference

| Tier | Agent Count | Estimated App Records | Sync Duration | Notes |
|---|---|---|---|---|
| Small | < 500 | < 100k | 1–3 min | Default config suitable |
| Medium | 500–2,000 | 100k–500k | 3–10 min | Default config suitable |
| Large | 2,000–10,000 | 500k–3M | 10–45 min | Apply tuning from this guide |
| Enterprise | 10,000–50,000 | 3M–15M | 1–4 hours | Full tuning + replica set required |
| Very Large | 50,000+ | 15M+ | 4+ hours | Contact maintainers for guidance |

---

## MongoDB Indexing

Sentora performance is heavily index-dependent. Missing indexes cause full collection scans that are orders of magnitude slower at scale.

### Required Indexes

The following indexes must exist. They are created automatically on first startup, but verify them if you are running a custom or restored MongoDB instance.

```javascript
// agents collection
db.agents.createIndex({ "s1_agent_id": 1 }, { unique: true })
db.agents.createIndex({ "group_id": 1 })
db.agents.createIndex({ "verdict": 1 })
db.agents.createIndex({ "last_seen": -1 })
db.agents.createIndex({ "group_id": 1, "verdict": 1 })

// applications collection
db.applications.createIndex({ "agent_id": 1 })
db.applications.createIndex({ "name": 1 })
db.applications.createIndex({ "agent_id": 1, "name": 1 }, { unique: true })

// fingerprints collection
db.fingerprints.createIndex({ "group_id": 1 }, { unique: true })

// taxonomy_entries collection
db.taxonomy_entries.createIndex({ "patterns": 1 })
db.taxonomy_entries.createIndex({ "is_universal": 1 })
db.taxonomy_entries.createIndex({ "category": 1 })

// sync_jobs collection
db.sync_jobs.createIndex({ "started_at": -1 })
db.sync_jobs.createIndex({ "status": 1, "started_at": -1 })
```

### Verify Indexes Exist

```bash
docker compose exec mongo mongosh sentora --eval "
  ['agents', 'applications', 'fingerprints', 'taxonomy_entries', 'sync_jobs']
    .forEach(col => {
      print('\\n=== ' + col + ' ===');
      db[col].getIndexes().forEach(idx => print(JSON.stringify(idx.key)));
    })
"
```

### Index Rebuild (if needed)

If you suspect indexes are missing or corrupt:

```bash
docker compose exec mongo mongosh sentora --eval "
  db.applications.reIndex()
  db.agents.reIndex()
"
```

For large `applications` collections (millions of documents), this can take several minutes. The database remains online during the reindex.

---

## S1 API Rate Limiting

The SentinelOne API enforces rate limits. Exceeding these limits causes requests to return HTTP 429 (Too Many Requests), which stalls sync.

### Configuration

Set the following in `.env`:

```dotenv
# Requests per minute to the S1 API (default: 100)
# SentinelOne's standard limit is typically 200–300 RPM depending on your tier
RATE_LIMIT_PER_MINUTE=100

# Page size for agent/application list endpoints (default: 200, max: 1000)
S1_PAGE_SIZE=500

# Maximum retry attempts on 429 or 5xx responses (default: 5)
S1_MAX_RETRIES=5

# Initial backoff in seconds for exponential retry (default: 2)
S1_RETRY_BACKOFF_SECONDS=2
```

### Retry Strategy

Sentora uses exponential backoff with jitter for retried requests:

```
wait = backoff_seconds * (2 ^ attempt) + random(0, 1)
```

Attempts and wait times with `S1_RETRY_BACKOFF_SECONDS=2`:

| Attempt | Wait (approx.) |
|---|---|
| 1 | 4 seconds |
| 2 | 8 seconds |
| 3 | 16 seconds |
| 4 | 32 seconds |
| 5 | 64 seconds |

If all retries are exhausted, the sync job is marked as failed with the affected page noted in the error log. The next sync can be triggered manually.

### Finding Your S1 Rate Limit

Check your SentinelOne contract or contact your S1 account manager. As a conservative starting point, set `RATE_LIMIT_PER_MINUTE=80` to stay well under standard limits.

---

## Sync Performance

### Batching Strategy

Application data is fetched per-agent in pages. The sync pipeline uses a bounded concurrency pool to parallelize fetches:

```dotenv
# Number of concurrent agent application fetches (default: 5)
# Increase carefully — each concurrent fetch counts toward the rate limit
SYNC_CONCURRENCY=5
```

At `SYNC_CONCURRENCY=5` and `S1_PAGE_SIZE=500`, the effective throughput is approximately:

```
throughput = (RATE_LIMIT_PER_MINUTE / pages_per_agent) * SYNC_CONCURRENCY
```

For most agents, 1–4 pages of applications is typical. With 2 pages per agent average:

```
throughput = (100 / 2) * 5 = 250 agents/minute
```

### Estimated Sync Duration by Environment Size

| Agent Count | Avg Pages/Agent | SYNC_CONCURRENCY | Approx Duration |
|---|---|---|---|
| 500 | 2 | 5 | ~2 min |
| 2,000 | 2 | 5 | ~8 min |
| 5,000 | 2 | 10 | ~10 min |
| 10,000 | 3 | 10 | ~30 min |
| 25,000 | 3 | 15 | ~60 min |
| 50,000 | 4 | 20 | ~3 hours |

These are estimates — actual times depend on S1 API response latency and your rate limit tier.

### Scheduling Syncs

For large environments, schedule syncs during off-peak hours. In `.env`:

```dotenv
# Cron expression for automatic sync (default: disabled)
# Example: 2:00 AM every night
SYNC_SCHEDULE=0 2 * * *
```

---

## Classification Performance

### Recomputation Cost

Classification runs against all agents whenever any of the following change:

- A fingerprint is saved or updated.
- A taxonomy entry is added, updated, or deleted.
- A manual classification trigger is issued.

For environments with 50,000+ agents and dozens of fingerprints, a full recomputation can take 30–120 seconds. During this window, the Dashboard shows a "Classifying..." banner and verdict counts may be stale.

### Incremental Classification

By default, Sentora uses incremental classification: after a sync, only agents whose application lists changed since the last sync are reclassified. This is significantly faster than full recomputation.

```dotenv
# Enable incremental classification (default: true)
CLASSIFICATION_INCREMENTAL=true
```

Disable incremental mode only if you need to force a full reclassification (e.g., after changing threshold configuration):

```bash
curl -X POST http://localhost:5002/api/v1/classification/recompute \
  -H "X-API-Key: your_api_key" \
  -d '{"full": true}'
```

### When Classification Triggers Automatically vs. Manually

| Event | Automatic? | Notes |
|---|---|---|
| Sync completes | Yes | Incremental by default |
| Fingerprint saved | Yes | Affects only that group |
| Taxonomy entry added/updated | Yes | Full reclassification required |
| Threshold config changed | No | Must trigger manually via API |
| First-time setup | No | Must trigger manually or wait for first sync |

---

## MongoDB Resource Recommendations

### Memory (RAM)

MongoDB performs best when its working set fits in RAM. The "working set" for Sentora is primarily the `applications` collection.

| Agent Count | Estimated applications Collection Size | Recommended RAM |
|---|---|---|
| < 2,000 | < 500 MB | 2 GB |
| 2,000–10,000 | 500 MB – 3 GB | 4–8 GB |
| 10,000–50,000 | 3–15 GB | 16–32 GB |
| 50,000+ | 15+ GB | 64 GB+ |

MongoDB uses the WiredTiger storage engine's cache, which defaults to 50% of available RAM minus 1 GB. Set it explicitly:

```yaml
# In docker-compose.yml
services:
  mongo:
    command: --wiredTigerCacheSizeGB 4
```

### Storage

MongoDB with WiredTiger compresses data by default (snappy). Effective storage is typically 40–60% of raw data size.

Provision at least:
- 3× the estimated uncompressed data size for MongoDB data directory.
- A separate volume for MongoDB data (not the OS disk) to avoid I/O contention.

### Connection Pool

The backend connects to MongoDB via a connection pool. Default pool size is 10 connections. For high-concurrency workloads (many simultaneous API requests or parallel classification), increase this:

```dotenv
MONGO_MAX_POOL_SIZE=50
```

---

## Production Deployment Recommendations

### Docker Compose Resource Limits

Apply resource limits in `docker-compose.yml` to prevent any single service from consuming all host resources:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M

  frontend:
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M

  mongo:
    deploy:
      resources:
        limits:
          cpus: "4.0"
          memory: 8G
        reservations:
          cpus: "1.0"
          memory: 2G
    command: --wiredTigerCacheSizeGB 4
```

### MongoDB Replica Set

For production environments, run MongoDB as a replica set rather than a standalone instance. A replica set provides:

- **Automatic failover** if the primary node goes down.
- **Read scaling** — route read-heavy classification queries to secondaries.
- **Point-in-time recovery** via oplog.

A minimal three-member replica set for Docker Compose:

```yaml
services:
  mongo-primary:
    image: mongo:7
    command: mongod --replSet rs0 --bind_ip_all
    volumes:
      - mongo-primary-data:/data/db

  mongo-secondary-1:
    image: mongo:7
    command: mongod --replSet rs0 --bind_ip_all
    volumes:
      - mongo-secondary-1-data:/data/db

  mongo-secondary-2:
    image: mongo:7
    command: mongod --replSet rs0 --bind_ip_all
    volumes:
      - mongo-secondary-2-data:/data/db
```

Initiate the replica set on first boot:

```bash
docker compose exec mongo-primary mongosh --eval "
  rs.initiate({
    _id: 'rs0',
    members: [
      { _id: 0, host: 'mongo-primary:27017', priority: 2 },
      { _id: 1, host: 'mongo-secondary-1:27017', priority: 1 },
      { _id: 2, host: 'mongo-secondary-2:27017', priority: 1 }
    ]
  })
"
```

Update `MONGO_URI` in `.env` to include all members:

```dotenv
MONGO_URI=mongodb://mongo-primary:27017,mongo-secondary-1:27017,mongo-secondary-2:27017/sentora?replicaSet=rs0
```

### Monitoring

For production deployments, expose MongoDB metrics to your monitoring stack:

- Use `mongo-express` or MongoDB Atlas for visual monitoring.
- Export MongoDB metrics via `mongodb_exporter` to Prometheus.
- Alert on: replication lag > 30 seconds, available disk < 20%, connection pool saturation > 80%.

Sentora backend exposes a `/metrics` endpoint (Prometheus format) at `http://localhost:5002/metrics` when `ENABLE_METRICS=true` is set in `.env`.
