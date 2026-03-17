# Sentora — Feature & Benefit Overview

## Elevator Pitch

Sentora is the multi-EDR endpoint compliance platform that transforms raw agent and application data from EDR platforms (SentinelOne, CrowdStrike, Defender) into actionable compliance intelligence — covering SOC 2, PCI DSS 4.0, HIPAA, BSI IT-Grundschutz, DORA, ISO 27001, NIST CSF 2.0, NIS2, and CIS Controls v8 out of the box. Instead of manually exporting spreadsheets and mapping controls, security teams get real-time compliance scores, automated violation detection, and audit-ready evidence — across fleets of 1,000 to 150,000+ endpoints.

---

## Core Platform

### 5-Phase Sync Pipeline

**What it does:**
A production-proven ingestion engine that synchronizes your entire EDR tenant — sites, groups, agents, installed applications, and tags — through five independent, parallelizable phases with checkpoint-based resume.

**Customer benefit:**

- Handles 100,000+ agents without manual data exports or CSV juggling
- Cursor-based pagination with checkpoint persistence: if a sync fails mid-way, it resumes from the last checkpoint — no re-syncing the entire fleet
- Real-time WebSocket progress reporting: your team sees sync status live in the dashboard, not in a background email 30 minutes later
- Configurable scheduling (including weekly full sync) ensures data is always current without manual intervention

### Multi-Tenant Architecture

**What it does:**
Database-per-tenant isolation with distributed locking and leader election for multi-worker deployments. Each tenant gets a fully separate MongoDB database.

**Customer benefit:**

- **Data isolation guarantee**: Tenant A never sees Tenant B's data — not through a row-level filter, but through physically separate databases
- **MSSPs and holding structures** can manage multiple EDR tenants from a single Sentora instance
- Distributed locks ensure that concurrent workers never produce duplicate syncs or conflicting compliance evaluations
- Scale horizontally by adding workers; leader election handles coordination automatically

### Authentication & Access Control

**What it does:**
Full enterprise auth stack: JWT with 15-minute access tokens and 7-day refresh tokens (family-tracked for theft detection), OIDC (Okta, Azure AD, Keycloak), SAML, TOTP-based 2FA, and API key authentication with granular scopes.

**Customer benefit:**

- **SSO integration**: Users authenticate via your existing identity provider — no separate password to manage
- **TOTP 2FA**: Adds a second factor for local accounts, with QR-code provisioning and 6-digit verification
- **4 RBAC roles** (Super Admin, Admin, Analyst, Viewer) let you enforce least-privilege access across your compliance team
- **API keys with scopes**: Automate workflows (CI/CD, SIEM integration) without exposing user credentials
- Password security includes bcrypt hashing, breach checking via HaveIBeenPwned (k-Anonymity), password history enforcement, and account lockout
- Server-side session tracking with immediate revocation — a deactivated user loses access instantly, not at token expiry

---

## Software Intelligence

### Fingerprint Engine (TF-IDF + Lift Scoring)

**What it does:**
A statistical engine that analyzes which applications are characteristic for each agent group. It uses TF-IDF-based matching and lift scoring (how much more likely an app appears in a group vs. the fleet average) to generate fingerprint proposals automatically.

**Customer benefit:**

- **Automatic discovery**: Instead of manually defining "Group X should have App Y", the engine proposes discriminative markers — e.g., "agents in the Finance group are 12× more likely to have Bloomberg Terminal than the fleet average"
- **Configurable thresholds**: Coverage minimum (≥60%), outside maximum (<25%), lift minimum (≥2.0×), top-K proposals (10 per group) — tunable to your fleet's characteristics
- **Glob pattern matching**: Markers use wildcards (`*`, `?`) for flexible app name matching, with weighted scoring (0.1–2.0 per marker)
- **Proposal workflow**: Machine-generated suggestions flow through a pending → applied/dismissed workflow, keeping humans in the loop
- Result: You go from "we have 50,000 apps installed across 10,000 agents" to "here are the 10 most characteristic apps per group" in minutes, not weeks

### Classification Engine

**What it does:**
Classifies every installed application on every endpoint using fingerprint matches, library lookups, and anomaly detection. Produces verdicts (matched, partial, unmatched) with confidence scores.

**Customer benefit:**

