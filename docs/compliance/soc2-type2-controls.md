# SOC 2 Type II Control Mapping

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-SOC2-001                              |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Security & Compliance Team                 |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Overview

This document maps Sentora's existing security controls to the AICPA SOC 2 Type II
Trust Service Criteria. Sentora is a SentinelOne EDR Software Fingerprint & Asset
Classification Tool built on FastAPI (Python 3.12+), Vue 3 (TypeScript), and MongoDB 7.

SOC 2 Type II evaluates the operating effectiveness of controls over a defined period
(typically 6-12 months). This mapping identifies the controls in place, the evidence
artifacts that demonstrate their operation, and any gaps requiring remediation.

### Scope

The following components are in scope:

| Component         | Description                                              |
|-------------------|----------------------------------------------------------|
| Backend API       | FastAPI application (`backend/main.py`)                  |
| Frontend SPA      | Vue 3 application (`frontend/`)                          |
| Database          | MongoDB 7 (replica set)                                  |
| Authentication    | JWT + RBAC + TOTP 2FA + OIDC SSO + SAML SSO + API Keys  |
| CI/CD Pipeline    | GitHub Actions (lint, test, build, deploy)                |
| Infrastructure    | Docker containers with non-root user, resource limits    |
| Monitoring        | Prometheus metrics, structured logging, health probes    |

---

## 2. CC1 — Control Environment

### CC1.1 — Demonstrates Commitment to Integrity and Ethical Values

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC1.1-01 | Code of conduct is documented and accessible | `CODE_OF_CONDUCT.md` in repository root defines behavioral expectations for all contributors | File exists in repo root |
| CC1.1-02 | Security policy published | `SECURITY.md` defines vulnerability disclosure process, responsible disclosure timelines, and security contact information | File exists in repo root |
| CC1.1-03 | Licensing terms clearly defined | `LICENSE` (AGPL-3.0) and `COMMERCIAL_LICENSE.md` define usage terms | Files exist in repo root |

### CC1.2 — Board Exercises Oversight

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC1.2-01 | Architecture Decision Records maintained | `docs/adr/` contains 22 ADRs documenting all significant technical decisions with context, decision, and consequences | ADR directory listing |
| CC1.2-02 | Documentation of system architecture | `docs/architecture/` contains system design documentation; `docs/data-model.md` documents all MongoDB collections | Documentation files |

### CC1.3 — Establishes Structure, Authority, and Responsibility

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC1.3-01 | Role-based access control model | Four roles defined: `super_admin`, `admin`, `analyst`, `viewer` with distinct permission boundaries | `backend/domains/auth/entities.py` |
| CC1.3-02 | Separation of duties | Read-only viewer role cannot modify data; analyst role limited to fingerprinting; admin manages users and taxonomy | `backend/middleware/auth.py` — `require_role()` |
| CC1.3-03 | Domain-driven design enforces boundaries | 17 bounded contexts with dedicated entities, DTOs, repositories, services, and routers | `backend/domains/` directory structure |

### CC1.4 — Demonstrates Commitment to Competence

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC1.4-01 | Automated code quality enforcement | Ruff linter, mypy type checking, vue-tsc type checking enforced in CI | `.github/workflows/` |
| CC1.4-02 | Comprehensive test coverage | Backend: 279 tests, 87.40% coverage (85% gate); Frontend: 169 tests; E2E: Playwright smoke tests | `backend/pytest.ini`, `frontend/vitest.config.ts` |

### CC1.5 — Enforces Accountability

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC1.5-01 | Audit logging with tamper detection | All security-relevant actions logged with hash-chain integrity verification; 90-day TTL retention | Audit log collection in MongoDB |
| CC1.5-02 | Correlation IDs for request tracing | `RequestLoggingMiddleware` assigns unique correlation IDs to every request | `backend/middleware/` |
| CC1.5-03 | Git history maintains change accountability | All changes tracked via Git with commit authorship; PRs required for merges | GitHub repository settings |

---

## 3. CC2 — Communication and Information

### CC2.1 — Uses Relevant Information

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC2.1-01 | Structured JSON logging | Loguru configured for structured JSON output with correlation IDs, timestamps, severity levels | `backend/main.py`, `RequestLoggingMiddleware` |
| CC2.1-02 | Real-time sync progress | WebSocket endpoint at `/api/v1/sync/progress` broadcasts sync status with rate limiting (10 msg/s per client) | `backend/domains/sync/manager.py` |
| CC2.1-03 | API documentation auto-generated | OpenAPI schema served at `/api/spec.json` and `/api/spec.yaml` | `backend/main.py` |

