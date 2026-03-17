# Compliance Monitoring

Sentora monitors endpoint software compliance as part of your broader compliance program. It provides automated evidence collection and continuous monitoring for the endpoint management controls within SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA, and ISO/IEC 27001.

> **Important:** Sentora provides monitoring and evidence, not certification. Full compliance requires additional controls, policies, and assessments beyond Sentora's scope.

---

## Available Frameworks

| Framework | Version | Focus Area | Controls |
|-----------|---------|------------|----------|
| **SOC 2 Type II** | 2024 | AICPA Trust Services Criteria (Security, Availability) | 16 |
| **PCI DSS** | 4.0.1 | Payment Card Industry Data Security | 16 |
| **HIPAA** | 45 CFR 164 | Health Insurance Portability — ePHI safeguards | 16 |
| **BSI IT-Grundschutz** | Edition 2023 | German federal information security standard | 17 |
| **DORA** | EU 2022/2554 | Digital Operational Resilience Act — EU financial entities | 20 |
| **ISO/IEC 27001** | 2022 | International ISMS standard — Annex A technological controls | 16 |
| **NIST CSF 2.0** | 2.0 (2024) | US cybersecurity framework — Identify, Protect, Detect functions | 15 |
| **NIS2** | EU 2022/2555 | EU cybersecurity directive — Article 21 technical measures | 13 |
| **CIS Controls v8** | 8.0 (2021) | Prioritized security controls — Controls 1, 2, 7, 10 safeguards | 14 |

Each framework ships with pre-built controls that can be individually enabled, disabled, or configured per tenant.

---

## Check Types

Every control uses one of 11 check types. Each check queries Sentora's existing data (agents, apps, classifications, EOL lifecycle data) — no additional agents or scanners required.

| Check Type | What It Checks | Example Control |
|------------|---------------|-----------------|
| **prohibited_app** | Are applications classified as Prohibited installed? | SOC2-CC6.7, PCI-2.2.5-P |
| **required_app** | Are required applications missing from endpoints? | SOC2-CC6.8, HIPAA-REQ-SW |
| **agent_version** | Is the SentinelOne agent up to date? | SOC2-CC6.6, BSI-SYS.2.1.A6 |
| **agent_online** | Have agents checked in recently? | SOC2-A1.1, PCI-5.2.1 |
| **app_version** | Are installed applications at current versions? | SOC2-CC3.2, PCI-6.3.3 |
| **sync_freshness** | Is the data inventory recent enough? | SOC2-CC6.1, PCI-2.2.1 |
| **classification_coverage** | What percentage of agents have been classified? | SOC2-CC7.2, HIPAA-CLASS-COV |
| **unclassified_threshold** | Are too many apps per endpoint unclassified? | SOC2-CC7.3, PCI-12.5.1-UNCL |
| **delta_detection** | Have new applications appeared since the last sync? | SOC2-CC7.1, PCI-11.5.1 |
| **custom_app_presence** | Is a specific application present or absent? | HIPAA-312a2iv (encryption) |
| **eol_software** | Is End-of-Life software installed on endpoints? | DORA-8.7-01, PCI-6.3.3-EOL |

---

## Getting Started

### 1. Enable a Framework

Navigate to **Compliance > Settings**. Each framework is shown as a card with an enable/disable toggle. Click the toggle to activate a framework for your tenant.

### 2. Review Controls

Click a framework card to see all its controls. Each control shows:
- **Control ID** — the framework's official reference (e.g. `SOC2-CC6.7`)
- **Severity** — Critical, High, Medium, or Low
- **Description** — what the control checks
- **Scope** — which agents are evaluated (tags, groups, or all)

You can disable individual controls or override their severity and thresholds.

### 3. Run a Check

Click **Run All Checks** on the Compliance Dashboard. The engine evaluates all enabled controls across all enabled frameworks concurrently.

Results appear in:
- **Control Status Table** — pass/fail/warning per control
- **Unified Violations Feed** — all findings from both compliance and enforcement
- **Control Detail View** — click any control to see per-endpoint violations and historical trend

### 4. Configure Scoping

