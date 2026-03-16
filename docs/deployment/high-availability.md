# High-Availability MongoDB Deployment

This guide covers deploying Sentora with a MongoDB replica set for production-grade availability.

## Why Replica Sets?

- **Automatic failover**: if the primary node goes down, a secondary is elected within seconds
- **Read scaling**: route read queries to secondaries to reduce primary load
- **Data durability**: `w: majority` ensures writes are acknowledged by multiple nodes
- **Required for**: change streams (used by horizontal scaling pub/sub), multi-worker deployments

## Quick Start (Docker Compose)

```bash
# Start 3-node replica set + backend
docker compose -f docker-compose.yml -f docker-compose.ha.yml up -d

# Wait ~15s for replica set initialization, then verify
docker compose -f docker-compose.yml -f docker-compose.ha.yml logs mongo-rs-init

# Verify replica set status via API (requires admin auth)
curl -H "Authorization: Bearer <admin-token>" http://localhost:5002/health/replica
```

## Configuration

Add these to your `.env` file (all optional — defaults are production-safe):

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | Use `mongodb://host1,host2,host3/?replicaSet=rs0` for replica sets |
| `MONGO_READ_PREFERENCE` | `primary` | `primary`, `primaryPreferred`, `secondaryPreferred`, `secondary`, `nearest` |
| `MONGO_WRITE_CONCERN_W` | `majority` | `majority` (recommended) or a number |
| `MONGO_WRITE_CONCERN_J` | `true` | Journal acknowledgement for writes |
| `MONGO_MAX_POOL_SIZE` | `100` | Max connections in the pool |
| `MONGO_MIN_POOL_SIZE` | `0` | Min connections kept alive |
| `MONGO_MAX_IDLE_TIME_MS` | `30000` | Idle connection timeout (ms) |

### Read Preference Guide

| Preference | Use Case |
|-----------|----------|
| `primary` | Default. All reads go to primary. Strongest consistency |
| `primaryPreferred` | Reads from primary, falls back to secondary during failover |
| `secondaryPreferred` | Offloads reads to secondaries. Best for read-heavy workloads |
| `nearest` | Lowest latency. Good for geographically distributed deployments |

## Health Monitoring

### Endpoints

- `GET /health/ready` — Returns `ready`, `degraded` (if replica members are unhealthy), or `not_ready` (503)
- `GET /health/replica` — Full replica set status (admin-only, returns 404 if standalone)

### Example Response (`/health/ready`)

```json
{
  "status": "ready",
  "replica_set": "rs0",
  "members": 3
}
```

## Production Deployment

For production, deploy MongoDB outside of Docker Compose (e.g., MongoDB Atlas, self-managed VMs):

1. Set up a 3-node replica set per [MongoDB documentation](https://www.mongodb.com/docs/manual/tutorial/deploy-replica-set/)
2. Enable authentication and TLS
3. Update `MONGO_URI`:
   ```
   MONGO_URI=mongodb://user:pass@host1:27017,host2:27017,host3:27017/sentora?replicaSet=rs0&authSource=admin&tls=true
   ```
4. Set `MONGO_WRITE_CONCERN_W=majority` and `MONGO_WRITE_CONCERN_J=true`

## Failover Behavior

- Motor (the async MongoDB driver) automatically retries operations during failover
- The `serverSelectionTimeoutMS=3000` setting means the app waits up to 3 seconds for a new primary
- Distributed locks (`distributed_lock.py`) work correctly with replica sets — all writes target the primary
- The `/health/ready` endpoint reports `degraded` if any member is unhealthy

## Migrating from Standalone

1. Convert standalone MongoDB to a single-member replica set:
   ```bash
   mongosh --eval 'rs.initiate({_id: "rs0", members: [{_id: 0, host: "localhost:27017"}]})'
   ```
2. Add secondaries:
   ```bash
   mongosh --eval 'rs.add("secondary1:27017"); rs.add("secondary2:27017")'
   ```
3. Update `MONGO_URI` to include `?replicaSet=rs0`
4. Restart the backend