### CC2.2 — Communicates Internally

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC2.2-01 | ADR process for architectural decisions | All significant decisions documented with context, alternatives considered, and consequences | `docs/adr/README.md` |
| CC2.2-02 | Changelog maintained | `CHANGELOG.md` tracks all notable changes by version | File in repo root |
| CC2.2-03 | Troubleshooting documentation | Common issues and solutions documented | `docs/troubleshooting.md` |

### CC2.3 — Communicates Externally

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC2.3-01 | Security vulnerability disclosure process | `SECURITY.md` defines how to report vulnerabilities, expected response times, and disclosure policy | File in repo root |
| CC2.3-02 | Webhook notifications for security events | System supports webhook notifications for sync failures, auth anomalies, and classification changes | Configuration documentation |

---

## 4. CC3 — Risk Assessment

### CC3.1 — Specifies Suitable Objectives

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC3.1-01 | Security objectives documented | Security requirements documented in `SECURITY.md` and `docs/security/` | Documentation files |
| CC3.1-02 | Data classification policy | Four-tier classification (Public, Internal, Confidential, Restricted) applied to all data types | `docs/compliance/data-classification.md` |

### CC3.2 — Identifies and Analyzes Risk

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC3.2-01 | Dependency vulnerability scanning | `pip-audit` and `npm audit` integrated into CI pipeline to detect known CVEs | CI workflow files |
| CC3.2-02 | Removed vulnerable dependencies | python-jose (unmaintained, known CVEs) replaced with PyJWT; passlib replaced with direct bcrypt 5.x | `docs/adr/` ADR documenting change |
| CC3.2-03 | ReDoS protection tested | Regex denial-of-service tests included in test suite | `backend/tests/` — regex_dos tests |

### CC3.3 — Considers Potential for Fraud

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC3.3-01 | Rate limiting prevents abuse | Per-IP sliding window rate limiting on all API endpoints | Rate limiting middleware |
| CC3.3-02 | Account lockout prevents brute force | 5 failed login attempts triggers 15-minute lockout | `backend/domains/auth/service.py` |
| CC3.3-03 | Input validation prevents injection | Pydantic models validate all request bodies; MongoDB parameterized queries prevent NoSQL injection | All DTO definitions in `backend/domains/*/dto.py` |

### CC3.4 — Identifies and Assesses Changes

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC3.4-01 | Change management process | All changes go through feature branches, PR review, CI validation, and controlled deployment | `docs/compliance/change-management.md` |
| CC3.4-02 | Migration strategy documented | MongoDB schema evolution strategy documented with forward-compatible patterns | `docs/deployment/migrations.md` |

---

## 5. CC4 — Monitoring Activities

### CC4.1 — Selects and Develops Monitoring Activities

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC4.1-01 | Prometheus metrics collection | `MetricsMiddleware` tracks request counts, duration histograms, and in-progress gauge per endpoint | `backend/middleware/metrics.py` |
| CC4.1-02 | Health check endpoints | Liveness (`/health`) and readiness (`/health/ready`) probes; readiness pings MongoDB | `backend/main.py` |
| CC4.1-03 | Audit log integrity verification | Hash-chain audit logs enable tamper detection; each entry references hash of previous entry | Audit log implementation |

### CC4.2 — Evaluates and Communicates Deficiencies

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC4.2-01 | CI test gates prevent regression | 85% backend coverage gate; frontend coverage thresholds (60-70%); all tests must pass before merge | `frontend/vitest.config.ts`, pytest config |
| CC4.2-02 | Load testing identifies performance issues | Locust configuration with 3 user profiles (ReadOnly 80%, Sync 10%, Power 10%) | `backend/tests/load/locustfile.py` |
| CC4.2-03 | OpenTelemetry tracing (opt-in) | Distributed tracing via `OTEL_ENABLED=true` for request flow analysis | `backend/middleware/tracing.py` |

---

## 6. CC5 — Control Activities

### CC5.1 — Selects and Develops Control Activities

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC5.1-01 | RBAC enforcement on all protected endpoints | `require_role()` middleware validates JWT claims and role membership before handler execution | `backend/middleware/auth.py` |
| CC5.1-02 | Per-IP rate limiting | Sliding window algorithm limits request rates per IP address per endpoint | Rate limiting implementation |
| CC5.1-03 | Request body size limiting | `BodySizeLimitMiddleware` enforces 10 MB maximum request size (returns HTTP 413) | `backend/main.py` middleware stack |
| CC5.1-04 | Security headers on all responses | CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy | `SecurityHeadersMiddleware` |