Many controls can be scoped to specific agent groups or tags. For example, PCI DSS controls default to agents tagged `PCI-CDE`. To configure:

1. Go to **Compliance > Settings**
2. Select a framework
3. Click the control to edit
4. Set scope tags (e.g. `PCI-CDE`, `HIPAA`) or scope groups (e.g. `Production`)

### 5. Schedule Automatic Checks

By default, compliance checks run automatically after every successful data sync. You can also configure a cron schedule under **Compliance > Settings > Check Schedule**.

---

## Framework-Specific Notes

### SOC 2

SOC 2 is principles-based, not prescriptive. Sentora's controls are recommendations based on the Trust Services Criteria — not an official checklist. Use the evidence summaries in your audit preparation materials.

### PCI DSS 4.0.1

PCI DSS distinguishes between CDE (Cardholder Data Environment) and non-CDE systems. Tag your CDE endpoints with `PCI-CDE` in SentinelOne, and Sentora's PCI controls will automatically scope to those endpoints.

### HIPAA

HIPAA safeguards are marked as **Required** or **Addressable**. Addressable safeguards require a risk-based decision but are not optional. Tag ePHI-processing endpoints with `HIPAA`.

### BSI IT-Grundschutz

BSI controls are classified by requirement level:
- **Basis** (MUSS) — mandatory baseline
- **Standard** (SOLLTE) — recommended
- **Elevated** (SOLLTE bei erhohtem Schutzbedarf) — for higher protection needs

### DORA (Digital Operational Resilience Act)

DORA (EU 2022/2554) applies to EU financial entities and their critical ICT third-party providers. It has been fully applicable since 17 January 2025. Sentora covers the endpoint software management aspects of DORA across 5 article categories:

- **Art. 8 — ICT Asset Identification** (6 controls): Software inventory completeness, classification coverage, critical asset identification, inventory freshness, risk source detection, legacy system assessment.
- **Art. 9 — ICT Protection & Prevention** (7 controls): Endpoint monitoring, EDR presence, encryption presence, unauthorized software restriction, change detection, agent version currency, software patch currency.
- **Art. 10 — ICT Anomaly Detection** (2 controls): Software change anomaly detection, unclassified software anomaly.
- **Art. 11 — ICT Business Continuity** (2 controls): Endpoint monitoring continuity, data collection continuity.
- **Art. 28 — ICT Third-Party Software Risk** (3 controls): Third-party software inventory, unapproved third-party software, third-party software documentation.

**Configuration required:** Three controls (`DORA-8.4-01`, `DORA-9.2-01`, `DORA-9.2-02`) require tenant-specific configuration of which applications to check. Until configured, these controls return "not applicable". Navigate to **Compliance > Settings > DORA** to configure them.

**Scope disclaimer:** DORA encompasses broader requirements including ICT incident reporting (Art. 17-19), digital operational resilience testing (Art. 24-27), and third-party contractual arrangements (Art. 28-30) that are outside Sentora's scope.

### ISO/IEC 27001:2022

ISO 27001 is the international standard for information security management systems (ISMS). Sentora evaluates the subset of Annex A controls that can be validated through endpoint software data:

- **A.5 Organizational Controls** (4 controls): Asset inventory completeness and currency (A.5.9), acceptable use enforcement (A.5.10), information transfer continuity (A.5.14).
- **A.8 Technological Controls** (12 controls): Endpoint device protection (A.8.1), malware protection (A.8.7), vulnerability management (A.8.8), configuration management (A.8.9), monitoring activities (A.8.16), software installation control (A.8.19), secure development visibility (A.8.25), change management (A.8.32).

**Statement of Applicability (SoA):** ISO 27001 requires organizations to justify excluded controls. When disabling any control, you can provide a `disable_reason` that is preserved in the audit log and displayed in the Settings view. This field is available for all frameworks but is particularly important for ISO 27001.

**Configuration required:** One control (`ISO-A.8.19-REQ`) requires tenant-specific configuration of required security applications. Until configured, it returns "not applicable".

