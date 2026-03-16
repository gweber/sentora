# Change Management Policy

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-CM-001                                |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Engineering & Security Team                |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Purpose

This policy defines the change management process for the Sentora platform. It
ensures that all changes to the system are planned, reviewed, tested, and deployed in
a controlled manner to minimize risk to system availability, security, and integrity.

---

## 2. Scope

This policy covers:

- Source code changes (backend and frontend)
- Configuration changes (environment variables, runtime config)
- Infrastructure changes (Docker, MongoDB, deployment topology)
- Dependency updates (Python packages, npm packages)
- Database schema changes (collection structure, indexes)
- Documentation changes affecting operational procedures

---

## 3. Change Categories

| Category | Description | Approval | Examples |
|----------|-------------|----------|----------|
| **Standard** | Pre-approved, low-risk, routine changes | CI pipeline pass + 1 PR reviewer | Bug fixes, documentation updates, minor UI changes |
| **Normal** | Changes requiring review and testing | CI pipeline pass + 2 PR reviewers | New features, API changes, dependency updates |
| **Emergency** | Urgent changes to resolve P1/P2 incidents | IC approval + post-change review | Security patches, critical bug fixes, credential rotation |
| **Significant** | Architectural or high-impact changes | CI pipeline + 2 reviewers + ADR | New domains, auth mechanism changes, database migrations |

---

## 4. Development Lifecycle

### 4.1 Branch Strategy

```
main (production)
  |
  +-- feature/TICKET-description    (new features)
  +-- fix/TICKET-description        (bug fixes)
  +-- hotfix/TICKET-description     (emergency fixes)
  +-- chore/description             (maintenance tasks)
```

| Branch | Base | Merges To | Protection |
|--------|------|-----------|------------|
| `main` | -- | -- | Protected: no direct commits, PR required, CI must pass |
| `feature/*` | `main` | `main` | None (developer branch) |
| `fix/*` | `main` | `main` | None (developer branch) |
| `hotfix/*` | `main` | `main` | Emergency: IC approval, post-merge review |

### 4.2 Development Process

1. **Create branch** from `main` with appropriate prefix
2. **Implement changes** following coding standards:
   - Backend: Python 3.12+, Pydantic DTOs, loguru logging, type hints
   - Frontend: TypeScript strict mode, Vue 3 Composition API, Tailwind v4
3. **Write tests** for all changes:
   - Backend: pytest with coverage (85% gate)
   - Frontend: Vitest for stores/composables (60-70% gate)
   - E2E: Playwright for user-facing flows
4. **Commit** with descriptive messages following conventional commits
5. **Push** and create Pull Request

### 4.3 Code Review Requirements

| Change Category | Reviewers Required | Review Focus |
|----------------|-------------------|--------------|
| Standard | 1 | Correctness, style, test coverage |
| Normal | 2 | Architecture, security, performance, test coverage |
| Emergency | 1 (IC) + post-change review by 2 | Correctness, minimal scope, no regressions |
| Significant | 2 + ADR review | Architecture alignment, security implications, migration plan |

**Review Checklist:**

- [ ] Code follows project conventions (Ruff-clean, typed, DTOs used)
- [ ] Tests added/updated and passing
- [ ] No secrets or credentials in code
- [ ] Input validation via Pydantic models
- [ ] RBAC properly applied to new endpoints
- [ ] Audit logging for security-relevant actions
- [ ] Error handling follows hierarchy pattern (ADR-0011)
- [ ] Documentation updated if API or behavior changes
- [ ] No new dependencies with known vulnerabilities
- [ ] Performance impact considered for data-heavy operations

---

## 5. CI/CD Pipeline

### 5.1 Pipeline Stages

The CI/CD pipeline runs on GitHub Actions for every push and pull request.

