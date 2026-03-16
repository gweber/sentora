# Business Continuity Plan

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-BC-001                                |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Operations & Security Team                 |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Purpose

This Business Continuity Plan (BCP) defines procedures for maintaining and restoring
Sentora operations during and after disruptions. It covers high availability
architecture, backup and restore procedures, disaster recovery, and recovery objectives.

---

## 2. Scope

This plan covers:

- Sentora backend API (FastAPI)
- Sentora frontend SPA (Vue 3)
- MongoDB 7 database
- SentinelOne API integration
- Supporting infrastructure (Docker, networking)

---

## 3. Recovery Objectives

### 3.1 Service Tiers

| Tier | Service | RPO | RTO | Priority |
|------|---------|-----|-----|----------|
| 1 | Dashboard and agent inventory (read) | 4 hours | 1 hour | Critical |
| 2 | Authentication and access control | 0 (no data loss) | 30 minutes | Critical |
| 3 | Fingerprint matching and classification | 4 hours | 2 hours | High |
| 4 | SentinelOne sync pipeline | 24 hours | 4 hours | Medium |
| 5 | Audit logging and metrics | 1 hour | 2 hours | Medium |
| 6 | Taxonomy management | 24 hours | 4 hours | Low |

### 3.2 Recovery Objective Definitions

| Objective | Definition | Target |
|-----------|-----------|--------|
| **RPO** (Recovery Point Objective) | Maximum acceptable data loss measured in time | See tier table above |
| **RTO** (Recovery Time Objective) | Maximum acceptable downtime | See tier table above |
| **MTPD** (Maximum Tolerable Period of Disruption) | Longest period the business can tolerate | 8 hours for Tier 1-2; 24 hours for Tier 3-6 |

---

## 4. High Availability Architecture

### 4.1 MongoDB Replica Set

Sentora supports MongoDB replica set deployment for database-level high availability.

**Reference:** `docs/adr/0014-mongodb-replica-set-support.md`

| Component | Configuration | Purpose |
|-----------|--------------|---------|
| Primary node | Read/write operations | Active database serving all queries |
| Secondary node(s) | Read replicas (optional read preference) | Automatic failover target |
| Arbiter (optional) | Vote-only member | Maintains odd voter count for election |

**Failover behavior:**

1. Primary node becomes unavailable (crash, network partition, or maintenance)
2. Secondary nodes detect primary absence via heartbeat (default: 10s interval)
3. Election occurs among eligible secondaries (typically < 12 seconds)
4. New primary elected and begins accepting writes
5. Application reconnects automatically via MongoDB driver (Motor 3.7.1)
6. `MONGODB_URL` connection string should include all replica set members

**Configuration in `docker-compose.yml`:**
- Replica set initialization supported
- Resource limits: 1 CPU, 1 GB RAM per MongoDB node
- Health checks configured for each node

### 4.2 Application-Level Resilience

| Feature | Implementation | Reference |
|---------|---------------|-----------|
| Health probes | `/health` (liveness), `/health/ready` (readiness pings MongoDB) | `backend/main.py` |
| Graceful degradation | Readiness probe returns 503 when MongoDB unreachable; load balancer removes instance | Health check endpoints |
| Checkpoint-based sync | Sync operations save progress; resume after failure without full re-sync | `backend/domains/sync/manager.py` |
| Rate limiting | Prevents overload during recovery; protects partially-restored service | Rate limiting middleware |
| Fail-fast on misconfiguration | Backend refuses to start without required config (S1_API_TOKEN) | Startup validation |

### 4.3 Container Resilience

| Feature | Configuration | Reference |
|---------|--------------|-----------|
| Restart policy | `restart: unless-stopped` in Docker Compose | `docker-compose.yml` |
| Resource limits | 1 CPU, 1 GB RAM per container | `docker-compose.yml` |
| Health checks | Docker-level health checks for automatic restart | `docker-compose.yml` |
| Non-root execution | `apprunner` user (uid 1001) limits blast radius | `Dockerfile.backend` |

---

## 5. Backup Strategy

### 5.1 Backup Types

| Backup Type | Method | Frequency | Retention | RPO Impact |
|-------------|--------|-----------|-----------|------------|
| Full database | `mongodump` (all collections) | Daily at 02:00 UTC | 30 days | 24 hours max |
| Incremental oplog | Continuous oplog capture (replica set) | Continuous | 72 hours | Minutes |
| Configuration | Environment variable export | Before each deployment | 90 days | N/A |
| Application code | Git repository | Per commit | Indefinite | N/A |

### 5.2 Backup Scope

