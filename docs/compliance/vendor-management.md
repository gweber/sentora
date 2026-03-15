# Vendor and Dependency Management Policy

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-VM-001                                |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Engineering & Security Team                |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Purpose

This policy defines the process for evaluating, onboarding, monitoring, and managing
third-party dependencies and vendor integrations used by the Sentora platform. It
ensures that external components do not introduce unacceptable security, licensing,
or operational risks.

---

## 2. Scope

This policy covers:

- Python packages (backend dependencies via pip)
- Node.js packages (frontend dependencies via npm)
- External API integrations (SentinelOne)
- Container base images (Docker)
- Database systems (MongoDB)
- Development and CI/CD tooling

---

## 3. Dependency Risk Assessment Framework

### 3.1 Risk Scoring Criteria

Each dependency is assessed across five dimensions:

| Dimension | Weight | Low Risk (1) | Medium Risk (2) | High Risk (3) |
|-----------|--------|-------------|-----------------|----------------|
| **Security history** | 30% | No CVEs in 3 years | Minor CVEs, promptly patched | Critical CVEs or slow response |
| **Maintenance activity** | 25% | Release within 6 months | Release within 12 months | No release > 12 months |
| **License compatibility** | 15% | MIT, BSD, Apache 2.0 | LGPL, MPL | GPL (non-AGPL), proprietary |
| **Dependency tree depth** | 15% | < 5 transitive deps | 5-20 transitive deps | > 20 transitive deps |
| **Criticality to Sentora** | 15% | Nice-to-have utility | Important functionality | Core functionality, hard to replace |

**Risk Score:** Weighted average (1.0-3.0)
- 1.0-1.5: Low risk — standard monitoring
- 1.6-2.2: Medium risk — quarterly review
- 2.3-3.0: High risk — monthly review + mitigation plan

### 3.2 Removed Dependencies

The following dependencies were removed due to unacceptable risk:

| Package | Reason for Removal | Replacement | ADR |
|---------|-------------------|-------------|-----|
| `python-jose` | Unmaintained; known CVEs; no active development | `PyJWT 2.12` | Documented in project memory |
| `passlib` | Unmaintained; incompatible with bcrypt 5.x | Direct `bcrypt 5.0` usage | Documented in project memory |

---

## 4. Backend Dependency Inventory

### 4.1 Core Dependencies

| Package | Version | License | Purpose | Risk Score | Notes |
|---------|---------|---------|---------|------------|-------|
| `fastapi` | 0.135.1 | MIT | Web framework, API routing, OpenAPI generation | 1.2 | Actively maintained by Tiangolo; large community |
| `uvicorn` | 0.41 | BSD-3 | ASGI server for FastAPI | 1.2 | Standard ASGI server; async support |
| `motor` | 3.7.1 | Apache-2.0 | Async MongoDB driver | 1.3 | Official MongoDB async driver for Python |
| `pydantic` | 2.12.5 | MIT | Data validation, DTO definitions, settings | 1.1 | Core to request/response validation; very active |
| `loguru` | 0.7.3 | MIT | Structured logging | 1.3 | Single developer but stable; widely used |
| `bcrypt` | 5.0 | Apache-2.0 | Password hashing | 1.2 | Maintained; replaces passlib dependency |
| `PyJWT` | 2.12 | MIT | JWT token creation and verification | 1.3 | Replaces python-jose; actively maintained |
| `prometheus-client` | 0.24.1 | Apache-2.0 | Metrics collection and exposition | 1.2 | Official Prometheus Python client |

### 4.2 Supporting Dependencies

| Package | Version | License | Purpose | Risk Score | Notes |
|---------|---------|---------|---------|------------|-------|
| `python-multipart` | -- | Apache-2.0 | Form data parsing (FastAPI dependency) | 1.3 | Required by FastAPI for form handling |
| `httpx` | -- | BSD-3 | HTTP client for S1 API communication | 1.2 | Modern async HTTP client |
| `scikit-learn` | -- | BSD-3 | TF-IDF vectorization for fingerprint matching | 1.4 | Large dependency tree; core to matching |

### 4.3 Development Dependencies