### CC5.2 — Deploys Through Policies and Procedures

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC5.2-01 | DTO-based data transfer | All API boundaries use Pydantic DTOs; internal entities never exposed directly | `backend/domains/*/dto.py` |
| CC5.2-02 | Concurrency control | `asyncio.Lock` guards concurrent proposal generation; single-worker deployment enforced | `backend/domains/fingerprint/service.py` |
| CC5.2-03 | Distributed locking for future scaling | MongoDB advisory locks implemented for multi-worker scenarios | `backend/utils/distributed_lock.py` |

### CC5.3 — Deploys Using Technology

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC5.3-01 | Automated CI/CD pipeline | GitHub Actions runs linting (ruff), type checking (mypy, vue-tsc), tests (pytest, vitest), and Docker builds | `.github/workflows/` |
| CC5.3-02 | Container security | Non-root user (`apprunner`, uid 1001), multi-stage Docker builds, resource limits (1 CPU, 1G RAM) | `Dockerfile.backend`, `docker-compose.yml` |

---

## 7. CC6 — Logical and Physical Access Controls

### CC6.1 — Implements Logical Access Security

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC6.1-01 | JWT-based authentication | Short-lived access tokens (15 min) with refresh token rotation (7-day lifetime) | `backend/domains/auth/service.py` |
| CC6.1-02 | Multi-factor authentication | TOTP-based 2FA enrollment and verification for all user accounts | `backend/domains/auth/` |
| CC6.1-03 | SSO integration | OIDC and SAML SSO support for enterprise identity provider federation | Auth domain implementation |
| CC6.1-04 | Password complexity enforcement | Minimum 12 characters with complexity requirements (uppercase, lowercase, digit); special chars optional per NIST guidance | Auth service validation |
| CC6.1-05 | API key authentication | Tenant-scoped API keys with SHA-256 hashing, scope-based access control, per-key rate limiting, and key rotation with grace period (ADR-0022) | `backend/domains/api_keys/` |

### CC6.2 — Controls Access Credentials

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC6.2-01 | Passwords hashed with bcrypt | bcrypt 5.x with appropriate work factor; no plaintext storage | `backend/domains/auth/service.py` |
| CC6.2-02 | API token protection | S1 API tokens stored as environment variables, never in code or logs | `.env.example` documents required vars |
| CC6.2-03 | JWT secret management | `JWT_SECRET_KEY` from environment; auto-generated with warning if not configured | `backend/config.py` startup |
| CC6.2-04 | API key credential storage | API keys stored as SHA-256 hashes; plaintext shown once at creation, never persisted | `backend/domains/api_keys/service.py` |

### CC6.3 — Restricts Logical Access

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC6.3-01 | Role-based access control | Four roles: super_admin > admin > analyst > viewer with hierarchical permissions | `backend/domains/auth/entities.py` |
| CC6.3-02 | Endpoint-level authorization | Each route declares required role; `OptionalAuth` for backward-compatible public access | Router files across all domains |
| CC6.3-03 | Session management | Server-side sessions with 30-day inactivity timeout, 30-day absolute lifetime, immediate revocation via in-memory cache | Auth service + session registry |
| CC6.3-04 | Account lockout | 5 failed attempts triggers 15-minute lockout with exponential backoff | Auth service implementation |

### CC6.4 — Prevents Unauthorized Access

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC6.4-01 | CORS policy | Explicit allowed origins, methods, and headers; credentials restricted in production | `CORSMiddleware` in `backend/main.py` |
| CC6.4-02 | Content Security Policy | CSP header prevents XSS and data injection attacks | `SecurityHeadersMiddleware` |
| CC6.4-03 | Transport security | HSTS header enforces HTTPS in production | `SecurityHeadersMiddleware` |

### CC6.5 — Disposes of Confidential Information

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC6.5-01 | Audit log TTL | 90-day TTL on audit log entries ensures automated disposal | MongoDB TTL index configuration |
| CC6.5-02 | Token expiration | Access tokens expire in 15 minutes; refresh tokens expire in 7 days | Auth service token generation |

### CC6.6 — Restricts Access to System Components

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC6.6-01 | Non-root container execution | Backend runs as `apprunner` (uid 1001), not root | `Dockerfile.backend` |
| CC6.6-02 | Resource limits | CPU (1 core) and memory (1 GB) limits per container | `docker-compose.yml` |
| CC6.6-03 | MongoDB access control | Database authentication required; connection string secured via environment variable | `.env.example` |

---

## 8. CC7 — System Operations

### CC7.1 — Detects and Monitors Configuration Changes

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC7.1-01 | Runtime configuration management | `domains/config/` provides centralized runtime config with audit trail | Config domain implementation |
| CC7.1-02 | Infrastructure as Code | Docker Compose defines complete deployment topology | `docker-compose.yml` |

