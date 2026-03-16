# Compliance Monitoring

Sentora monitors endpoint software compliance as part of your broader compliance program. It provides automated evidence collection and continuous monitoring for the endpoint management controls within SOC 2, PCI DSS, HIPAA, and BSI IT-Grundschutz.

> **Important:** Sentora provides monitoring and evidence, not certification. Full compliance requires additional controls, policies, and assessments beyond Sentora's scope.

---

## Available Frameworks

| Framework | Version | Focus Area | Controls |
|-----------|---------|------------|----------|
| **SOC 2 Type II** | 2024 | AICPA Trust Services Criteria (Security, Availability) | 15 |
| **PCI DSS** | 4.0.1 | Payment Card Industry Data Security | 15 |
| **HIPAA** | 45 CFR 164 | Health Insurance Portability — ePHI safeguards | 15 |
| **BSI IT-Grundschutz** | Edition 2023 | German federal information security standard | 16 |

Each framework ships with pre-built controls that can be individually enabled, disabled, or configured per tenant.

---

## Check Types

Every control uses one of 10 check types. Each check queries Sentora's existing data (agents, apps, classifications) — no additional agents or scanners required.

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
