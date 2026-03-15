# ISO 27001:2022 Annex A Control Mapping

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-ISO-001                               |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Security & Compliance Team                 |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Overview

This document maps Sentora's security controls to the ISO 27001:2022 Annex A
controls (A.5 through A.8). Sentora is a SentinelOne EDR Software Fingerprint &
Asset Classification Tool deployed as containerized microservices (FastAPI backend,
Vue 3 frontend, MongoDB 7 database).

ISO 27001:2022 restructured Annex A into four themes:

| Theme | Control Range | Count |
|-------|--------------|-------|
| A.5 — Organizational Controls | A.5.1 – A.5.37 | 37 |
| A.6 — People Controls | A.6.1 – A.6.8 | 8 |
| A.7 — Physical Controls | A.7.1 – A.7.14 | 14 |
| A.8 — Technological Controls | A.8.1 – A.8.34 | 34 |

---

## 2. A.5 — Organizational Controls

### A.5.1 — Policies for Information Security

| Aspect | Detail |
|--------|--------|
| **Control** | Policies for information security shall be defined, approved, published, and communicated |
| **Implementation** | `SECURITY.md` defines vulnerability disclosure, responsible reporting, and security contacts. `CODE_OF_CONDUCT.md` establishes behavioral expectations. Data classification policy in `docs/compliance/data-classification.md` |
| **Evidence** | Repository root files; compliance documentation directory |
| **Status** | Implemented |

### A.5.2 — Information Security Roles and Responsibilities

| Aspect | Detail |
|--------|--------|
| **Control** | Information security roles and responsibilities shall be defined and allocated |
| **Implementation** | RBAC model defines four roles (super_admin, admin, analyst, viewer) with explicit permissions. `require_role()` middleware enforces role boundaries at the API level |
| **Evidence** | `backend/domains/auth/entities.py`, `backend/middleware/auth.py` |
| **Status** | Implemented |

### A.5.3 — Segregation of Duties

| Aspect | Detail |
|--------|--------|
| **Control** | Conflicting duties and responsibilities shall be segregated |
| **Implementation** | Viewers cannot modify data. Analysts limited to fingerprinting operations. Only admins manage users and taxonomy. Domain-driven design enforces bounded contexts |
| **Evidence** | Role definitions in auth entities; router-level role requirements |
| **Status** | Implemented |

### A.5.4 — Management Responsibilities

| Aspect | Detail |
|--------|--------|
| **Control** | Management shall require all personnel to apply information security |
| **Implementation** | Code of conduct required for all contributors; security policy published and accessible |
| **Evidence** | `CODE_OF_CONDUCT.md`, `SECURITY.md` |
| **Status** | Implemented |

### A.5.5 — Contact with Authorities

| Aspect | Detail |
|--------|--------|
| **Control** | Appropriate contacts with relevant authorities shall be maintained |
| **Implementation** | `SECURITY.md` provides security contact information; incident response plan defines escalation paths |
| **Evidence** | `SECURITY.md`, `docs/compliance/incident-response.md` |
| **Status** | Implemented |

### A.5.7 — Threat Intelligence

| Aspect | Detail |
|--------|--------|
| **Control** | Information relating to information security threats shall be collected and analyzed |
| **Implementation** | `pip-audit` and `npm audit` in CI pipeline scan dependencies against known vulnerability databases. Dependency versions pinned and tracked |
| **Evidence** | CI workflow configuration; `backend/requirements.txt`; `frontend/package.json` |
| **Status** | Implemented |

### A.5.8 — Information Security in Project Management

| Aspect | Detail |
|--------|--------|
| **Control** | Information security shall be integrated into project management |
| **Implementation** | ADR process documents security implications of architectural decisions. Security review is part of PR review process |
| **Evidence** | `docs/adr/` — 15+ ADRs with security considerations |
| **Status** | Implemented |

### A.5.9 — Inventory of Information and Other Associated Assets