### CC7.2 — Monitors System Components

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC7.2-01 | Prometheus metrics endpoint | Request counters, duration histograms, in-progress gauges at `/metrics` | `backend/middleware/metrics.py` |
| CC7.2-02 | Liveness probe | `/health` returns 200 always | `backend/main.py` |
| CC7.2-03 | Readiness probe | `/health/ready` pings MongoDB, returns 503 if down | `backend/main.py` |
| CC7.2-04 | Structured logging | JSON-formatted logs with loguru; correlation IDs per request | `RequestLoggingMiddleware` |

### CC7.3 — Evaluates Security Events

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC7.3-01 | Audit log analysis | Security-relevant events (login, role change, data modification) logged with actor, action, target, timestamp | Audit log collection |
| CC7.3-02 | Hash-chain integrity | Each audit entry contains hash of previous entry; enables tamper detection | Audit log implementation |

### CC7.4 — Implements Recovery Mechanisms

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC7.4-01 | Checkpoint-based sync resume | Sync operations checkpoint progress; can resume after failure without full re-sync | `backend/domains/sync/manager.py` |
| CC7.4-02 | Graceful degradation | Readiness probe reports unhealthy; load balancer removes instance from rotation | Health check endpoints |

---

## 9. CC8 — Change Management

### CC8.1 — Manages Changes Through Defined Process

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC8.1-01 | Feature branch workflow | All changes developed on feature branches; direct commits to main prohibited | GitHub branch protection |
| CC8.1-02 | Pull request reviews | Code review required before merge; CI must pass | GitHub PR settings |
| CC8.1-03 | ADR documentation | Significant architectural decisions documented with context and consequences | `docs/adr/` — 22 ADRs |

### CC8.2 — Tests Changes Before Deployment

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC8.2-01 | Automated test suite | Backend: 279 tests (87.40% coverage); Frontend: 169 tests; E2E: Playwright | Test configurations |
| CC8.2-02 | Multi-stage CI pipeline | Lint (ruff) -> Type check (mypy, vue-tsc) -> Unit tests -> Integration tests -> Docker build | `.github/workflows/` |
| CC8.2-03 | Load testing | Locust-based load tests with realistic user profiles | `backend/tests/load/locustfile.py` |

### CC8.3 — Manages System Changes

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC8.3-01 | Versioned releases | Changelog tracks versions; Docker images tagged by version | `CHANGELOG.md`, Docker config |
| CC8.3-02 | Migration strategy | Forward-compatible MongoDB schema evolution; migration docs maintained | `docs/deployment/migrations.md` |

---

## 10. CC9 — Risk Mitigation

### CC9.1 — Identifies and Manages Risks

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC9.1-01 | Automated backup with retention | MongoDB backup strategy with defined retention periods | Backup configuration |
| CC9.1-02 | High availability | MongoDB replica set support for failover | `docs/adr/0014-mongodb-replica-set-support.md` |
| CC9.1-03 | Distributed locking | MongoDB advisory locks prevent data corruption in multi-worker scenarios | `backend/utils/distributed_lock.py` |

### CC9.2 — Manages Vendor Risk

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| CC9.2-01 | Dependency inventory | All dependencies pinned with known versions; unmaintained packages removed | `backend/requirements.txt`, `frontend/package.json` |
| CC9.2-02 | Vulnerability scanning | `pip-audit` and `npm audit` in CI pipeline | CI workflow configuration |
| CC9.2-03 | Vendor management policy | Third-party risk assessment process documented | `docs/compliance/vendor-management.md` |

---

## 11. A1 — Availability

### A1.1 — Maintains Processing Capacity

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| A1.1-01 | Container resource limits | 1 CPU, 1 GB RAM per container with Docker resource management | `docker-compose.yml` |
| A1.1-02 | Rate limiting prevents overload | Per-IP sliding window rate limiting protects backend from abuse | Rate limiting middleware |
| A1.1-03 | SentinelOne API rate limiting | Token bucket algorithm prevents exceeding S1 API limits | `backend/domains/sync/manager.py` |

### A1.2 — Provides Recovery Capabilities

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| A1.2-01 | MongoDB replica set failover | Automatic primary election on node failure | ADR-0014, MongoDB config |
| A1.2-02 | Checkpoint-based resume | Sync checkpoints enable restart without full re-sync | Sync manager implementation |
| A1.2-03 | Automated backups | Scheduled MongoDB backups with defined RPO/RTO targets | Backup configuration |