| Package | Version | License | Purpose | Risk Score |
|---------|---------|---------|---------|------------|
| `pytest` | -- | MIT | Test framework | 1.1 |
| `pytest-asyncio` | -- | Apache-2.0 | Async test support | 1.3 |
| `pytest-cov` | -- | MIT | Coverage reporting | 1.2 |
| `ruff` | -- | MIT | Linting and formatting | 1.1 |
| `mypy` | -- | MIT | Static type checking | 1.2 |
| `locust` | -- | MIT | Load testing | 1.3 |
| `pip-audit` | -- | Apache-2.0 | Dependency vulnerability scanning | 1.1 |

---

## 5. Frontend Dependency Inventory

### 5.1 Core Dependencies

| Package | Version | License | Purpose | Risk Score | Notes |
|---------|---------|---------|---------|------------|-------|
| `vue` | 3.5.25 | MIT | Frontend framework | 1.1 | Maintained by Evan You + core team; large ecosystem |
| `pinia` | 3.0.3 | MIT | State management | 1.2 | Official Vue state library; replaces Vuex |
| `vue-router` | 4.5.1 | MIT | Client-side routing | 1.2 | Official Vue router |
| `tailwindcss` | 4.2.1 | MIT | Utility-first CSS framework | 1.2 | Tailwind Labs; very active development |

### 5.2 Build Dependencies

| Package | Version | License | Purpose | Risk Score |
|---------|---------|---------|---------|------------|
| `vite` | 7.3+ | MIT | Build tool and dev server | 1.1 |
| `typescript` | -- | Apache-2.0 | Type checking | 1.1 |
| `vitest` | 3.2.4 | MIT | Unit testing framework | 1.2 |
| `@playwright/test` | -- | Apache-2.0 | E2E testing | 1.2 |
| `vue-tsc` | -- | MIT | Vue TypeScript type checking | 1.3 |

---

## 6. External Service Integrations

### 6.1 SentinelOne API

| Aspect | Detail |
|--------|--------|
| **Service** | SentinelOne Management Console API |
| **Purpose** | Source of agent inventory, installed applications, site/group hierarchy, tags |
| **Data classification** | Confidential (agent data), Restricted (API token) |
| **Authentication** | API token (`S1_API_TOKEN`) |
| **Rate limiting** | Token bucket algorithm in Sentora; respects S1 API rate limits |
| **Data flow** | Inbound only (Sentora reads from S1; does not write) |
| **Failure handling** | Fail-fast if token missing; checkpoint-based resume on API errors |
| **SLA dependency** | Medium — sync failure does not affect read access to cached data |
| **Risk score** | 1.8 (external dependency; critical for data freshness) |

**Mitigation:**
- Cached data remains available during S1 outages
- Checkpoint-based sync resume prevents full re-sync after partial failure
- Rate limiting prevents Sentora from being blocked by S1

### 6.2 Identity Providers (OIDC / SAML)

| Aspect | Detail |
|--------|--------|
| **Service** | Configured OIDC or SAML identity provider |
| **Purpose** | Single sign-on authentication |
| **Data classification** | Restricted (client secrets, SP keys), Confidential (user claims) |
| **Failure handling** | Local authentication (email/password) remains available as fallback |
| **Risk score** | 1.6 (optional integration; local auth as fallback) |

---

## 7. Container Base Images

| Image | Source | Purpose | Update Strategy |
|-------|--------|---------|-----------------|
| `python:3.12-slim` | Docker Hub (official) | Backend runtime | Monthly check for security updates |
| `node:lts-slim` | Docker Hub (official) | Frontend build | Monthly check for security updates |
| `mongo:7` | Docker Hub (official) | Database | Monitor for security patches |

**Image Security:**
- Multi-stage builds reduce attack surface (no build tools in runtime image)
- Non-root execution (`apprunner`, uid 1001)
- Pinned base image tags (not `latest`)
- Image scanning recommended before production deployment

---

## 8. Vulnerability Management

### 8.1 Automated Scanning

| Tool | Scope | Frequency | Integration |
|------|-------|-----------|-------------|
| `pip-audit` | Python dependencies | Every CI run | GitHub Actions pipeline |
| `npm audit` | Node.js dependencies | Every CI run | GitHub Actions pipeline |
| Docker image scanning | Container base images | Per build | CI pipeline (recommended) |

### 8.2 Vulnerability Response