| Aspect | Detail |
|--------|--------|
| **Control** | An inventory of information and associated assets shall be maintained |
| **Implementation** | Data model documentation catalogs all MongoDB collections and their contents. Vendor management documents all third-party dependencies |
| **Evidence** | `docs/data-model.md`, `docs/compliance/vendor-management.md` |
| **Status** | Implemented |

### A.5.10 — Acceptable Use of Information and Other Associated Assets

| Aspect | Detail |
|--------|--------|
| **Control** | Rules for acceptable use shall be identified, documented, and implemented |
| **Implementation** | License terms (AGPL-3.0 and commercial) define acceptable use. Code of conduct covers contributor behavior |
| **Evidence** | `LICENSE`, `COMMERCIAL_LICENSE.md`, `CODE_OF_CONDUCT.md` |
| **Status** | Implemented |

### A.5.12 — Classification of Information

| Aspect | Detail |
|--------|--------|
| **Control** | Information shall be classified according to information security needs |
| **Implementation** | Four-tier data classification: Public, Internal, Confidential, Restricted. All Sentora data types classified with handling requirements |
| **Evidence** | `docs/compliance/data-classification.md` |
| **Status** | Implemented |

### A.5.13 — Labelling of Information

| Aspect | Detail |
|--------|--------|
| **Control** | An appropriate set of procedures for labelling shall be developed |
| **Implementation** | All compliance documents carry classification labels. Environment variable documentation marks secrets with `[REQUIRED]` sensitivity markers |
| **Evidence** | Document headers; `.env.example` |
| **Status** | Implemented |

### A.5.14 — Information Transfer

| Aspect | Detail |
|--------|--------|
| **Control** | Information transfer rules shall be in place |
| **Implementation** | TLS enforced via HSTS header. API payloads validated through Pydantic DTOs. WebSocket connections rate-limited (10 msg/s). CORS restricts cross-origin requests |
| **Evidence** | `SecurityHeadersMiddleware`, `CORSMiddleware`, DTO definitions |
| **Status** | Implemented |

### A.5.15 — Access Control

| Aspect | Detail |
|--------|--------|
| **Control** | Rules to control physical and logical access shall be established |
| **Implementation** | Comprehensive access control policy documents RBAC, authentication methods, session management, and lockout policies |
| **Evidence** | `docs/compliance/access-control-policy.md` |
| **Status** | Implemented |

### A.5.16 — Identity Management

| Aspect | Detail |
|--------|--------|
| **Control** | The full lifecycle of identities shall be managed |
| **Implementation** | User registration, authentication (JWT + TOTP 2FA), SSO (OIDC/SAML), session management, and account lockout. Admin-controlled user lifecycle |
| **Evidence** | `backend/domains/auth/` — full auth domain |
| **Status** | Implemented |

### A.5.17 — Authentication Information

| Aspect | Detail |
|--------|--------|
| **Control** | Allocation and management of authentication information shall be controlled |
| **Implementation** | Passwords hashed with bcrypt 5.x. JWT secrets from environment. TOTP secrets encrypted. Password complexity: 12+ characters with mixed requirements |
| **Evidence** | Auth service implementation; `.env.example` |
| **Status** | Implemented |

### A.5.22 — Monitoring, Review, and Change Management of Supplier Services

| Aspect | Detail |
|--------|--------|
| **Control** | Changes to supplier services shall be managed |
| **Implementation** | SentinelOne API integration includes rate limiting (token bucket), cursor-based pagination, and fail-fast on misconfiguration. Dependency versions pinned |
| **Evidence** | `backend/domains/sync/manager.py`; vendor management policy |
| **Status** | Implemented |

### A.5.23 — Information Security for Use of Cloud Services

| Aspect | Detail |
|--------|--------|
| **Control** | Processes for cloud service use shall be established |
| **Implementation** | Containerized deployment with defined resource limits. Docker Compose specifies complete topology. Non-root execution reduces blast radius |
| **Evidence** | `docker-compose.yml`, `Dockerfile.backend` |
| **Status** | Implemented |