- **Visibility into shadow IT**: Unclassified or anomalous applications surface automatically — you see what doesn't belong
- **Anomaly detection**: Flags applications that appear where they shouldn't, based on statistical group profiles
- **Confidence scoring**: Match scores (≥0.7 = matched, 0.4–0.7 = partial, <0.4 = unmatched) let you prioritize review effort on borderline cases
- Classification results are the foundation for compliance checks and enforcement rules — one classification run feeds both modules

### Library System

**What it does:**
Ingests software definitions from five authoritative sources: NIST CPE (NVD), MITRE ATT&CK, Chocolatey, Homebrew Core, and Homebrew Cask. Each source provides normalized app names, glob patterns, and version metadata.

**Customer benefit:**

- **NIST CPE**: Map installed software to official CPE identifiers — the same identifiers used in vulnerability databases (NVD/CVE)
- **MITRE ATT&CK**: Detect known threat actor tools and malware on endpoints using MITRE's software catalog
- **Chocolatey + Homebrew**: Match applications against the two largest platform-specific package registries (Windows and macOS)
- **No manual data entry**: Library entries are ingested with checkpoint recovery and automatic normalization — your team doesn't maintain a spreadsheet of "known good" software
- Library matches feed directly into classification and compliance checks, closing the loop between "what's installed" and "what's allowed"

---

## Compliance Module

### 5 Frameworks, 81 Controls, 10 Check Types

**What it does:**
Automated compliance evaluation against five industry frameworks, with 81 pre-built controls and 10 distinct check types — all evaluated against live EDR data.

| Framework           | Controls | Focus                                                  |
| ------------------- | -------- | ------------------------------------------------------ |
| SOC 2 Type II       | 15       | Security, availability, integrity, confidentiality     |
| PCI DSS 4.0.1       | 15       | Malware protection, patch management, secure software  |
| HIPAA Security Rule | 15       | Required & addressable safeguards                      |
| BSI IT-Grundschutz  | 16       | German/DACH regulatory standard (3 requirement levels) |
| DORA                | 20       | EU financial entity digital operational resilience     |

**10 Check Types:**

| Check Type                | What It Evaluates                                              |
| ------------------------- | -------------------------------------------------------------- |
| `prohibited_app`          | Blacklisted software present on endpoints                      |
| `required_app`            | Mandatory software missing from endpoints                      |
| `agent_version`           | EDR agent below minimum version                                |
| `agent_online`            | Agents unreachable or offline                                  |
| `app_version`             | Specific application below required version                    |
| `sync_freshness`          | Data older than acceptable threshold                           |
| `classification_coverage` | Percentage of classified vs. total applications                |
| `unclassified_threshold`  | Too many unknown applications on an endpoint                   |
| `delta_detection`         | Unauthorized software changes since last baseline              |
| `custom_app_presence`     | Custom application requirements (e.g., backup agent installed) |

**Customer benefit:**

- **Audit preparation in hours, not weeks**: Run all checks across your fleet, get a framework-level compliance score, and drill down to individual control violations
- **Continuous compliance**: Checks run automatically after every sync — you don't find out you're non-compliant the day before the audit
- **Evidence-ready**: Each violation includes the agent hostname, the specific check that failed, the violation detail, and a remediation hint
- **Custom controls**: Extend built-in frameworks with tenant-specific control definitions
- **Scoping**: Apply controls to specific groups and/or tags — not every control applies to every endpoint

### Framework Dashboard & Score Cards

**What it does:**
A per-framework dashboard showing the overall compliance score (% of passing controls), individual control status (pass/fail/warning/error), and a unified violations feed with filtering and CSV export.

**Customer benefit:**

- **Executive reporting**: One number per framework — "We are 87% compliant with SOC 2" — with drill-down for the audit team
- **Control-level detail**: Each control shows its current status, severity, last check time, and all associated violations
- **Unified violations view**: Compliance and enforcement violations in a single, filterable feed — no switching between modules to get the full picture
- **Trend visibility**: Track compliance posture over time, not just at audit snapshots
- **CSV export**: Download violations for external reporting or SIEM ingestion

### CQRS Backend Architecture

**What it does:**
Command-Query Responsibility Separation: compliance check execution (commands) and result reads (queries) are separated into distinct code paths. Classification results are treated as disposable projections, recomputed deterministically on demand.

**Customer benefit:**