| CVSS Score | Severity | Response Time | Action |
|------------|----------|---------------|--------|
| 9.0-10.0 | Critical | 24 hours | Emergency change process; immediate patch or mitigation |
| 7.0-8.9 | High | 7 days | Priority update; standard change process |
| 4.0-6.9 | Medium | 30 days | Scheduled update in next maintenance window |
| 0.1-3.9 | Low | 90 days | Include in next quarterly dependency update |

### 8.3 Vulnerability Tracking

All identified vulnerabilities are tracked with:

- CVE identifier
- Affected package and version
- CVSS score and severity
- Exploitability in Sentora context
- Remediation status (patched, mitigated, accepted, or not applicable)
- Date identified and date resolved

---

## 9. Dependency Update Strategy

### 9.1 Update Cadence

| Update Type | Frequency | Process |
|-------------|-----------|---------|
| Security patches | Immediate when detected | Emergency or standard change per severity |
| Patch versions (x.x.Z) | Monthly | Standard change; run full test suite |
| Minor versions (x.Y.0) | Quarterly | Normal change; review changelog for breaking changes |
| Major versions (X.0.0) | Evaluate when released | Significant change; ADR if migration required |

### 9.2 Update Procedure

1. **Identify available updates:** `pip list --outdated` / `npm outdated`
2. **Review changelogs:** Check for breaking changes, deprecations, security fixes
3. **Check compatibility:** Verify compatibility with other dependencies
4. **Update in isolation:** Update one dependency at a time for major/minor versions
5. **Run full test suite:** Backend (pytest) + Frontend (vitest) + E2E (Playwright)
6. **Verify security:** Run `pip-audit` / `npm audit` after update
7. **Deploy and monitor:** Standard deployment process with enhanced monitoring

### 9.3 Version Pinning

- **Backend:** Exact versions pinned in `requirements.txt` (e.g., `fastapi==0.135.1`)
- **Frontend:** Version ranges in `package.json` with `package-lock.json` for reproducibility
- **Docker:** Base image tags pinned (not `latest`)
- **Rationale:** Reproducible builds; prevents unexpected breaking changes

---

## 10. New Dependency Evaluation

### 10.1 Evaluation Checklist

Before adding any new dependency:

- [ ] **Necessity:** Can the functionality be implemented without the dependency?
- [ ] **Alternatives:** Were at least 2 alternatives compared?
- [ ] **License:** Is the license compatible with AGPL-3.0?
- [ ] **Security:** Does `pip-audit` / `npm audit` report any CVEs?
- [ ] **Maintenance:** Was the last release within 12 months?
- [ ] **Community:** Does the package have a healthy contributor base?
- [ ] **Dependencies:** What is the transitive dependency count?
- [ ] **Size:** Is the package size reasonable for the functionality provided?
- [ ] **History:** Has the package been previously removed for risk reasons?
- [ ] **Testing:** Has the package been tested with our existing dependency set?

### 10.2 Approval Requirements

| Risk Score | Approver |
|------------|----------|
| 1.0-1.5 (Low) | 1 PR reviewer |
| 1.6-2.2 (Medium) | 2 PR reviewers + security review |
| 2.3-3.0 (High) | 2 PR reviewers + security review + ADR required |

---

## 11. Vendor Offboarding

When removing a dependency or vendor integration:

1. Identify all code references to the dependency
2. Implement replacement (if needed) before removal
3. Update tests to cover replacement implementation
4. Remove dependency from `requirements.txt` / `package.json`
5. Verify no transitive dependencies on the removed package remain
6. Run full test suite
7. Update this document to reflect the removal
8. Document in project memory if the removal was for security/maintenance reasons

---

## 12. Compliance Mapping

| Requirement | Framework | Control |
|-------------|-----------|---------|
| Vendor risk management | SOC 2 CC9.2 | This policy, Sections 3-6 |
| Supply chain security | ISO 27001 A.5.22 | Section 6 (S1 integration) |
| Vulnerability management | ISO 27001 A.8.8 | Section 8 |
| Secure development | ISO 27001 A.8.25 | Sections 9-10 |
| Threat intelligence | ISO 27001 A.5.7 | Section 8.1 (automated scanning) |

---

*This policy is reviewed semi-annually or when significant dependency changes occur.
The dependency inventory (Sections 4-7) is verified quarterly against actual
`requirements.txt` and `package.json` contents.*