### A.5.24 — Information Security Incident Management Planning

| Aspect | Detail |
|--------|--------|
| **Control** | Planning and preparation for managing incidents shall be established |
| **Implementation** | Six-phase incident response plan documented covering preparation through lessons learned |
| **Evidence** | `docs/compliance/incident-response.md` |
| **Status** | Implemented |

### A.5.25 — Assessment and Decision on Information Security Events

| Aspect | Detail |
|--------|--------|
| **Control** | Information security events shall be assessed and classified |
| **Implementation** | Audit logs capture security events with severity levels. Structured JSON logging enables automated analysis. Prometheus metrics provide anomaly detection signals |
| **Evidence** | Audit log collection; `backend/middleware/metrics.py` |
| **Status** | Implemented |

### A.5.26 — Response to Information Security Incidents

| Aspect | Detail |
|--------|--------|
| **Control** | Incidents shall be responded to according to documented procedures |
| **Implementation** | Incident response plan defines containment, eradication, and recovery procedures with role assignments |
| **Evidence** | `docs/compliance/incident-response.md` |
| **Status** | Implemented |

### A.5.27 — Learning from Information Security Incidents

| Aspect | Detail |
|--------|--------|
| **Control** | Knowledge from incidents shall be used to strengthen security |
| **Implementation** | Lessons Learned phase in IR plan; post-incident reviews produce ADRs for systemic improvements |
| **Evidence** | IR plan Phase 6; ADR process |
| **Status** | Implemented |

### A.5.28 — Collection of Evidence

| Aspect | Detail |
|--------|--------|
| **Control** | Procedures for identification and collection of evidence shall be established |
| **Implementation** | Hash-chain audit logs with 90-day retention provide tamper-evident evidence. Structured logging with correlation IDs enables forensic analysis |
| **Evidence** | Audit log implementation; `RequestLoggingMiddleware` |
| **Status** | Implemented |

### A.5.29 — Information Security During Disruption

| Aspect | Detail |
|--------|--------|
| **Control** | Security shall be maintained during disruption |
| **Implementation** | Business continuity plan addresses security during disruption scenarios. MongoDB replica set provides data availability. Checkpoint-based sync enables recovery |
| **Evidence** | `docs/compliance/business-continuity.md` |
| **Status** | Implemented |

### A.5.30 — ICT Readiness for Business Continuity

| Aspect | Detail |
|--------|--------|
| **Control** | ICT readiness shall be planned, implemented, maintained, and tested |
| **Implementation** | HA MongoDB, automated backups, defined RPO/RTO targets, health check endpoints for automated failover |
| **Evidence** | Business continuity plan; health endpoints |
| **Status** | Implemented |

### A.5.31 — Legal, Statutory, Regulatory, and Contractual Requirements

| Aspect | Detail |
|--------|--------|
| **Control** | Legal and regulatory requirements shall be identified |
| **Implementation** | AGPL-3.0 and commercial license terms clearly defined. SOC 2 and ISO 27001 compliance mappings maintained |
| **Evidence** | `LICENSE`, `COMMERCIAL_LICENSE.md`, compliance documentation |
| **Status** | Implemented |

### A.5.34 — Privacy and Protection of PII

| Aspect | Detail |
|--------|--------|
| **Control** | Privacy requirements shall be identified and met |
| **Implementation** | Data classification identifies PII (user emails, agent hostnames/IPs) with appropriate handling requirements. Audit log TTL ensures data minimization |
| **Evidence** | Data classification policy; audit log TTL configuration |
| **Status** | Implemented |

### A.5.35 — Independent Review of Information Security

| Aspect | Detail |
|--------|--------|
| **Control** | The approach to managing information security shall be independently reviewed |
| **Implementation** | Semi-annual compliance document reviews scheduled. External audit readiness maintained |
| **Evidence** | Review dates on all compliance documents |
| **Status** | Implemented |