**Scope disclaimer:** ISO 27001 certification requires a complete ISMS encompassing risk assessment, policies, procedures, people controls (A.6), physical security (A.7), supplier management, and management review — all outside Sentora's scope. Sentora provides supporting evidence for a subset of Annex A requirements.

### NIST CSF 2.0

NIST CSF 2.0 (February 2024) organizes cybersecurity outcomes into six Functions: Govern, Identify, Protect, Detect, Respond, and Recover. Sentora evaluates selected subcategories within three Functions:

- **Identify** (4 controls): Asset management — inventory completeness, currency, software classification, lifecycle tracking (ID.AM-01, ID.AM-02).
- **Protect** (8 controls): Platform security, data security, and infrastructure resilience — configuration management, software maintenance, EOL removal, authorized software enforcement, encryption presence (PR.DS, PR.IR, PR.PS).
- **Detect** (3 controls): Continuous monitoring — endpoint coverage, agent currency, vulnerability awareness (DE.CM).

Govern, Respond, and Recover require organizational governance, incident management, and recovery processes outside endpoint monitoring scope.

### NIS2 (EU Directive 2022/2555)

NIS2 applies to essential and important entities across the EU (~160,000 organizations). Article 21(2) lists ten measures (a)-(j). Sentora evaluates five:

- **(a) Risk analysis** (4 controls): Endpoint protection, agent currency, EOL exposure, asset inventory.
- **(d) Supply chain** (2 controls): Software patch currency, third-party EOL detection.
- **(e) Acquisition/development/maintenance** (4 controls): Unauthorized software, required security software, classification, change detection.
- **(h) Cyber hygiene** (2 controls): Software inventory known, data freshness.
- **(i) Cryptography** (1 control): Encryption software presence.

Measures (b) incident handling, (c) business continuity, (f) effectiveness assessment, (g) reporting, and (j) MFA are outside endpoint monitoring scope. National NIS2 implementations may impose additional requirements.

### CIS Controls v8

CIS Controls v8 define 18 prioritized controls with 153 safeguards across three Implementation Groups (IG1 Basic, IG2 Foundational, IG3 Advanced). Sentora evaluates safeguards from four Controls:

- **Control 1 — Enterprise Asset Inventory** (2 safeguards, IG1): Inventory completeness and currency.
- **Control 2 — Software Asset Inventory** (6 safeguards, IG1-IG3): Software inventory, EOL detection, unauthorized software, authorized software allowlisting, change detection, classification coverage.
- **Control 7 — Vulnerability Management** (3 safeguards, IG1): EOL detection, OS-level patching proxy (agent version), application patch management.
- **Control 10 — Malware Defenses** (3 safeguards, IG1-IG2): Anti-malware deployment, signature updates, behavior-based detection.

Controls 3-6, 8-9, and 11-18 cover access management, data protection, email security, network monitoring, and other areas outside endpoint software inventory scope.

---

## Custom Controls

Tenant administrators can create custom controls that use any of the 10 check types. Navigate to **Compliance > Settings**, select a framework, and click **Add Custom Control**.

Custom control IDs must start with `custom-` (e.g. `custom-vpn-required`).

---

## API Reference

All compliance endpoints are under `/api/v1/compliance/`. See the OpenAPI specification at `/docs` (development mode) for full request/response schemas.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/frameworks` | List all frameworks with enabled state |
| GET | `/frameworks/{id}` | Framework detail with all controls |
| PUT | `/frameworks/{id}/enable` | Enable a framework |
| PUT | `/frameworks/{id}/disable` | Disable a framework |
| PUT | `/controls/{id}` | Configure a control |
| POST | `/controls/custom` | Create a custom control |
| POST | `/run` | Trigger compliance checks |
| GET | `/results/latest` | Latest check results |
| GET | `/results/{id}/history` | Historical trend for a control |
| GET | `/dashboard` | Aggregated compliance scores |
| GET | `/violations` | Compliance violations (paginated) |
| GET | `/violations/unified` | Combined compliance + enforcement violations |
| GET | `/violations/export` | CSV export |
| GET | `/schedule` | Current check schedule |
| PUT | `/schedule` | Update check schedule |