| Stage | Tool | Gate | Failure Action |
|-------|------|------|----------------|
| **1. Lint (Backend)** | `ruff check .` | Zero violations | Fix lint errors |
| **2. Type Check (Backend)** | `mypy` | Zero errors | Fix type annotations |
| **3. Type Check (Frontend)** | `vue-tsc --noEmit` | Zero errors | Fix TypeScript errors |
| **4. Unit Tests (Backend)** | `pytest` | All pass, 85% coverage | Fix tests, add coverage |
| **5. Unit Tests (Frontend)** | `vitest run` | All pass, 60-70% coverage | Fix tests, add coverage |
| **6. Security Scan (Backend)** | `pip-audit` | No high/critical CVEs | Update dependencies |
| **7. Security Scan (Frontend)** | `npm audit` | No high/critical CVEs | Update dependencies |
| **8. Docker Build (Backend)** | `docker build -f Dockerfile.backend` | Successful build | Fix Dockerfile or dependencies |
| **9. Docker Build (Frontend)** | `docker build -f Dockerfile.frontend` | Successful build | Fix Dockerfile or dependencies |
| **10. E2E Tests** | `npx playwright test` | Smoke tests pass | Fix E2E failures |

### 5.2 Pipeline Enforcement

- All stages must pass before merge is allowed
- Branch protection on `main` requires CI pass and reviewer approval
- Failed pipelines block merge; no override without IC approval
- Pipeline results visible on the PR for reviewer inspection

### 5.3 Test Coverage Requirements

| Component | Minimum Coverage | Current Coverage | Enforcement |
|-----------|-----------------|-----------------|-------------|
| Backend | 85% | 87.40% | pytest-cov with `--cov-fail-under=85` |
| Frontend Stores | 60% | > 60% | Vitest coverage thresholds in `vitest.config.ts` |
| Frontend Composables | 60% | > 60% | Vitest coverage thresholds |

---

## 6. Architecture Decision Records (ADRs)

### 6.1 When to Write an ADR

An ADR is required for:

- New bounded contexts or domain additions
- Authentication or authorization mechanism changes
- Database schema or index changes
- New middleware or middleware stack changes
- New external integrations or API changes
- Dependency additions or replacements (significant ones)
- Deployment topology changes

### 6.2 ADR Format

All ADRs follow this structure and are stored in `docs/adr/`:

```
# ADR-NNNN: Title

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXXX]

## Context
[Description of the problem and constraints]

## Decision
[What was decided and why]

## Consequences
[Positive and negative impacts of the decision]
```

### 6.3 Current ADR Inventory

| ADR | Title | Status |
|-----|-------|--------|
| 0011 | Error Hierarchy Over HTTP Exceptions | Accepted |
| 0012 | Weight-Based Marker Scoring | Accepted |
| 0013 | Fingerprint Library with Subscriptions | Accepted |
| 0014 | MongoDB Replica Set Support | Accepted |
| 0016 | SOC 2 / ISO 27001 Compliance | Accepted |

---

## 7. Deployment Process

### 7.1 Standard Deployment

| Step | Action | Responsible | Verification |
|------|--------|-------------|-------------|
| 1 | PR merged to `main` | Developer | CI pipeline passed, reviews approved |
| 2 | Build Docker images | CI/CD | Build artifacts created |
| 3 | Tag images with version | CI/CD or operator | Image tagged in registry |
| 4 | Update `docker-compose.yml` if needed | Operator | Config reviewed |
| 5 | Pull new images on target | Operator | `docker compose pull` |
| 6 | Rolling restart | Operator | `docker compose up -d` |
| 7 | Verify health probes | Operator | `/health` = 200, `/health/ready` = 200 |
| 8 | Monitor for 15 minutes | Operator | Prometheus metrics nominal |
| 9 | Update changelog | Developer | `CHANGELOG.md` updated |

### 7.2 Emergency Deployment

For P1/P2 incidents:

1. IC approves the emergency change
2. Hotfix branch created from `main`
3. Minimal fix applied with tests
4. CI pipeline runs (all stages must still pass)
5. Single reviewer (IC) approves PR
6. Merge and deploy immediately
7. Post-deployment monitoring (enhanced, 72 hours)
8. Post-change review within 5 business days by 2 additional reviewers