### A.5.36 — Compliance with Policies, Rules, and Standards

| Aspect | Detail |
|--------|--------|
| **Control** | Compliance shall be regularly reviewed |
| **Implementation** | Automated CI enforcement of code quality standards. Semi-annual compliance reviews. Coverage gates prevent regression |
| **Evidence** | CI configuration; compliance review schedule |
| **Status** | Implemented |

### A.5.37 — Documented Operating Procedures

| Aspect | Detail |
|--------|--------|
| **Control** | Operating procedures shall be documented and available |
| **Implementation** | `docs/` directory contains comprehensive operational documentation including troubleshooting, deployment, and security guides |
| **Evidence** | `docs/troubleshooting.md`, `docs/deployment/`, `docs/guides/` |
| **Status** | Implemented |

---

## 3. A.6 — People Controls

### A.6.1 — Screening

| Aspect | Detail |
|--------|--------|
| **Control** | Background verification checks shall be carried out |
| **Implementation** | Organizational policy (out of scope for application-level controls) |
| **Status** | N/A — Organizational |

### A.6.3 — Information Security Awareness, Education, and Training

| Aspect | Detail |
|--------|--------|
| **Control** | Personnel shall receive appropriate security awareness training |
| **Implementation** | Security policy and code of conduct published. Contribution guidelines include security considerations |
| **Evidence** | `SECURITY.md`, `CODE_OF_CONDUCT.md` |
| **Status** | Partially Implemented |

### A.6.8 — Information Security Event Reporting

| Aspect | Detail |
|--------|--------|
| **Control** | Personnel shall report observed or suspected security events |
| **Implementation** | `SECURITY.md` defines vulnerability reporting process with expected timelines |
| **Evidence** | `SECURITY.md` |
| **Status** | Implemented |

---

## 4. A.7 — Physical Controls

### A.7.4 — Physical Security Monitoring

| Aspect | Detail |
|--------|--------|
| **Control** | Premises shall be continuously monitored for unauthorized access |
| **Implementation** | Not applicable — Sentora is a containerized application. Physical security is the responsibility of the hosting infrastructure provider |
| **Status** | N/A — Infrastructure Provider |

> **Note:** Physical controls (A.7.1 through A.7.14) are largely delegated to the
> infrastructure/cloud provider. The Statement of Applicability (SoA) should document
> this delegation with references to the provider's compliance certifications.

---

## 5. A.8 — Technological Controls

### A.8.1 — User Endpoint Devices

| Aspect | Detail |
|--------|--------|
| **Control** | Information stored on, processed by, or accessible via endpoint devices shall be protected |
| **Implementation** | Frontend SPA runs in browser with CSP headers preventing XSS. No local data persistence beyond session tokens. HSTS enforces encrypted transport |
| **Evidence** | `SecurityHeadersMiddleware` CSP configuration |
| **Status** | Implemented |

### A.8.2 — Privileged Access Rights

| Aspect | Detail |
|--------|--------|
| **Control** | Allocation and use of privileged access rights shall be restricted and managed |
| **Implementation** | `super_admin` and `admin` roles strictly controlled. Admin creation requires existing admin privileges. All privileged actions logged in audit trail |
| **Evidence** | `backend/domains/auth/service.py`; audit log collection |
| **Status** | Implemented |

### A.8.3 — Information Access Restriction

| Aspect | Detail |
|--------|--------|
| **Control** | Access to information shall be restricted according to access control policy |
| **Implementation** | Endpoint-level authorization via `require_role()`. DTO layer prevents exposure of internal entities. Query-level filtering by user context |
| **Evidence** | `backend/middleware/auth.py`; router files |
| **Status** | Implemented |

### A.8.4 — Access to Source Code

| Aspect | Detail |
|--------|--------|
| **Control** | Read and write access to source code shall be managed |
| **Implementation** | Git repository with branch protection. PR reviews required. No direct commits to main branch |
| **Evidence** | GitHub repository settings |
| **Status** | Implemented |