| Collection | Backup Priority | Notes |
|-----------|----------------|-------|
| `users` | Critical | Auth data; password hashes, 2FA secrets |
| `agents` | High | Refreshable from SentinelOne, but sync takes time |
| `applications` | High | Refreshable from SentinelOne |
| `fingerprints` | High | Analyst work product; not easily recreated |
| `fingerprint_proposals` | Medium | Can be regenerated by re-running matcher |
| `classifications` | High | Rule-based; re-runnable but may differ |
| `classification_rules` | High | Analyst-defined rules |
| `taxonomy` | Medium | Seed data available; custom entries need backup |
| `software_library` | Medium | Reference data; seed available |
| `tags` | Medium | Tag rules and assignments |
| `audit_logs` | Medium | 90-day TTL; compliance evidence |
| `sync_state` | Low | Transient; re-created on next sync |
| `config` | Medium | Runtime settings |

### 5.3 Backup Procedures

#### 5.3.1 Full Database Backup

```bash
# Production backup (run from backup host)
mongodump \
  --uri="$MONGODB_URL" \
  --out="/backups/sentora/$(date +%Y%m%d_%H%M%S)" \
  --gzip \
  --oplog

# Verify backup integrity
mongorestore \
  --uri="mongodb://localhost:27017/sentora_verify" \
  --gzip \
  --drop \
  --dir="/backups/sentora/<backup_dir>" \
  --dryRun
```

#### 5.3.2 Backup Encryption

- Backups containing Confidential or Restricted data must be encrypted at rest
- Use AES-256 encryption with keys stored separately from backups
- Encryption keys rotated quarterly
- Backup encryption key documented (securely) for disaster recovery access

#### 5.3.3 Backup Verification

| Check | Frequency | Method |
|-------|-----------|--------|
| Backup completion | Daily (automated) | Verify backup file exists and size > 0 |
| Restore test | Monthly | Restore to test environment, verify data integrity |
| Full DR test | Quarterly | Complete restore and application validation |
| Backup encryption | Daily (automated) | Verify backup files are encrypted |

### 5.4 Backup Retention

| Type | Retention | Storage |
|------|-----------|---------|
| Daily full backups | 30 days | Encrypted storage, separate from primary |
| Weekly consolidation | 12 weeks | Encrypted archive storage |
| Monthly consolidation | 12 months | Encrypted archive storage, offsite |
| Pre-deployment snapshots | 7 days | Local encrypted storage |

---

## 6. Disaster Recovery Procedures

### 6.1 Scenario: Single Container Failure

**Impact:** Partial service degradation
**Recovery:** Automatic via Docker restart policy

| Step | Action | Time |
|------|--------|------|
| 1 | Docker detects unhealthy container via health check | ~30 seconds |
| 2 | Container automatically restarted | ~10 seconds |
| 3 | Application starts and passes readiness probe | ~15 seconds |
| 4 | Service resumes normal operation | Total: ~1 minute |

### 6.2 Scenario: MongoDB Primary Failure (Replica Set)

**Impact:** Brief write unavailability, reads may continue from secondaries
**Recovery:** Automatic via replica set election

| Step | Action | Time |
|------|--------|------|
| 1 | Secondaries detect primary absence | ~10 seconds |
| 2 | Election of new primary | ~12 seconds |
| 3 | Application reconnects to new primary | ~5 seconds |
| 4 | Readiness probe returns 200 | ~5 seconds |
| 5 | Normal operation resumes | Total: ~30 seconds |

### 6.3 Scenario: Complete MongoDB Loss

**Impact:** Full service outage
**Recovery:** Manual restore from backup

| Step | Action | Responsible | Time |
|------|--------|-------------|------|
| 1 | Detect outage via health probe (503) | Monitoring | ~1 minute |
| 2 | Assess scope; determine if restore needed | Operator | ~15 minutes |
| 3 | Provision new MongoDB instance(s) | Operator | ~15 minutes |
| 4 | Restore from most recent backup | Operator | ~30-60 minutes* |
| 5 | Apply oplog entries for point-in-time recovery | Operator | ~15 minutes |
| 6 | Update `MONGODB_URL` if endpoint changed | Operator | ~5 minutes |
| 7 | Restart application containers | Operator | ~2 minutes |
| 8 | Verify health probes pass | Operator | ~2 minutes |
| 9 | Trigger SentinelOne sync to recover latest data | Operator | ~30 minutes |
| 10 | Verify data integrity (audit log hash chain) | Operator | ~15 minutes |
| | **Total estimated recovery** | | **~2-3 hours** |

*Backup restore time depends on database size.

### 6.4 Scenario: Complete Infrastructure Loss

**Impact:** Total system unavailability
**Recovery:** Full rebuild from code and backups