- **Performance**: Read-heavy dashboard queries don't compete with write-heavy check execution
- **Consistency**: Results are always derived from current data — no stale cache, no event replay drift
- **Simplicity**: No event sourcing overhead; the system is deterministic and fully testable

---

## Enforcement Module

### 3 Rule Types with Taxonomy-Based Matching

**What it does:**
Policy enforcement through three rule types — **Required** (software must be installed), **Forbidden** (software must not be installed), and **Allowlist** (only whitelisted software permitted) — using the fingerprint engine's taxonomy-based pattern matching.

**Customer benefit:**

- **Forbidden rules**: "No cryptocurrency miners on any endpoint" — evaluated automatically after every sync, with violations surfaced immediately
- **Required rules**: "Every endpoint in PCI scope must have the DLP agent installed" — missing software flagged per-agent
- **Allowlist rules**: "Only approved software in the secure enclave group" — anything not on the list is a violation
- **Taxonomy integration**: Rules reference taxonomy categories, not raw app names — when a new version of a forbidden app appears with a slightly different name, the pattern still matches
- **Scoping**: Rules can target specific groups and/or tags — apply different policies to different parts of your fleet
- **Framework labels**: Tag rules with compliance framework references (e.g., "PCI-DSS 5.2.1") for audit traceability
- **Severity levels**: Critical, High, Medium, Low — prioritize remediation effort

### Webhook Events for Violations

**What it does:**
13 webhook event types including `enforcement.violation.new` and `enforcement.violation.resolved`, delivered via HMAC-SHA256 signed HTTP POST to your registered endpoints.

**Customer benefit:**

- **Real-time alerting**: Pipe violations to Slack, PagerDuty, ServiceNow, or your SIEM — the moment a forbidden app appears, your team knows
- **Automated remediation**: Trigger runbooks or orchestration workflows when violations are detected
- **Tamper-proof delivery**: HMAC-SHA256 signing ensures webhook payloads haven't been modified in transit
- **Resilient delivery**: Auto-disable after 10 consecutive failures prevents runaway retry loops

**Full webhook event catalog:**

| Category       | Events                                                                                                                 |
| -------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Sync           | `sync.completed`, `sync.failed`                                                                                        |
| Classification | `classification.completed`, `classification.anomaly_detected`                                                          |
| Enforcement    | `enforcement.check.completed`, `enforcement.violation.new`, `enforcement.violation.resolved`                           |
| Compliance     | `compliance.check.completed`, `compliance.violation.new`, `compliance.violation.resolved`, `compliance.score.degraded` |
| Audit          | `audit.chain.integrity_failure`                                                                                        |

---

## Integration & UX

### Unified Violations View

**What it does:**
A single view that aggregates violations from both the compliance module and the enforcement module, with filtering by source (compliance/enforcement), severity, and pagination.

**Customer benefit:**

- **One place to look**: Your SOC analyst doesn't need to check two different screens — all violations, regardless of source, appear in one filterable feed
- **Cross-module correlation**: See if an enforcement violation (forbidden app) also triggers a compliance violation (PCI control failure) for the same agent
- **Export**: Download the unified feed as CSV for external processing or reporting

### Shared Components & Pickers

**What it does:**
Reusable UI components — Group Picker, Tag Picker, Taxonomy Category Picker, Category Sidebar — used consistently across compliance, enforcement, and fingerprint modules.

**Customer benefit:**

- **Consistent experience**: Selecting scope (groups, tags) works the same way everywhere — no learning curve when moving between modules
- **Search and filter**: All pickers support search, multi-select, and display contextual metadata (agent counts, entry counts)

### Real-Time Dashboard & WebSocket Updates

**What it does:**
A main dashboard showing fleet health (OS distribution, machine types, network status), app intelligence metrics, fingerprinting progress, compliance scores, and enforcement violations — updated in real-time via WebSocket.

**Customer benefit:**

- **Live operational view**: Sync progress, compliance check results, and enforcement evaluations stream to the browser in real-time — no manual refresh
- **Automatic reconnection**: WebSocket connections reconnect with exponential backoff; auth failures trigger automatic token refresh
- **Lightweight**: Pure CSS visualizations (no heavy charting library) — the dashboard loads fast even on constrained networks

### In-App Getting Started Guide

**What it does:**
A two-tab onboarding guide: **Tenant Guide** (11 steps from initial settings through compliance) for all users, and **Platform Guide** (6 steps covering multi-tenant management) for super admins. Deployment-aware — SaaS vs. self-hosted surfaces the right content.