### A.8.5 — Secure Authentication

| Aspect | Detail |
|--------|--------|
| **Control** | Secure authentication technologies and procedures shall be established |
| **Implementation** | JWT tokens (15-min access, 7-day refresh with rotation). bcrypt 5.x password hashing. TOTP 2FA. OIDC/SAML SSO. Password complexity: 12+ chars. Account lockout: 5 attempts / 15 min |
| **Evidence** | `backend/domains/auth/` — complete auth domain |
| **Status** | Implemented |

### A.8.6 — Capacity Management

| Aspect | Detail |
|--------|--------|
| **Control** | Use of resources shall be monitored and adjusted |
| **Implementation** | Container resource limits (1 CPU, 1 GB RAM). Prometheus metrics track request rates and durations. Rate limiting prevents capacity exhaustion |
| **Evidence** | `docker-compose.yml`; `backend/middleware/metrics.py` |
| **Status** | Implemented |

### A.8.7 — Protection Against Malware

| Aspect | Detail |
|--------|--------|
| **Control** | Protection against malware shall be implemented |
| **Implementation** | Input validation (Pydantic models). Body size limiting (10 MB max). Dependency vulnerability scanning. No file upload functionality exposed |
| **Evidence** | `BodySizeLimitMiddleware`; DTO validation; CI vulnerability scanning |
| **Status** | Implemented |

### A.8.8 — Management of Technical Vulnerabilities

| Aspect | Detail |
|--------|--------|
| **Control** | Information about technical vulnerabilities shall be obtained and evaluated |
| **Implementation** | `pip-audit` and `npm audit` in CI. Known-vulnerable packages removed (python-jose, passlib). ReDoS testing in test suite. `SECURITY.md` vulnerability disclosure |
| **Evidence** | CI workflows; test suite; `SECURITY.md` |
| **Status** | Implemented |

### A.8.9 — Configuration Management

| Aspect | Detail |
|--------|--------|
| **Control** | Configurations shall be established, documented, implemented, monitored, and reviewed |
| **Implementation** | `domains/config/` provides runtime configuration management. `.env.example` documents all configuration with `[REQUIRED]` markers. Docker Compose defines deployment configuration |
| **Evidence** | Config domain; `.env.example`; `docker-compose.yml` |
| **Status** | Implemented |

### A.8.10 — Information Deletion

| Aspect | Detail |
|--------|--------|
| **Control** | Information shall be deleted when no longer required |
| **Implementation** | Audit log TTL (90 days) ensures automated deletion. JWT tokens self-expire (15 min access, 7 days refresh). MongoDB TTL indexes enforce retention policies |
| **Evidence** | Audit log TTL index; JWT expiration configuration |
| **Status** | Implemented |

### A.8.11 — Data Masking

| Aspect | Detail |
|--------|--------|
| **Control** | Data masking shall be used in accordance with access control policy |
| **Implementation** | DTO layer exposes only necessary fields. Passwords never returned in API responses. API tokens not logged. Structured logging excludes sensitive fields |
| **Evidence** | DTO definitions; logging configuration |
| **Status** | Implemented |

### A.8.12 — Data Leakage Prevention

| Aspect | Detail |
|--------|--------|
| **Control** | Data leakage prevention measures shall be applied |
| **Implementation** | CSP headers prevent data exfiltration via scripts. CORS restricts cross-origin access. `.gitignore` prevents committing secrets. DTO layer prevents internal entity exposure |
| **Evidence** | `SecurityHeadersMiddleware`; `CORSMiddleware`; `.gitignore` |
| **Status** | Implemented |

### A.8.14 — Redundancy of Information Processing Facilities

| Aspect | Detail |
|--------|--------|
| **Control** | Information processing facilities shall be implemented with sufficient redundancy |
| **Implementation** | MongoDB replica set support with automatic failover. Health probes enable load balancer-driven failover for application tier |
| **Evidence** | ADR-0014; health check endpoints; `docker-compose.yml` |
| **Status** | Implemented |