| Step | Action | Responsible | Time |
|------|--------|-------------|------|
| 1 | Provision new infrastructure | Operator | ~30 minutes |
| 2 | Clone Git repository | Operator | ~5 minutes |
| 3 | Configure environment variables from backup | Operator | ~15 minutes |
| 4 | Build Docker images | CI/CD or manual | ~15 minutes |
| 5 | Deploy containers via `docker-compose up` | Operator | ~5 minutes |
| 6 | Restore MongoDB from offsite backup | Operator | ~60 minutes |
| 7 | Verify health probes | Operator | ~5 minutes |
| 8 | Rotate all secrets (JWT, API tokens) | Security | ~15 minutes |
| 9 | Trigger full SentinelOne sync | Operator | ~60 minutes |
| 10 | Verify data integrity and service functionality | QA | ~30 minutes |
| | **Total estimated recovery** | | **~4-5 hours** |

### 6.5 Scenario: SentinelOne API Unavailability

**Impact:** Sync pipeline fails; existing data remains available
**Recovery:** Graceful degradation; automatic retry

| Step | Action | Time |
|------|--------|------|
| 1 | Sync manager detects S1 API failure | Immediate |
| 2 | Sync enters checkpoint state; WebSocket notifies clients | ~1 second |
| 3 | All read operations continue normally (cached data) | No downtime |
| 4 | Dashboard shows "Last sync" timestamp as stale indicator | Immediate |
| 5 | When S1 API recovers, next sync resumes from checkpoint | Automatic |

---

## 7. Communication During Disruption

### 7.1 Notification Matrix

| Severity | Who to Notify | When | Channel |
|----------|--------------|------|---------|
| Tier 1-2 service down | All stakeholders, users | Within 15 minutes | Email + status page |
| Tier 3-4 service down | Technical team, managers | Within 1 hour | Internal messaging |
| Tier 5-6 service down | Technical team | Within 4 hours | Internal messaging |
| Planned maintenance | All users | 48 hours in advance | Email + in-app notice |

### 7.2 Status Updates

During unplanned outages:
- Initial notification within response time (per severity)
- Updates every 30 minutes during active recovery
- Resolution notification when service is restored
- Post-incident report within 5 business days

---

## 8. Testing and Maintenance

### 8.1 DR Testing Schedule

| Test Type | Frequency | Scope | Success Criteria |
|-----------|-----------|-------|------------------|
| Backup restore | Monthly | Single collection restore to test env | Data matches source |
| Full database restore | Quarterly | Complete restore to test env | All collections present; app starts; health probes pass |
| Failover test (replica set) | Quarterly | Kill primary; verify election and app reconnection | Service recovers within 1 minute |
| Full DR drill | Semi-annually | Complete infrastructure rebuild from scratch | Service restored within RTO targets |
| Communication test | Semi-annually | Notification chain activation | All stakeholders notified within target times |

### 8.2 Test Documentation

Each DR test must produce:
- Test date and participants
- Scenario tested
- Actual recovery time vs. target RTO
- Issues encountered
- Improvements identified
- Sign-off by operations lead

### 8.3 Plan Maintenance

| Activity | Frequency | Responsible |
|----------|-----------|-------------|
| Full BCP review | Semi-annually | Operations lead + Security team |
| Contact list update | Quarterly | Operations lead |
| RTO/RPO target review | Annually | Business stakeholders + Operations |
| Backup procedure verification | Monthly | Operations team |
| Infrastructure documentation update | Per deployment change | Operations team |

---

## 9. Dependencies and Single Points of Failure

| Component | SPOF Risk | Mitigation |
|-----------|-----------|------------|
| MongoDB (standalone) | High | Deploy as replica set (ADR-0014) |
| Backend container | Medium | Docker restart policy; multiple instances behind load balancer |
| SentinelOne API | External | Graceful degradation; checkpoint resume; cached data remains available |
| JWT_SECRET_KEY | Medium | Documented rotation procedure; backup of current key |
| DNS | Medium | Redundant DNS providers |
| Docker host | High (single host) | Container orchestration (Kubernetes) or multi-host Docker Swarm for production |

---

## 10. Compliance Mapping

| Requirement | Framework | Control |
|-------------|-----------|---------|
| Availability controls | SOC 2 A1.1-A1.3 | Sections 3-6 |
| Recovery capabilities | SOC 2 CC7.4 | Sections 5-6 |
| ICT readiness | ISO 27001 A.5.30 | This plan |
| Business continuity during disruption | ISO 27001 A.5.29 | Sections 4, 6 |
| Redundancy | ISO 27001 A.8.14 | Section 4 |

---

*This plan is reviewed semi-annually, after any significant outage, and when
infrastructure changes occur. DR test results are archived for compliance evidence.*
