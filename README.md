# Sentora

> Multi-EDR endpoint compliance monitoring platform.
> Turns raw agent inventory into audit-ready evidence across SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA, ISO 27001, NIST CSF 2.0, NIS2, and CIS Controls v8.

[![CI](https://github.com/gweber/sentora/actions/workflows/ci.yml/badge.svg)](https://github.com/gweber/sentora/actions/workflows/ci.yml)
[![Security Scan](https://github.com/gweber/sentora/actions/workflows/security-scan.yml/badge.svg)](https://github.com/gweber/sentora/actions/workflows/security-scan.yml)
[![CodeQL](https://github.com/gweber/sentora/actions/workflows/codeql.yml/badge.svg)](https://github.com/gweber/sentora/actions/workflows/codeql.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](docs/deployment/docker.md)

---

<!-- TODO: Screenshot of the compliance dashboard with score cards, enforcement status, and violations -->
<p align="center">
  <img src="docs/assets/dashboard-screenshot.png" alt="Sentora Dashboard" width="800">
</p>

---

## What is Sentora?

Sentora connects to your EDR management console (SentinelOne and CrowdStrike Falcon today, Defender next), pulls the complete application inventory across your agent fleet, and normalizes it using deterministic fingerprint-based classification. On top of that normalized inventory, it continuously monitors compliance posture across SOC 2 Type II, PCI DSS 4.0.1, HIPAA, BSI IT-Grundschutz, DORA, ISO 27001, NIST CSF 2.0, NIS2, and CIS Controls v8 — 142 controls in total. Enforcement rules let you define which software is required, forbidden, or allowed on which endpoints, with violations surfaced in a unified feed and pushed via webhooks. Every action is recorded in a forensic audit trail backed by a SHA-256 hash-chain that is cryptographically tamper-evident, exportable to cold storage, and verifiable with an air-gapped CLI tool.

---

## Highlights

**Compliance Monitoring** — Continuous posture monitoring across SOC 2 Type II, PCI DSS 4.0.1, HIPAA Security Rule, BSI IT-Grundschutz, and DORA. 81 pre-built controls across 11 check types, evaluated automatically after every sync. Unified violations feed with CSV export for auditor delivery.

**Enforcement Rules** — Define software policies as Required, Forbidden, or Allowlist. Scope rules to specific groups or agent tags. Webhook alerts fire on every new violation for immediate PSA/ITSM integration.

**Software Fingerprinting** — TF-IDF-based marker suggestions and discriminative lift scoring for automatic fingerprint proposals across all groups. Hierarchical taxonomy, deterministic scoring, human-readable confidence signals. No black-box ML.

**Forensic Audit Trail** — SHA-256 hash-chain with epoch-based segmentation, cold-storage export, and an air-gapped CLI verification tool. Every modification or deletion of an audit entry is cryptographically detectable.

**Enterprise Authentication** — Server-side sessions with immediate revocation, JWT access/refresh token rotation with family-based theft detection, RBAC (super_admin / admin / analyst / viewer), TOTP MFA, OIDC & SAML SSO, password policy with breach checking, account lifecycle management. Credential separation keeps profile and auth data in distinct collections.

**Integration Ready** — API-key authentication with granular scopes, per-key rate limiting, and key rotation. HMAC-signed webhook events for compliance, enforcement, sync, and audit chain events. Docker-first deployment with multi-tenant database-per-tenant isolation.

---

## The Problem

Your EDR console shows thousands of raw application entries with inconsistent naming across OS versions and locales. Sentora normalizes, classifies, and audits them automatically.

Auditors need evidence that only approved software runs on regulated endpoints. Sentora generates that evidence continuously — not once a quarter from a manually cleaned spreadsheet.

You need to prove compliance across SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, or DORA. Sentora monitors 142 controls after every sync and surfaces violations the moment they occur.

---

## Quick Start

### Prerequisites

| Requirement                           | Version                          |
| ------------------------------------- | -------------------------------- |
| Docker                                | 24+                              |
| Docker Compose                        | v2 (bundled with Docker Desktop) |
| EDR console access (SentinelOne)      | Any supported version            |
| EDR API token                         | Read-only scope is sufficient    |

### Deploy

```bash
# 1. Clone the repository
git clone https://github.com/gweber/sentora.git
cd sentora

# 2. Copy and edit the environment file
cp .env.example .env
#    Set S1_BASE_URL and S1_API_TOKEN in .env

# 3. Build and start all services
docker compose up -d

# 4. Verify all containers are healthy
docker compose ps

# 5. Open the UI and create your first admin account
open http://localhost:5002
```

The backend API is available at `http://localhost:5002/api/v1/`. Interactive API docs (Swagger UI) are at `http://localhost:5002/api/docs` (development mode only). For next steps, see the [Quick Start Guide](docs/guides/quickstart.md).

### Local Development

```bash
# Backend (port 5002, hot-reload)
cd backend && uvicorn main:app --reload --port 5002

# Frontend (port 5003, Vite dev server, proxies /api to 5002)
cd frontend && npm run dev

# Tests
cd backend && pytest

# Lint / type-check
cd backend && ruff check .
cd frontend && npm run typecheck
```

---

## Feature Reference

| Category       | Features                                                                                              |
| -------------- | ----------------------------------------------------------------------------------------------------- |
| Compliance     | SOC 2 Type II, PCI DSS 4.0.1, HIPAA, BSI IT-Grundschutz, DORA, ISO 27001 (142 controls, 11 check types) |
| Enforcement    | Required / Forbidden / Allowlist rules, scoped by group and tag                                       |
| Fingerprinting | TF-IDF suggestions, lift-based auto-proposer, hierarchical taxonomy                                   |
| Audit          | SHA-256 hash-chain, epoch segmentation, air-gapped CLI verifier, cold-storage export                  |
| Auth           | JWT + refresh rotation, OIDC, SAML, TOTP, RBAC, server-side sessions, credential separation, API keys |
| Integration    | Webhooks (HMAC-signed), API-key auth with scopes, Docker-first deployment                             |
| Data Sources   | SentinelOne (5-phase sync, cursor pagination, checkpoint-resume)                                      |
| Library        | NIST CPE, MITRE ATT&CK, Chocolatey, Homebrew fingerprint ingestion                                    |

---

## Architecture

Sentora is built on Python 3.12 / FastAPI for the backend, Vue 3 / TypeScript / Tailwind v4 for the frontend, and MongoDB 7 for persistence. The backend follows domain-driven design with 12 bounded contexts, each owning its router, service layer, and repository. The compliance module uses CQRS; other domains use a straightforward service-layer pattern. Multi-tenant deployments use database-per-tenant isolation.

For the full architecture including C4 diagrams, see [Architecture Overview](docs/architecture/overview.md).

---

## Use Cases

**Regulatory Compliance** — Regulated industries (finance, healthcare, critical infrastructure) must prove endpoint software compliance. Sentora automates evidence collection across SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA, ISO 27001, NIST CSF 2.0, NIS2, and CIS Controls v8, reducing manual audit preparation from weeks to minutes.

**BSI IT-Grundschutz** — German organizations subject to BSI IT-Grundschutz can leverage Sentora's 16 automated controls for endpoint software compliance — a capability not available in general-purpose GRC tools.

**OT/ICS Security** — Fingerprint known-good OT software (SCADA HMIs, engineering workstations, historian clients) and immediately surface any endpoint running software outside the approved set.

**IT Asset Management** — Replace spreadsheet-based software registers with a live, queryable asset register that updates automatically on each scheduled sync.

**Shadow IT Detection** — Applications that fail to match any known fingerprint are flagged as unclassifiable and surfaced for triage, escalation, or promotion to the fingerprint library.

---

## Demo Mode

Explore the UI without a SentinelOne connection by seeding the database with realistic demo data:

```bash
# Seed demo data (requires an admin account)
curl -X POST http://localhost:5002/api/v1/demo/seed \
  -H "Authorization: Bearer <admin-token>"

# Clear demo data when done
curl -X DELETE http://localhost:5002/api/v1/demo/seed \
  -H "Authorization: Bearer <admin-token>"
```

Demo data includes 3 sites, 6 groups, 135 agents with realistic hostnames and OS types, ~1,000 installed applications with distinct per-group profiles, fingerprints, and classification results.

---

## Documentation

| Document                                                          | Contents                                                                                     |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [CHANGELOG](CHANGELOG.md)                                         | Version history and unreleased changes                                                       |
| [TESTING](TESTING.md)                                             | Testing philosophy, conventions, coverage gates, and how to run the suite                    |
| [SECURITY](SECURITY.md)                                           | Responsible disclosure policy, data classification, and security design                      |
| [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md)                             | Contributor Covenant v2.1 community standards                                                |
| [CONTRIBUTING](docs/contributing/CONTRIBUTING.md)                 | Development setup, branch naming, commit conventions, PR process, code style                 |
| **Architecture**                                                  |                                                                                              |
| [Architecture Overview](docs/architecture/overview.md)            | C4 system context, container, and component diagrams                                         |
| [Data Flow](docs/architecture/data-flow.md)                       | Sync flow, classification flow, WebSocket lifecycle                                          |
| [Domain Model](docs/architecture/domain-model.md)                 | Entity relationships and cross-context policies                                              |
| [Data Model](docs/data-model.md)                                  | Complete MongoDB collection definitions with fields and indexes                              |
| [ADRs](docs/adr/)                                                 | 29 Architecture Decision Records                                                                 |
| **Deployment**                                                    |                                                                                              |
| [Docker](docs/deployment/docker.md)                               | Docker Compose quick start and production hardening                                          |
| [Environment Variables](docs/deployment/environment-variables.md) | Complete `.env` reference with defaults and descriptions                                     |
| [High Availability](docs/deployment/high-availability.md)         | MongoDB replica set configuration and failover                                               |
| [Migrations](docs/deployment/migrations.md)                       | Schema evolution strategy, index management, rollback                                        |
| **Guides**                                                        |                                                                                              |
| [Quick Start](docs/guides/quickstart.md)                          | 10-step getting started guide                                                                |
| [First Fingerprint](docs/guides/first-fingerprint.md)             | Walkthrough building a fingerprint with OT/SCADA example                                     |
| [Interpreting Results](docs/guides/interpreting-results.md)       | Classification verdict definitions and scoring                                               |
| [Scaling](docs/guides/scaling.md)                                 | Guidance for large fleets (10k+ agents)                                                      |
| [Ingestion Sources](docs/guides/ingestion-sources.md)             | NIST CPE, MITRE, Chocolatey, Homebrew library adapters                                       |
| **Compliance & Security**                                         |                                                                                              |
| [Compliance Monitoring](docs/COMPLIANCE.md)                       | SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA monitoring                                   |
| [Compliance Handbook](docs/COMPLIANCE_HANDBOOK.md)                | Operator reference: control details, configuration, troubleshooting                          |
| [Enforcement](docs/ENFORCEMENT.md)                                | Required / Forbidden / Allowlist software policy rules                                       |
| [Audit Chain](docs/security/audit-chain.md)                       | Forensic hash-chain architecture, verification, and threat model                             |
| [Audit Chain API](docs/api/audit-chain.md)                        | REST API and CLI tool reference for audit chain                                              |
| [Webhook Events](docs/api/webhooks.md)                            | Complete webhook event catalog with payload schemas                                          |
| [Threat Model](docs/security/threat-model.md)                     | Threat assessment and mitigation strategies                                                  |
| [Troubleshooting](docs/troubleshooting.md)                        | Common issues and solutions                                                                  |

---

## Roadmap

### Shipped

- [x] SentinelOne API sync — full / incremental / resume modes with cursor watermarks
- [x] Real-time WebSocket progress reporting
- [x] Scheduled background refresh with hot-reloadable interval
- [x] Fingerprint editor with TF-IDF suggestions and discriminative-lift auto-proposer
- [x] Classification engine — four-verdict model
- [x] Taxonomy category tree with seed data
- [x] Dashboard with fleet health metrics
- [x] Comprehensive audit log
- [x] Docker Compose single-command deployment
- [x] 85%+ backend test coverage
- [x] Enterprise authentication — JWT, refresh rotation, TOTP 2FA, OIDC, SAML, RBAC
- [x] Inbound API rate limiting
- [x] Fingerprint library with public source ingestion (NIST CPE, MITRE, Chocolatey, Homebrew)
- [x] Webhook notifications (HMAC-signed)
- [x] Multi-tenant deployment with database-per-tenant isolation
- [x] Forensic audit hash-chain with air-gapped CLI verifier
- [x] Compliance monitoring — SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA (142 controls)
- [x] Enforcement rules — Required / Forbidden / Allowlist
- [x] API-key authentication with granular scopes and key rotation

### Planned

- [ ] CrowdStrike Falcon connector
- [ ] Microsoft Defender for Endpoint connector
- [ ] PDF compliance reports with white-label branding
- [x] ISO/IEC 27001:2022 framework support (16 Annex A controls)
- [x] NIST CSF 2.0 framework support (15 controls)
- [x] NIS2 (EU 2022/2555) framework support (13 controls)
- [x] CIS Controls v8 framework support (14 safeguards)
- [ ] Scheduled compliance report delivery (email/webhook)
- [ ] CLI tool for CI/CD integration (`sentora-cli`)
- [ ] SCIM user provisioning

---

## Contributing

Contributions are welcome. Please read the [Code of Conduct](CODE_OF_CONDUCT.md) before opening an issue or pull request.

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-feature`).
3. Follow the conventions in [TESTING.md](TESTING.md) — all new logic must have tests.
4. Run `ruff check .` before pushing.
5. Open a pull request against `main` with a clear description of the change and why it is needed.

For significant changes, please open an issue first to discuss the approach.

---

## Security

Please do not file public GitHub issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

---

## License

This project is dual-licensed:

- **Open Source** — [GNU AGPL-3.0](LICENSE) for open-source use. You may use, modify, and distribute this software under the terms of the AGPL. If you modify Sentora and provide it as a network service, you must make your modified source code available.

- **Commercial** — A commercial license is available for organisations that cannot comply with the AGPL (e.g., proprietary SaaS deployments, closed-source integrations, or OEM embedding). See [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) for details.

© 2025–2026 Guenter Weber webersheim@gmail.com . All rights reserved.