### A.8.15 — Logging

| Aspect | Detail |
|--------|--------|
| **Control** | Logs recording activities, exceptions, faults, and events shall be produced and protected |
| **Implementation** | Structured JSON logging (loguru) with correlation IDs. Audit logs with hash-chain integrity. Prometheus metrics. 90-day audit retention |
| **Evidence** | `RequestLoggingMiddleware`; audit log collection; `backend/middleware/metrics.py` |
| **Status** | Implemented |

### A.8.16 — Monitoring Activities

| Aspect | Detail |
|--------|--------|
| **Control** | Networks, systems, and applications shall be monitored for anomalous behavior |
| **Implementation** | Prometheus metrics (request counts, durations, in-progress). Health check probes. OpenTelemetry tracing (opt-in). Rate limiting detects abnormal request patterns |
| **Evidence** | `/metrics` endpoint; `/health`; `/health/ready`; `backend/middleware/tracing.py` |
| **Status** | Implemented |

### A.8.20 — Networks Security

| Aspect | Detail |
|--------|--------|
| **Control** | Networks and network devices shall be secured |
| **Implementation** | Docker network isolation between containers. CORS policy restricts cross-origin access. HSTS enforces encrypted transport. Rate limiting protects against network-level abuse |
| **Evidence** | `docker-compose.yml` network config; middleware stack |
| **Status** | Implemented |

### A.8.22 — Web Filtering

| Aspect | Detail |
|--------|--------|
| **Control** | Access to external websites shall be managed to reduce exposure to malicious content |
| **Implementation** | Backend makes outbound connections only to configured SentinelOne API endpoint. No arbitrary outbound access. CSP restricts frontend resource loading |
| **Evidence** | S1Client configuration; CSP headers |
| **Status** | Implemented |

### A.8.24 — Use of Cryptography

| Aspect | Detail |
|--------|--------|
| **Control** | Rules for effective use of cryptography shall be defined and implemented |
| **Implementation** | bcrypt 5.x for password hashing. PyJWT for token signing (HS256/RS256). HSTS for transport encryption. Hash-chain integrity for audit logs |
| **Evidence** | Auth service; SecurityHeadersMiddleware; audit log implementation |
| **Status** | Implemented |

### A.8.25 — Secure Development Life Cycle

| Aspect | Detail |
|--------|--------|
| **Control** | Rules for secure development shall be established and applied |
| **Implementation** | CI pipeline: linting (ruff) -> type checking (mypy, vue-tsc) -> tests (pytest, vitest) -> Docker build. PR reviews required. ADR documentation for decisions |
| **Evidence** | `.github/workflows/`; `docs/adr/`; `docs/compliance/change-management.md` |
| **Status** | Implemented |

### A.8.26 — Application Security Requirements

| Aspect | Detail |
|--------|--------|
| **Control** | Information security requirements shall be identified when developing or acquiring applications |
| **Implementation** | Security requirements documented in ADRs. Input validation via Pydantic. Authentication and authorization built into middleware layer. Security headers applied globally |
| **Evidence** | ADRs; middleware stack; DTO definitions |
| **Status** | Implemented |

### A.8.27 — Secure System Architecture and Engineering Principles

| Aspect | Detail |
|--------|--------|
| **Control** | Principles for engineering secure systems shall be established and applied |
| **Implementation** | CQRS architecture. DDD bounded contexts. DTO-based data transfer (no entity exposure). Non-root containers. Multi-stage Docker builds. Single-worker deployment for lock safety |
| **Evidence** | `backend/domains/` architecture; `Dockerfile.backend` |
| **Status** | Implemented |

### A.8.28 — Secure Coding

| Aspect | Detail |
|--------|--------|
| **Control** | Secure coding principles shall be applied |
| **Implementation** | Ruff linter enforces code standards. Pydantic validates all inputs. Parameterized MongoDB queries prevent injection. No dynamic query construction. ReDoS testing |
| **Evidence** | CI linting; DTO definitions; test suite |
| **Status** | Implemented |

