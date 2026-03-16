# Sentora — Architecture Decision Records

This directory contains all Architecture Decision Records (ADRs) for the Sentora project.
ADRs capture the significant technical decisions made during design and development, along with
the context and consequences of each decision.

## Index

| ADR                                                     | Title                                   | Status     | Date       | Summary                                                                                                   |
| ------------------------------------------------------- | --------------------------------------- | ---------- | ---------- | --------------------------------------------------------------------------------------------------------- |
| [0001](0001-use-mongodb-over-postgresql.md)             | Use MongoDB over PostgreSQL             | Accepted   | 2026-03-15 | Document-oriented storage with Motor async driver for agent and app data                                  |
| [0002](0002-cqrs-without-event-sourcing.md)             | CQRS Without Event Sourcing             | Accepted   | 2026-03-15 | Separate command/query paths; classification is a disposable read-side projection                         |
| [0003](0003-tfidf-for-software-fingerprinting.md)       | TF-IDF for Software Fingerprinting      | Accepted   | 2026-03-15 | TF-IDF-inspired scoring to surface characteristic apps per group                                          |
| [0004](0004-glob-patterns-over-exact-match.md)          | Glob Patterns over Exact Match          | Accepted   | 2026-03-15 | Glob patterns matched against normalized names to tolerate version and locale variants                    |
| [0005](0005-denormalize-group-names.md)                 | Denormalize Group Names                 | Accepted   | 2026-03-15 | Store group_name alongside group_id to avoid per-render lookups in MongoDB                                |
| [0006](0006-application-name-normalization-strategy.md) | Application Name Normalization Strategy | Accepted   | 2026-03-15 | Two-field strategy: original name preserved, normalized_name used for matching                            |
| [0007](0007-classification-as-disposable-read-model.md) | Classification as Disposable Read Model | Accepted   | 2026-03-15 | Full recomputation on any trigger; results stored separately from source data                             |
| [0008](0008-websocket-for-sync-progress.md)             | WebSocket for Sync Progress             | Accepted   | 2026-03-15 | WebSocket endpoint pushes real-time sync progress events to connected clients                             |
| [0009](0009-seed-taxonomy-with-user-extensions.md)      | Seed Taxonomy with User Extensions      | Accepted   | 2026-03-15 | Curated YAML seed of 100+ industrial software entries; users extend at runtime                            |
| [0010](0010-no-authentication-in-v1.md)                 | No Authentication in v1                 | Superseded | 2026-03-15 | Superseded by ADR-0018 (JWT + RBAC) and ADR-0022 (API keys)                                               |
| [0011](0011-error-hierarchy-over-http-exceptions.md)    | Error Hierarchy over HTTP Exceptions    | Accepted   | 2026-03-15 | Domain error hierarchy mapped to HTTP by a global handler; domain code stays clean                        |
| [0012](0012-weight-based-marker-scoring.md)             | Weight-Based Marker Scoring             | Accepted   | 2026-03-15 | Markers carry 0.0-1.0 weights; score = sum(matched weights) / sum(all weights)                            |
| [0013](0013-fingerprint-library-with-subscriptions.md)  | Fingerprint Library with Subscriptions  | Accepted   | 2026-03-15 | Shared fingerprint templates with subscription-based marker distribution and public source ingestion      |
| [0014](0014-mongodb-replica-set-support.md)             | MongoDB Replica Set Support             | Accepted   | 2026-03-15 | Configurable replica set connections with read preference, write concern, and health reporting            |
| [0015](0015-horizontal-scaling.md)                      | Horizontal Scaling (Multi-Worker)       | Accepted   | 2026-03-15 | Leader election, pub/sub, and enhanced distributed locks for multi-worker deployments                     |
| [0016](0016-soc2-iso27001-compliance.md)                | SOC 2 / ISO 27001 Compliance            | Accepted   | 2026-03-15 | Comprehensive compliance documentation suite mapping controls to SOC 2 and ISO 27001                      |
| [0017](0017-dual-deployment-mode.md)                    | Dual Deployment Mode (On-Prem / SaaS)   | Accepted   | 2026-03-15 | Single codebase runtime switch between on-prem single-tenant and SaaS multi-tenant modes                  |
| [0018](0018-jwt-authentication-with-rbac.md)            | JWT Authentication with RBAC            | Accepted   | 2026-03-15 | JWT + refresh rotation, four-role RBAC, TOTP 2FA, OIDC/SAML SSO; supersedes ADR-0010                      |
| [0019](0019-compliance-monitoring-engine.md)            | Compliance Monitoring Engine            | Accepted   | 2026-03-15 | Built-in compliance engine with 61 controls across 4 frameworks, automated checks, and evidence snapshots |
| [0020](0020-enforcement-rules-engine.md)                | Enforcement Rules Engine                | Accepted   | 2026-03-15 | Taxonomy-anchored software policy enforcement with Required/Forbidden/Allowlist rule types                |
| [0021](0021-enterprise-auth-hardening.md)               | Enterprise Auth Hardening               | Accepted   | 2026-03-15 | Server-side sessions, account lifecycle, password policy, token hardening, anomaly detection              |
| [0021-forensic](0021-forensic-audit-hash-chain.md)      | Forensic Audit Hash-Chain               | Accepted   | 2026-03-15 | SHA-256 linked audit entries with epoch segmentation for tamper detection                                 |
| [0022](0022-api-key-authentication.md)                  | API Key Authentication                  | Accepted   | 2026-03-15 | Tenant-scoped API keys for external integrations with scopes, rate limiting, and rotation                 |

## Format

All ADRs follow the Michael Nygard format: Context, Decision, Consequences (Positive / Negative / Risks), and Alternatives Considered.

## Status Values

- **Proposed** — under discussion, not yet implemented
- **Accepted** — approved and active
- **Deprecated** — superseded but retained for history
- **Superseded** — replaced by a later decision