**Customer benefit:**

- **Self-service onboarding**: New users follow a structured path from first sync to first compliance report without external documentation
- **Role-appropriate**: Analysts see the tenant workflow; platform admins see tenant management, library sources, and audit configuration
- **Reduces time-to-value**: Guided setup means your team is productive on day one, not after a week of reading docs

### Toast Notifications & Confirmation Dialogs

**What it does:**
System-wide toast notifications (success, error, info) with auto-dismiss, and inline confirmation dialogs for destructive actions (delete rule, remove user, revoke API key).

**Customer benefit:**

- **Immediate feedback**: Every action produces visible confirmation — no wondering "did it work?"
- **Destructive action safety**: Deletions require explicit confirmation, preventing accidental data loss

---

## Enterprise Readiness

### Security Hardening

**What it does:**

| Layer                     | Implementation                                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **HTTP Security Headers** | CSP, HSTS (1 year), X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy               |
| **Rate Limiting**         | Per-IP sliding window (100 req/min global, 5 req/min on login)                                                 |
| **Body Size Limit**       | 10 MB maximum request payload                                                                                  |
| **Input Validation**      | Pydantic v2 strict types on all API endpoints; schema violations rejected at HTTP 422                          |
| **Password Security**     | bcrypt (adaptive salt), HaveIBeenPwned breach checking, password history, account lockout                      |
| **Session Security**      | Server-side tracking, family-based token reuse detection, immediate revocation                                 |
| **API Key Format**        | `sentora_sk_live_` prefix — detectable by GitHub secret scanners                                               |
| **Audit Trail**           | SHA-256 hash-chain with epoch segmentation, tamper detection, cold-storage export, air-gapped CLI verification |
| **Credential Separation** | Profile data and auth credentials stored in distinct collections — credentials never exposed in API responses  |
| **Token Redaction**       | S1 API tokens automatically redacted from all logs                                                             |

**Customer benefit:**

- **Audit-ready security posture**: Security headers, rate limiting, and input validation meet enterprise security review requirements out of the box
- **Forensic audit trail**: The SHA-256 hash-chain provides cryptographic proof that audit logs haven't been tampered with — a requirement for SOC 2 and regulatory audits
- **Breach-aware passwords**: Passwords checked against known breaches before acceptance — reduces credential-stuffing risk

### Test Coverage

**What it does:**
72 test files (23 unit, 41 integration, plus frontend and E2E), enforced 85% backend coverage gate, real MongoDB in tests (no mocks), and security-specific test suites (injection, authorization, audit logging).

**Customer benefit:**

- **Reliability**: 85% coverage minimum enforced in CI — regressions are caught before they reach production
- **Real database testing**: Tests run against actual MongoDB, not mocks — what passes in CI passes in production
- **Security testing**: Dedicated test suites for NoSQL injection, authorization bypass, and audit integrity — security isn't an afterthought

### DevOps & Deployment

**What it does:**

| Capability             | Details                                                                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Container**          | Multi-stage Docker build (Node 22 → Python 3.12-slim), non-root user (UID 1001), resource limits                                           |
| **Health Checks**      | `/health` (liveness), `/health/ready` (readiness with MongoDB check), `/health/replica` (replica set status)                               |
| **HA-Ready**           | Multi-worker mode with distributed locking; configurable via `WORKERS` env var                                                             |
| **CI/CD**              | 8 GitHub Actions gates: pre-commit, backend tests, frontend tests, E2E, pip-audit, bandit SAST, Docker build + Trivy scan, SBOM generation |
| **Observability**      | OpenTelemetry tracing (opt-in), Prometheus metrics endpoint, Loguru structured logging                                                     |
| **Container Security** | Trivy scan for CRITICAL/HIGH CVEs, Alpine-based images with `apk upgrade --no-cache`                                                       |
| **SBOM**               | CycloneDX software bill of materials generated on main branch                                                                              |

**Customer benefit:**

- **Production-ready containers**: Non-root execution, health checks, resource limits, and CVE scanning — meets enterprise container security policies
- **Observable**: Distributed tracing (Jaeger/Datadog/etc.), Prometheus metrics, and structured logging — your ops team can monitor Sentora with existing tooling
- **CI/CD gated**: Every change passes 8 automated quality gates before merge — including security scanning (SAST, dependency audit, container scan)
- **SBOM**: Software Bill of Materials for supply chain transparency — increasingly required by enterprise procurement