### 7.3 Rollback Procedure

| Step | Action | Command |
|------|--------|---------|
| 1 | Identify previous known-good image tag | Check deployment log |
| 2 | Update compose to previous tag | Edit `docker-compose.yml` |
| 3 | Stop current containers | `docker compose down` |
| 4 | Start with previous version | `docker compose up -d` |
| 5 | Verify health probes | `curl /health && curl /health/ready` |
| 6 | Verify data integrity | Check audit log hash chain |
| 7 | Investigate root cause | Post-rollback analysis |

---

## 8. Database Change Management

### 8.1 MongoDB Schema Changes

MongoDB is schemaless, but structural changes still require management:

| Change Type | Process | Risk Level |
|-------------|---------|------------|
| New collection | ADR + code change + migration doc | Low |
| New field (additive) | Code change with default value | Low |
| Field rename | Migration script + dual-read period | Medium |
| Field removal | Remove reads first, then field | Medium |
| Index change | ADR + performance testing | Medium |
| Collection removal | Migration script + backup verification | High |

### 8.2 Migration Documentation

All database changes documented in `docs/deployment/migrations.md`:

- What changed and why
- Forward-compatible patterns used
- Rollback procedure
- Data verification steps

---

## 9. Configuration Change Management

### 9.1 Environment Variable Changes

| Step | Action |
|------|--------|
| 1 | Update `.env.example` with new variable and documentation |
| 2 | Document as `[REQUIRED]` or `[OPTIONAL]` with default value |
| 3 | Add startup validation in `backend/main.py` if required |
| 4 | Update `docs/troubleshooting.md` if relevant |
| 5 | Communicate to all deployment operators |

### 9.2 Runtime Configuration Changes

Changes via `domains/config/`:

- All changes logged in audit trail
- Requires admin or super_admin role
- Changes take effect immediately (no restart required)
- Previous values preserved in audit log for rollback reference

---

## 10. Dependency Management

### 10.1 Update Strategy

| Type | Frequency | Process |
|------|-----------|---------|
| Security patches (CVE) | Immediate when detected | Emergency change process |
| Minor version updates | Monthly | Standard change process |
| Major version updates | Quarterly evaluation | Normal change + ADR if breaking |
| New dependencies | As needed | Normal change + security review |

### 10.2 Dependency Review Checklist

Before adding or updating a dependency:

- [ ] Check for known CVEs (`pip-audit` / `npm audit`)
- [ ] Verify the package is actively maintained (last release < 12 months)
- [ ] Review license compatibility (AGPL-3.0 compatible)
- [ ] Assess transitive dependency tree size
- [ ] Check for previously removed vulnerable alternatives (e.g., python-jose, passlib)
- [ ] Pin exact version in `requirements.txt` or `package.json`

---

## 11. Change Audit Trail

All changes are tracked through:

| Source | What It Records |
|--------|----------------|
| Git history | Code changes with author, timestamp, commit message |
| PR records | Review comments, approvals, CI results |
| ADR documents | Architectural decision context and rationale |
| CHANGELOG.md | User-facing changes by version |
| Audit logs | Runtime configuration changes |
| Deployment log | Image versions, deployment timestamps |

---

## 12. Compliance Mapping

| Requirement | Framework | Control |
|-------------|-----------|---------|
| Change management process | SOC 2 CC8.1 | This policy, Sections 3-7 |
| Pre-deployment testing | SOC 2 CC8.2 | Section 5 (CI/CD pipeline) |
| System change management | SOC 2 CC8.3 | Sections 7-9 |
| Secure development lifecycle | ISO 27001 A.8.25 | Sections 4-5 |
| Change management | ISO 27001 A.8.32 | This policy |

---

*This policy is reviewed semi-annually or when the development process changes
significantly. All team members must acknowledge the current version.*