### A.8.29 — Security Testing in Development and Acceptance

| Aspect | Detail |
|--------|--------|
| **Control** | Security testing processes shall be defined and implemented |
| **Implementation** | 279 backend tests (87.40% coverage). 169 frontend tests. Playwright E2E tests. Load testing with Locust. ReDoS unit tests. Integration tests for auth, sync, and all domains |
| **Evidence** | Test configurations; CI test results |
| **Status** | Implemented |

### A.8.31 — Separation of Development, Test, and Production Environments

| Aspect | Detail |
|--------|--------|
| **Control** | Development, testing, and production environments shall be separated |
| **Implementation** | Test database (`sentora_test`) auto-dropped before/after each test. Development runs on ports 5002/5003. Docker Compose defines isolated production topology. CORS credentials restricted in production only |
| **Evidence** | Test configuration; `docker-compose.yml`; CORS middleware config |
| **Status** | Implemented |

### A.8.32 — Change Management

| Aspect | Detail |
|--------|--------|
| **Control** | Changes to information processing facilities shall be subject to change management procedures |
| **Implementation** | Feature branch workflow. PR reviews required. CI validation before merge. ADR documentation for architectural changes. Versioned releases with changelog |
| **Evidence** | `docs/compliance/change-management.md`; `CHANGELOG.md`; `docs/adr/` |
| **Status** | Implemented |

### A.8.33 — Test Information

| Aspect | Detail |
|--------|--------|
| **Control** | Test information shall be appropriately selected, protected, and managed |
| **Implementation** | Dedicated test database dropped between runs. No production data used in tests. Test fixtures use synthetic data |
| **Evidence** | Test configuration; conftest.py setup |
| **Status** | Implemented |

### A.8.34 — Protection of Information Systems During Audit Testing

| Aspect | Detail |
|--------|--------|
| **Control** | Audit tests shall be planned and agreed with management |
| **Implementation** | Load testing uses controlled profiles (ReadOnly 80%, Sync 10%, Power 10%). Tests run against isolated environments. Rate limiting protects production during any audit scanning |
| **Evidence** | `backend/tests/load/locustfile.py`; rate limiting middleware |
| **Status** | Implemented |

---

## 6. Statement of Applicability Summary

| Control Range | Total | Applicable | Implemented | Partially | Not Applicable |
|--------------|-------|-----------|-------------|-----------|---------------|
| A.5 (Organizational) | 37 | 28 | 26 | 1 | 9 |
| A.6 (People) | 8 | 3 | 2 | 1 | 5 |
| A.7 (Physical) | 14 | 0 | 0 | 0 | 14 |
| A.8 (Technological) | 34 | 24 | 24 | 0 | 10 |
| **Total** | **93** | **55** | **52** | **2** | **38** |

> **Note:** Physical controls (A.7) are delegated to the infrastructure provider and
> excluded from the application-level Statement of Applicability. Controls marked
> "Not Applicable" are either organizational-level (handled outside the application)
> or not relevant to the deployment model.

---

## 7. Gap Analysis

| Gap ID | Control | Gap Description | Remediation | Priority | Target |
|--------|---------|-----------------|-------------|----------|--------|
| ISO-GAP-01 | A.5.6 | No formal threat intelligence sharing agreements | Establish threat intelligence feeds integration | Low | Q3 2026 |
| ISO-GAP-02 | A.6.3 | Security training is informal | Formalize security awareness program | Medium | Q2 2026 |
| ISO-GAP-03 | A.8.10 | No data retention policy for all collection types | Define and enforce retention for all collections | Medium | Q2 2026 |
| ISO-GAP-04 | A.5.35 | No external independent security audit completed | Schedule first external audit | High | Q2 2026 |

---

*This document is reviewed semi-annually or when significant changes to the system
occur. It references the ISO/IEC 27001:2022 standard, Annex A.*