### Documentation

**What it does:**
21 Architectural Decision Records (ADRs), module-specific documentation, a comprehensive security policy (SECURITY.md), an authoritative testing standard (TESTING.md, 26 KB), data model documentation (41 KB), quickstart guide, troubleshooting guide, and changelog.

**Customer benefit:**

- **Self-documenting architecture**: ADRs explain not just what was built, but why — your team understands design trade-offs without reverse-engineering the code
- **Onboarding acceleration**: New team members can understand the system through structured documentation, not tribal knowledge
- **Audit evidence**: Security and compliance documentation serves as evidence artifacts for SOC 2 and ISO audits

---

## Differenzierung

### vs. Generic IT Asset Tools (Lansweeper, NinjaOne)

Generic asset tools discover and inventory hardware and software across your network. Sentora doesn't compete on breadth of discovery — it doesn't scan your network for printers or patch Windows updates.

**Where Sentora goes deeper:**

- **Compliance mapping**: Lansweeper shows you what's installed. Sentora tells you whether what's installed complies with SOC 2 CC7.1 or BSI SYS.2.1.A6 — and produces the evidence artifact
- **Software intelligence**: TF-IDF fingerprinting and lift scoring analyze which applications are characteristic for each group — generic asset tools show flat inventories
- **Enforcement policies**: Forbidden/required/allowlist rules with real-time violation webhooks — not just "this app exists" but "this app shouldn't exist and here's who to notify"
- **EDR depth**: Sentora uses the EDR API as its authoritative data source — agent version, online status, group membership, tags — and builds compliance logic on top of it

**Multi-EDR architecture:** Sentora supports multiple EDR platforms through a source adapter pattern. SentinelOne is the first fully implemented adapter. CrowdStrike and Defender are next. The canonical data model ensures all compliance checks, enforcement rules, and reports work source-agnostically.

### vs. Broad GRC Platforms (Drata, Vanta, Sprinto)

GRC platforms manage your entire compliance program: policy management, vendor assessments, employee training tracking, access reviews, cloud posture. Sentora doesn't do any of that.

**Where Sentora is deeper:**

- **Endpoint-level granularity**: GRC platforms check "do you have an EDR?" (yes/no). Sentora checks "is the EDR agent on version ≥23.4, online, on 47,832 of 48,000 endpoints, and are there 3 agents running unauthorized cryptocurrency miners in the Berlin office?"
- **10 specialized check types**: Not just "control passes or fails" but 10 distinct evaluation methods purpose-built for endpoint and application compliance
- **Fingerprint intelligence**: No GRC platform has TF-IDF-based software fingerprinting or statistical anomaly detection at the endpoint level
- **BSI IT-Grundschutz**: Drata and Vanta focus on SOC 2 and ISO 27001. Sentora ships 16 BSI controls mapped to specific building blocks (SYS.2.1, APP.6, OPS.1.1.3) at three requirement levels

**Where Sentora is narrower:**

- No policy document management
- No vendor risk assessment
- No employee training tracking
- No cloud infrastructure posture (AWS, GCP, Azure)
- No access review workflows

**Recommended approach:** Use Sentora alongside your GRC platform. Sentora provides the endpoint compliance evidence that feeds into your broader compliance program.

### vs. Endpoint Security Suites (Qualys, Tanium, Axonius)

These platforms provide vulnerability management, asset discovery, and endpoint visibility across heterogeneous environments.

**How Sentora complements them:**

- **EDR depth over breadth**: While Axonius aggregates data from dozens of sources with shallow integration each, Sentora goes deep on EDR sources — extracting compliance intelligence that requires understanding the EDR data model (groups, tags, agent lifecycle, application inventory)
- **Compliance-first**: Qualys focuses on vulnerabilities (CVEs). Sentora focuses on compliance posture (is the right software installed, is the wrong software absent, is the agent current and online)
- **Software classification**: None of these tools offer TF-IDF fingerprinting with automatic group-level proposal generation
- **Enforcement with taxonomy**: Tanium can enforce policies, but Sentora's taxonomy-based pattern matching means rules adapt to application naming variations automatically