### A1.3 — Tests Recovery Procedures

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| A1.3-01 | Disaster recovery plan documented | Recovery procedures and testing schedule defined | `docs/compliance/business-continuity.md` |

---

## 12. PI1 — Processing Integrity

### PI1.1 — Maintains Processing Integrity

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| PI1.1-01 | Input validation via Pydantic | All API inputs validated through Pydantic models with type checking and constraints | `backend/domains/*/dto.py` |
| PI1.1-02 | TF-IDF fingerprint matching | Weight-based scoring with 0.7/0.4 thresholds ensures classification accuracy | `backend/domains/fingerprint/matcher.py` |
| PI1.1-03 | Classification algorithms tested | TF-IDF scoring, lift-based proposer, and weighted marker matching verified in unit tests | `backend/tests/unit/test_matcher.py`, `backend/tests/test_integration/test_fingerprint_proposals.py` |

### PI1.2 — Detects Processing Errors

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| PI1.2-01 | Error hierarchy with structured responses | Consistent error handling with typed exceptions and HTTP status mapping | `docs/adr/0011-error-hierarchy-over-http-exceptions.md` |
| PI1.2-02 | 409 Conflict guards | Concurrent operation detection prevents duplicate processing | Fingerprint service `_proposal_lock` |

---

## 13. C1 — Confidentiality

### C1.1 — Identifies Confidential Information

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| C1.1-01 | Data classification policy | Four-tier classification applied to all data types | `docs/compliance/data-classification.md` |
| C1.1-02 | Sensitive data identified | API tokens, JWT secrets, passwords, TOTP secrets classified as Restricted | Data classification policy |

### C1.2 — Protects Confidential Information

| Control ID | Control Description | Implementation | Evidence |
|------------|-------------------|----------------|----------|
| C1.2-01 | Secrets in environment variables | No secrets in code; `.env.example` documents required variables with `[REQUIRED]` markers | `.env.example` |
| C1.2-02 | Password hashing | bcrypt 5.x with appropriate cost factor; passwords never stored in plaintext | Auth service |
| C1.2-03 | TLS encryption in transit | HSTS header enforces HTTPS; TLS termination at load balancer | SecurityHeadersMiddleware |
| C1.2-04 | Non-root containers | Reduced attack surface; container compromise limited to `apprunner` user | `Dockerfile.backend` |

---

## 14. Gap Analysis and Remediation

| Gap ID | TSC Criterion | Gap Description | Remediation Plan | Priority | Target Date |
|--------|--------------|-----------------|------------------|----------|-------------|
| GAP-01 | CC1.2 | Formal security governance board not established | Establish quarterly security review meetings | Medium | Q2 2026 |
| GAP-02 | CC3.2 | No formal annual risk assessment process | Implement annual risk assessment procedure | Medium | Q2 2026 |
| GAP-03 | CC4.1 | No SIEM integration | Evaluate and integrate SIEM solution for centralized log analysis | Low | Q3 2026 |
| GAP-04 | A1.3 | DR testing not regularly scheduled | Establish quarterly DR drill schedule | Medium | Q2 2026 |
| GAP-05 | CC6.6 | MongoDB encryption at rest not enforced | Enable MongoDB encrypted storage engine | High | Q2 2026 |

---

## 15. Evidence Collection Schedule

| Evidence Type | Collection Frequency | Responsible Party | Storage Location |
|--------------|---------------------|-------------------|------------------|
| Audit log exports | Monthly | Platform team | Secure archive |
| Access review reports | Quarterly | Security team | Compliance vault |
| Vulnerability scan results | Weekly (automated) | CI/CD pipeline | GitHub Actions artifacts |
| Test coverage reports | Per commit | CI/CD pipeline | GitHub Actions artifacts |
| Incident response logs | Per incident | Security team | Incident tracker |
| Change management records | Per change | Development team | Git history + PR records |
| Backup verification logs | Monthly | Operations team | Secure archive |
| Penetration test reports | Annually | Third-party auditor | Compliance vault |

---

## 16. Audit Readiness Checklist

- [ ] All control owners identified and documented
- [ ] Evidence artifacts collected for the audit period
- [ ] Gap remediation items tracked and progressing
- [ ] Access reviews completed for the period
- [ ] Incident response procedures tested within 12 months
- [ ] Business continuity plan reviewed within 12 months
- [ ] Vendor risk assessments current
- [ ] Employee security awareness training completed
- [ ] Penetration test conducted within 12 months
- [ ] Data classification review completed within 12 months

---

*This document is reviewed semi-annually or upon significant system changes. All control
mappings reference the AICPA 2017 Trust Service Criteria framework.*