**The honest position:** If you need vulnerability scanning, patch deployment, or cross-platform endpoint management, Sentora is not a replacement. It's the compliance intelligence layer that sits on top of your EDR deployment and answers the question: "Are our endpoints compliant with Framework X — and if not, which ones, why, and how do we fix it?"

---

## BSI IT-Grundschutz — DACH Spotlight

### Why BSI IT-Grundschutz Matters

BSI IT-Grundschutz is the German Federal Office for Information Security's comprehensive methodology for implementing information security management. For organizations in Germany, Austria, and Switzerland, it serves as:

- **Regulatory baseline**: KRITIS operators (critical infrastructure) in Germany are legally required to demonstrate IT security measures — BSI IT-Grundschutz is the accepted methodology
- **Certification path**: BSI IT-Grundschutz certification (ISO 27001 based on IT-Grundschutz) is recognized by German federal and state authorities, and increasingly required in public sector procurement
- **Insurance and liability**: Demonstrating BSI compliance can be relevant for cyber insurance premiums and reducing director liability under NIS2/IT-Sicherheitsgesetz 2.0
- **Customer requirements**: Large German enterprises increasingly require BSI compliance from their suppliers and service providers

### Sentora's 16 BSI Controls

Sentora maps 16 automated controls to specific BSI building blocks across three requirement levels:

**Basis (MUSS — Mandatory)**

| Control ID            | Building Block   | What It Checks                                                 |
| --------------------- | ---------------- | -------------------------------------------------------------- |
| BSI-SYS.2.1.A6        | General Client   | EDR agent installed and active                                 |
| BSI-SYS.2.1.A6-ONLINE | General Client   | Agent reachable and reporting to management console            |
| BSI-APP.6.A1          | General Software | Software inventory completeness (classification coverage ≥70%) |
| BSI-APP.6.A1-SYNC     | General Software | Data freshness — sync completed within acceptable window       |
| BSI-APP.6.A4          | General Software | Delta detection — unauthorized software changes flagged        |
| BSI-OPS.1.1.3.A15-EDR | Patch Management | EDR agent on current version                                   |

**Standard (SOLLTE — Recommended)**

| Control ID       | Building Block   | What It Checks                                      |
| ---------------- | ---------------- | --------------------------------------------------- |
| BSI-SYS.2.1.A3   | General Client   | Auto-update mechanisms active                       |
| BSI-SYS.2.1.A4   | General Client   | Backup software present                             |
| BSI-APP.6.A2     | General Software | Required applications catalog enforced              |
| BSI-APP.6.A5     | General Software | Unused/unauthorized software identified for removal |
| BSI-OPS.1.1.3.A1 | Patch Management | Patch management process validated                  |

**Erhöhter Schutzbedarf (Elevated Protection)**

| Control ID                   | Building Block   | What It Checks                                               |
| ---------------------------- | ---------------- | ------------------------------------------------------------ |
| BSI-SYS.2.1.A42              | General Client   | Software allowlist enforced — only approved applications     |
| BSI-SYS.2.1.A42-UNCL         | General Client   | Unclassified application threshold (cap on unknown software) |
| BSI-APP.6.A1 (elevated)      | General Software | Higher classification coverage requirement (≥85%)            |
| Additional elevated controls | Various          | Enhanced protection measures for high-security environments  |

### Why This Is a Differentiator

- **Few endpoint tools automate BSI controls**: Most GRC platforms (Drata, Vanta, Sprinto) focus on SOC 2 and ISO 27001. BSI IT-Grundschutz requires German-specific building block mapping that international platforms rarely implement
- **Building-block granularity**: Sentora maps controls to specific BSI building blocks (SYS.2.1, APP.6, OPS.1.1.3) — not generic "do you have endpoint protection" checkboxes
- **Three requirement levels**: Basis/Standard/Elevated separation reflects the actual BSI methodology — your auditor sees the same structure they expect
- **Automated evidence**: Instead of manually documenting "we have virus protection on our clients" (SYS.2.1.A6), Sentora shows the exact coverage percentage across your fleet, with per-agent detail and historical trend

For DACH organizations undergoing BSI certification or demonstrating KRITIS compliance, Sentora provides automated, continuous evidence for 16 endpoint-related controls — reducing audit preparation from weeks of manual evidence collection to a dashboard view with exportable results.

---

## Typical Use Cases

### 1. CISO Preparing for SOC 2 Audit

**Problem:** The SOC 2 audit is in 6 weeks. The auditor will ask for evidence that endpoints have current EDR agents, no prohibited software, and classified application inventories. Today, this evidence lives in EDR exports, spreadsheets, and tribal knowledge.

**How Sentora solves it:**

- Connect Sentora to your EDR tenant → initial sync completes in minutes
- 15 SOC 2 controls evaluate automatically against live data
- The compliance dashboard shows: "SOC 2: 87% — 13 of 15 controls passing"
- Drill into the 2 failing controls: 47 agents running an outdated EDR version, 12 agents with unclassified applications above threshold
- Export the violations feed as CSV → hand to the ops team for remediation
- Re-run checks after remediation → score updates to 100%

**Result:** Audit evidence generated continuously, not assembled in a panic. The auditor sees real-time compliance posture, not a point-in-time snapshot that's already stale.

### 2. IT-Ops Enforcing Forbidden Software Fleet-Wide

**Problem:** Security policy prohibits cryptocurrency mining software and unauthorized remote access tools. Currently, someone manually searches the EDR console every quarter — and misses installations between checks.

**How Sentora solves it:**

- Create a **Forbidden** enforcement rule targeting the "Cryptocurrency" taxonomy category
- Scope it to all groups (or specific high-risk groups via the Group Picker)
- Set severity to **Critical**
- Register a webhook endpoint pointing to your Slack channel or ServiceNow instance
- Every sync triggers evaluation → the moment a mining tool appears on any agent, `enforcement.violation.new` fires
- The unified violations view shows which agent, which app, which group — with a remediation hint

**Result:** Continuous enforcement instead of quarterly spot-checks. Violations detected in minutes, not months. Webhook integration means the right team is notified immediately.

### 3. Compliance Team Demonstrating BSI IT-Grundschutz Conformity

**Problem:** Your organization is a KRITIS operator in Germany. The BSI auditor needs evidence for IT-Grundschutz building blocks SYS.2.1 (General Client) and APP.6 (General Software). Currently, this evidence is compiled manually from multiple systems.

**How Sentora solves it:**

- The BSI IT-Grundschutz framework is pre-configured with 16 controls mapped to specific building blocks
- Basis-level (MUSS) controls verify: EDR agent active, agent online, software inventory complete, data fresh, no unauthorized changes, EDR version current
- Standard-level (SOLLTE) controls verify: auto-updates active, backup software present, required applications installed, unused software flagged, patch management validated
- The compliance dashboard shows per-control status at each requirement level (Basis/Standard/Elevated)
- Export control results for the auditor — each control references its BSI building block ID

**Result:** 16 BSI controls evaluated automatically against live endpoint data. The auditor sees the same building-block structure they expect, with per-agent evidence and historical compliance trends.

### 4. Security Analyst Investigating Shadow IT

**Problem:** The security team suspects unauthorized software is proliferating across the fleet, but with 80,000 installed applications across 15,000 agents, manual review is impossible.

**How Sentora solves it:**

- The fingerprint engine runs TF-IDF analysis across all groups → generates statistical profiles of expected software per group
- The classification engine flags applications that don't match any fingerprint, library entry, or taxonomy category
- Anomaly detection surfaces applications that appear in groups where they statistically shouldn't exist
- The `unclassified_threshold` compliance check flags agents with too many unknown applications
- The analyst reviews anomalies in the classification view, accepts or dismisses findings, and creates enforcement rules for confirmed violations

**Result:** From 80,000 applications to a prioritized list of statistical anomalies in minutes. Shadow IT detection becomes data-driven, not anecdotal.

### 5. MSSP Managing Multiple Customer Tenants

**Problem:** You're a managed security service provider with 12 EDR customer tenants. Each customer has different compliance requirements (some need SOC 2, others PCI DSS, two need BSI). Today, each customer is managed separately with no unified view.

**How Sentora solves it:**

- Multi-tenant architecture: each customer gets an isolated database — no data leakage between tenants
- Platform-level compliance view aggregates scores across tenants
- Per-tenant compliance configuration: Customer A gets SOC 2 + PCI DSS, Customer B gets BSI IT-Grundschutz only
- API key authentication with tenant scoping enables per-customer automation
- Webhook events fire per-tenant — route each customer's violations to their respective notification channels

**Result:** Unified compliance management across your customer portfolio. One Sentora instance, 12 tenants, each with their own compliance frameworks, enforcement rules, and notification workflows.
