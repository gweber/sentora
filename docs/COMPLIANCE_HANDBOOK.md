# Sentora Compliance Handbook

> Complete operator reference for Sentora's compliance module. Covers 5 frameworks, 84 controls, and 11 check types.

## How Compliance Works in Sentora

Sentora's compliance module continuously monitors your endpoint fleet against industry frameworks. It checks the software installed on your endpoints — what's there, what's missing, what's outdated, and what's prohibited — and maps findings to specific compliance requirements.

### What Sentora Checks

- **Software inventory**: Which applications are installed on each endpoint
- **Application classification**: Whether each app is Approved, Flagged, Prohibited, or unclassified
- **Agent health**: SentinelOne agent version, online status, and data freshness
- **Change detection**: New or removed software between sync windows
- **End-of-Life**: Software that no longer receives security patches

### What Sentora Does NOT Check

- SentinelOne policy configuration (threat detection settings, firewall rules)
- Network security (firewalls, IDS/IPS, segmentation)
- User access controls (Active Directory, SSO, MFA)
- Physical security controls
- Operational procedures (incident response plans, training records)
- Contractual or legal compliance requirements

### How Checks Run

Compliance checks execute automatically in two ways:
1. **After sync**: When a data sync completes, compliance checks run against the fresh data
2. **Scheduled**: A configurable cron schedule (default: daily at 06:00 UTC)

You can also trigger a manual compliance run from **Compliance > Run Checks**.

### How Scores Are Calculated

Each framework's score is calculated as:

```
Score = (Passed Controls / Applicable Controls) x 100
```

- **Applicable** = all enabled controls minus those returning `not_applicable`
- Controls with status `not_applicable` (unconfigured or no agents in scope) do not affect the score
- Controls with status `error` count as non-passing
- Controls with status `warning` count as non-passing

### Compliance vs. Enforcement

Sentora has two related but distinct modules:

| | Compliance | Enforcement |
|---|---|---|
| **Purpose** | Monitor and report posture | Detect and alert on rule violations |
| **Scope** | Framework-mapped controls | Custom rules (prohibited apps, required apps) |
| **Output** | Compliance scores + audit evidence | Violation alerts + webhook notifications |
| **Audience** | Auditors, compliance officers | MSP technicians, SOC analysts |

Both modules feed into the **Unified Violations** view, giving you a single pane for everything that's broken.

## Getting Started

### Step 1: Enable Your First Framework

1. Go to **Compliance > Settings**
2. Toggle on the framework you need (e.g. SOC 2, PCI DSS)
3. Click **Save**

Start with one framework. You can enable additional frameworks at any time.

### Step 2: Review Controls That Need Configuration

Some controls require tenant-specific configuration before they work. After enabling a framework:

1. Go to **Compliance > Settings > [Framework Name]**
2. Look for controls marked "Configuration Required"
3. Configure each one (e.g. specify which apps are required, which encryption tool to check)

**Common configurations:**
- **Required apps**: Specify which security software must be installed (e.g. "SentinelOne", "BitLocker")
- **App presence checks**: Specify which application to verify (e.g. "Cisco AnyConnect*" for VPN)

Controls left unconfigured will show `not_applicable` and won't affect your compliance score.

### Step 3: Run Your First Compliance Check

1. Go to **Compliance > Dashboard**
2. Click **Run Checks**
3. Wait for results (typically 5-30 seconds depending on fleet size)

### Step 4: Understand the Dashboard

The dashboard shows:
- **Framework cards**: One per enabled framework with its compliance score
- **Score color coding**: Green (>90%), Yellow (70-90%), Red (<70%)
- **Violations feed**: Latest violations across all frameworks, sorted by severity
- **Control status table**: Pass/fail status for every active control

### Step 5: Configure Scope (Optional)

By default, controls check all managed endpoints. To restrict a control to specific endpoints:

1. Go to **Compliance > Settings > [Framework] > [Control]**
2. Set **Scope Tags** (e.g. `PCI-CDE` to check only cardholder data environment endpoints)
3. Set **Scope Groups** (e.g. `Finance Department` to check only that group)
4. Click **Save**

PCI DSS controls come pre-scoped to `PCI-CDE` tags where appropriate.

## Framework Reference

Sentora monitors 84 controls across 5 compliance frameworks. 10 controls require tenant-specific configuration before they produce results.

### SOC 2 Type II

**Version:** 2024

AICPA Trust Services Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy

> **Disclaimer**
> These checks support evidence collection for SOC 2 audits. They do not constitute SOC 2 certification. Full compliance requires assessment by a licensed CPA firm.

<!-- TODO: Write framework_soc2 section in docs/handbook_content/framework_soc2.md -->

#### Controls

| Control ID | Title | Check Type | Severity | Config Required |
|---|---|---|---|---|
| `SOC2-CC6.1` | Complete Software Inventory | `sync_freshness_check` | **HIGH** | No |
| `SOC2-CC6.1-SW` | Software Asset Classification | `classification_coverage_check` | MEDIUM | No |
| `SOC2-CC6.6` | EDR Protection on All Endpoints | `agent_version_check` | **CRITICAL** | No |
| `SOC2-CC6.7` | No Prohibited Software | `prohibited_app_check` | **CRITICAL** | No |
| `SOC2-CC6.8` | Required Software Installed | `required_app_check` | **HIGH** | Yes |
| `SOC2-CC7.1` | Endpoint Software Change Monitoring | `delta_detection_check` | MEDIUM | No |
| `SOC2-CC7.2` | Classification Anomaly Detection | `classification_coverage_check` | **HIGH** | No |
| `SOC2-CC7.3` | Unclassified Application Threshold | `unclassified_threshold_check` | MEDIUM | No |
| `SOC2-CC8.1` | Software Change Tracking | `delta_detection_check` | MEDIUM | No |
| `SOC2-A1.1` | Endpoint Availability | `agent_online_check` | **HIGH** | No |
| `SOC2-A1.2` | Data Freshness | `sync_freshness_check` | **HIGH** | No |
| `SOC2-CC3.1` | Asset Classification Coverage | `classification_coverage_check` | MEDIUM | No |
| `SOC2-CC3.2` | Software Version Currency | `app_version_check` | MEDIUM | No |
| `SOC2-CC6.1-EOL` | End-of-Life Software Detection | `eol_software_check` | **HIGH** | No |
| `SOC2-CC9.1` | Endpoint Protection Currency | `agent_version_check` | **HIGH** | No |
| `SOC2-CC9.2` | Prohibited Software Enforcement | `prohibited_app_check` | **CRITICAL** | No |

#### Control Details

##### CC6 — Access Controls

###### `SOC2-CC6.1` — Complete Software Inventory

**Severity:** **HIGH**

**What it checks:** Verifies that all managed endpoints have synced application data within the configured time window (24 hours). Endpoints with stale or missing sync data represent gaps in the software asset inventory required by CC6.1.

**Parameters:** `max_hours_since_sync`: `24`

**How to fix a failure:** Ensure all agents are syncing regularly. Check the Sync view for errors or stalled runs. If data is stale, trigger a manual sync from the Sync page.

---

###### `SOC2-CC6.1-SW` — Software Asset Classification

**Severity:** MEDIUM

**What it checks:** Checks that at least 90% of installed applications have been classified as Approved, Flagged, or Prohibited. Unclassified applications represent unknown risk that cannot be assessed for access control compliance.

**Parameters:** `min_classified_percent`: `90`

**How to fix a failure:** Run the classification engine from the Classification view to classify unprocessed applications. Review unclassified applications in the App Overview and assign categories.

---

###### `SOC2-CC6.6` — EDR Protection on All Endpoints

**Severity:** **CRITICAL**

**What it checks:** Verifies all managed endpoints are running the SentinelOne agent at or above the fleet baseline version, ensuring continuous EDR protection coverage.

**Parameters:** None

**How to fix a failure:** Update the SentinelOne agent to the fleet baseline version on all non-compliant endpoints. Check the Agent Detail view to identify outdated agents and use the SentinelOne console to schedule upgrades.

---

###### `SOC2-CC6.7` — No Prohibited Software

**Severity:** **CRITICAL**

**What it checks:** Detects unauthorized software by scanning all managed endpoints for applications classified as Prohibited in the taxonomy. Any prohibited application violates logical access controls.

**Parameters:** None

**How to fix a failure:** Remove all prohibited applications from affected endpoints immediately. Review flagged endpoints in the Anomalies view and investigate how unauthorized software was installed.

---

###### `SOC2-CC6.8` — Required Software Installed

**Severity:** **HIGH**

**What it checks:** Verifies that configured mandatory security software is present on all managed endpoints (e.g. encryption tools, VPN clients). Requires tenant-specific configuration of which applications are required.

**Parameters:** `required_apps`: `[]`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the required applications for this control in Compliance > Settings > SOC 2 > SOC2-CC6.8. Specify the security software names that must be present on all endpoints (e.g. 'BitLocker', 'CrowdStrike'). Then deploy missing software.

---

###### `SOC2-CC6.1-EOL` — End-of-Life Software Detection

**Severity:** **HIGH**

**What it checks:** End-of-Life software no longer receives security patches and represents an unmitigated risk. This control detects applications that have reached End-of-Life using endoflife.date lifecycle data.

**Parameters:** `flag_security_only`: `True`, `min_match_confidence`: `0.8`

**How to fix a failure:** Upgrade End-of-Life software to a supported version. Review flagged applications in the App Overview filtered by EOL status. See endoflife.date for lifecycle information and supported version alternatives.

---

##### CC7 — System Operations

###### `SOC2-CC7.1` — Endpoint Software Change Monitoring

**Severity:** MEDIUM

**What it checks:** Detects new or removed applications between sync windows within a 24-hour lookback period. Changes in the software inventory may indicate unauthorized modifications or compromised endpoints.

**Parameters:** `lookback_hours`: `24`

**How to fix a failure:** Review detected software changes in the Anomalies view. Verify that all new installations were authorized. Investigate unexpected removals or additions.

---

###### `SOC2-CC7.2` — Classification Anomaly Detection

**Severity:** **HIGH**

**What it checks:** Checks that at least 80% of applications are classified, which is the minimum threshold needed to reliably detect anomalous software installations. Unclassified applications cannot be evaluated against the approved software policy.

**Parameters:** `min_classified_percent`: `80`

**How to fix a failure:** Run the classification engine from the Classification view to process unclassified applications. Review results in the App Overview and create fingerprints for recurring unknown applications.

---

###### `SOC2-CC7.3` — Unclassified Application Threshold

**Severity:** MEDIUM

**What it checks:** Flags endpoints where more than 10% of installed applications are unclassified. A high proportion of unclassified software undermines the ability to detect anomalous or unauthorized applications.

**Parameters:** `max_unclassified_percent`: `10`

**How to fix a failure:** Review unclassified applications on flagged endpoints in the App Overview. Use the Taxonomy Editor to classify unknown software or create fingerprints for recurring applications.

---

##### CC8 — Change Management

###### `SOC2-CC8.1` — Software Change Tracking

**Severity:** MEDIUM

**What it checks:** Detects software inventory changes over a 48-hour lookback window using Sentora's delta detection engine. Tracks new installations, removals, and version changes to support change management evidence collection.

**Parameters:** `lookback_hours`: `48`

**How to fix a failure:** Ensure sync schedules are active and completing on time in the Sync view. Review detected changes in the Anomalies view and verify they align with approved change requests.

---

##### A1 — Availability

###### `SOC2-A1.1` — Endpoint Availability

**Severity:** **HIGH**

**What it checks:** Checks that all managed endpoints have checked in within the last 7 days. Agents that have not reported in exceed the availability tolerance and may indicate decommissioned or unreachable systems.

**Parameters:** `max_offline_days`: `7`

**How to fix a failure:** Investigate offline endpoints in the Agent Detail view. Verify network connectivity, check whether the endpoint is decommissioned, and restore the SentinelOne agent service if needed.

---

###### `SOC2-A1.2` — Data Freshness

**Severity:** **HIGH**

**What it checks:** Verifies that the most recent data sync completed within the 48-hour window. Stale inventory data means compliance checks are evaluating outdated information, reducing the reliability of all other controls.

**Parameters:** `max_hours_since_sync`: `48`

**How to fix a failure:** Check the Sync view for errors or stalled sync runs. Verify the SentinelOne API connection is functional. If syncs are failing, trigger a manual sync from the Sync page.

---

##### CC3 — Risk Assessment

###### `SOC2-CC3.1` — Asset Classification Coverage

**Severity:** MEDIUM

**What it checks:** Checks that at least 70% of applications across managed endpoints have been classified. Classification results are the foundation for risk assessment -- unclassified software cannot be evaluated for risk.

**Parameters:** `min_classified_percent`: `70`

**How to fix a failure:** Run the classification engine from the Classification view. Review unclassified applications in the App Overview and assign categories using the Taxonomy Editor.

---

###### `SOC2-CC3.2` — Software Version Currency

**Severity:** MEDIUM

**What it checks:** Checks that no more than 20% of installed applications are running outdated versions compared to the library baseline. Outdated software may contain known vulnerabilities that increase the organization's risk profile.

**Parameters:** `max_outdated_percent`: `20`

**How to fix a failure:** Review outdated applications in the Library Browser view. Prioritize updates for applications with known vulnerabilities. Deploy patches through your software distribution tooling.

---

##### CC9 — Risk Mitigation

###### `SOC2-CC9.1` — Endpoint Protection Currency

**Severity:** **HIGH**

**What it checks:** Verifies SentinelOne agent versions are maintained at or above the fleet baseline to ensure consistent threat mitigation capabilities across the endpoint fleet.

**Parameters:** None

**How to fix a failure:** Update the SentinelOne agent on non-compliant endpoints to the fleet baseline version. Use the Agent Detail view to identify outdated agents and schedule upgrades through the SentinelOne console.

---

###### `SOC2-CC9.2` — Prohibited Software Enforcement

**Severity:** **CRITICAL**

**What it checks:** Provides continuous monitoring that no applications classified as Prohibited persist on any managed endpoint. Unlike CC6.7 (point-in-time detection), this control enforces ongoing compliance as part of risk mitigation.

**Parameters:** None

**How to fix a failure:** Remove prohibited software from affected endpoints immediately. Review recurring violations in the Anomalies view and investigate root causes. Update the taxonomy in the Taxonomy Editor if classification rules need refinement.

---

### PCI DSS 4.0.1

**Version:** 4.0.1

Payment Card Industry Data Security Standard — requirements for protecting cardholder data

> **Disclaimer**
> PCI DSS compliance requires validation by a Qualified Security Assessor (QSA). Sentora provides evidence and monitoring for endpoint-related requirements, not certification.

<!-- TODO: Write framework_pci_dss_4 section in docs/handbook_content/framework_pci_dss_4.md -->

#### Controls

| Control ID | Title | Check Type | Severity | Config Required |
|---|---|---|---|---|
| `PCI-2.2.1` | System Inventory Current | `sync_freshness_check` | **HIGH** | No |
| `PCI-2.2.5` | Only Authorised Software on CDE | `unclassified_threshold_check` | **CRITICAL** | No |
| `PCI-2.2.5-P` | No Prohibited Software in CDE | `prohibited_app_check` | **CRITICAL** | No |
| `PCI-5.2.1` | Anti-Malware on All Systems | `agent_online_check` | **CRITICAL** | No |
| `PCI-5.2.2` | Anti-Malware Definitions Current | `agent_version_check` | **HIGH** | No |
| `PCI-5.2.3` | Regular Security Scans | `sync_freshness_check` | MEDIUM | No |
| `PCI-5.3.1` | Anti-Malware Active on CDE Systems | `agent_online_check` | **CRITICAL** | No |
| `PCI-6.3.1` | Known Vulnerability Identification | `classification_coverage_check` | **HIGH** | No |
| `PCI-6.3.3` | Security Patches Timely | `app_version_check` | **HIGH** | No |
| `PCI-6.3.3-CDE` | CDE Patch Currency | `app_version_check` | **CRITICAL** | No |
| `PCI-6.3.3-EOL` | End-of-Life Software Patching | `eol_software_check` | **CRITICAL** | No |
| `PCI-11.5.1` | Change Detection on CDE | `delta_detection_check` | **CRITICAL** | No |
| `PCI-11.5.1-ALL` | Fleet-Wide Change Detection | `delta_detection_check` | MEDIUM | No |
| `PCI-12.5.1` | Complete System Component Inventory | `classification_coverage_check` | **HIGH** | No |
| `PCI-12.5.1-UNCL` | Unclassified Software Below Threshold | `unclassified_threshold_check` | MEDIUM | No |
| `PCI-12.5.2` | Required Security Software | `required_app_check` | **HIGH** | Yes |

#### Control Details

##### Req 2 — Secure Configurations

###### `PCI-2.2.1` — System Inventory Current

**Severity:** **HIGH**

**What it checks:** Verifies that the most recent data sync completed within 24 hours, ensuring the software inventory reflects the current state of all system components as required by PCI DSS Requirement 2.2.1.

**Parameters:** `max_hours_since_sync`: `24`

**How to fix a failure:** Check the Sync view for errors or stalled sync runs. If data is stale, trigger a manual sync from the Sync page. Verify the SentinelOne API connection is functional.

---

###### `PCI-2.2.5` — Only Authorised Software on CDE

**Severity:** **CRITICAL**

**What it checks:** Checks that 0% of applications on CDE-tagged endpoints are unclassified, meaning every single application must be classified as Approved, Flagged, or Prohibited. Any unclassified application in the CDE is a compliance gap.

**Parameters:** `max_unclassified_percent`: `0`
**Scope:** Tags: `PCI-CDE`

**How to fix a failure:** Classify every application on PCI-CDE tagged endpoints. Use the Classification view filtered to PCI-CDE groups. Any unclassified application in the CDE is a compliance gap.

---

###### `PCI-2.2.5-P` — No Prohibited Software in CDE

**Severity:** **CRITICAL**

**What it checks:** Scans all CDE-tagged endpoints for applications classified as Prohibited in the taxonomy. Any prohibited software in the Cardholder Data Environment is a critical PCI DSS violation.

**Parameters:** None
**Scope:** Tags: `PCI-CDE`

**How to fix a failure:** Remove prohibited software from CDE endpoints immediately. Review flagged endpoints in the Anomalies view filtered to PCI-CDE groups. Investigate how unauthorized software was installed.

---

##### Req 5 — Malware Protection

###### `PCI-5.2.1` — Anti-Malware on All Systems

**Severity:** **CRITICAL**

**What it checks:** Verifies that all managed endpoints have checked in within the last 24 hours, confirming the SentinelOne agent is active and providing anti-malware protection as required by PCI DSS Requirement 5.2.1.

**Parameters:** `max_offline_days`: `1`

**How to fix a failure:** Investigate offline endpoints in the Agent Detail view. Verify the SentinelOne agent service is running and restore connectivity. Offline endpoints lack anti-malware protection.

---

###### `PCI-5.2.2` — Anti-Malware Definitions Current

**Severity:** **HIGH**

**What it checks:** Checks that the SentinelOne agent version on each endpoint is at or above the fleet baseline. Outdated agent versions may lack current threat detection capabilities required by PCI DSS Requirement 5.2.2.

**Parameters:** None

**How to fix a failure:** Update the SentinelOne agent to the fleet baseline version on all non-compliant endpoints. Use the Agent Detail view to identify outdated agents and the SentinelOne console to schedule upgrades.

---

###### `PCI-5.2.3` — Regular Security Scans

**Severity:** MEDIUM

**What it checks:** Verifies that data syncs have completed within a 12-hour window, ensuring the software inventory is fresh enough for timely malware and threat detection as required by PCI DSS Requirement 5.2.3.

**Parameters:** `max_hours_since_sync`: `12`

**How to fix a failure:** Check the Sync view to verify sync schedules are active and completing on time. If syncs are failing, check the SentinelOne API connection and trigger a manual sync.

---

###### `PCI-5.3.1` — Anti-Malware Active on CDE Systems

**Severity:** **CRITICAL**

**What it checks:** Verifies that all CDE-tagged endpoints have checked in within the last 24 hours, confirming active anti-malware protection specifically on systems that process or store cardholder data.

**Parameters:** `max_offline_days`: `1`
**Scope:** Tags: `PCI-CDE`

**How to fix a failure:** Investigate offline CDE endpoints immediately in the Agent Detail view filtered to PCI-CDE groups. Restore SentinelOne agent connectivity. CDE systems without active anti-malware are a critical PCI violation.

---

##### Req 6 — Secure Software

###### `PCI-6.3.1` — Known Vulnerability Identification

**Severity:** **HIGH**

**What it checks:** Checks that at least 95% of installed applications are classified and matched against the NIST CPE library. Unmatched applications cannot be evaluated for known vulnerabilities (CVEs).

**Parameters:** `min_classified_percent`: `95`

**How to fix a failure:** Run the classification engine from the Classification view to process unmatched applications. Review results in the Library Browser to verify CPE matches. Create fingerprints for applications that cannot be auto-matched.

---

###### `PCI-6.3.3` — Security Patches Timely

**Severity:** **HIGH**

**What it checks:** Checks that no more than 10% of installed applications are running outdated versions compared to the library baseline. Outdated software may contain known vulnerabilities that violate PCI DSS patch management requirements.

**Parameters:** `max_outdated_percent`: `10`

**How to fix a failure:** Review outdated applications in the Library Browser view. Prioritize patching applications with known CVEs. Deploy updates through your software distribution tooling.

---

###### `PCI-6.3.3-CDE` — CDE Patch Currency

**Severity:** **CRITICAL**

**What it checks:** Enforces a 0% tolerance for outdated application versions on CDE-tagged endpoints. Every application in the Cardholder Data Environment must be running the current baseline version with no exceptions.

**Parameters:** `max_outdated_percent`: `0`
**Scope:** Tags: `PCI-CDE`

**How to fix a failure:** Patch all outdated software on CDE endpoints immediately. Review the Library Browser filtered to PCI-CDE groups to identify version gaps. Any outdated application in the CDE is a critical compliance violation.

---

###### `PCI-6.3.3-EOL` — End-of-Life Software Patching

**Severity:** **CRITICAL**

**What it checks:** End-of-Life software cannot be patched and violates PCI DSS patch management requirements. This control detects applications past their End-of-Life date using endoflife.date lifecycle data.

**Parameters:** `flag_security_only`: `False`, `min_match_confidence`: `0.8`

**How to fix a failure:** Replace End-of-Life software immediately. Review flagged applications in the App Overview filtered by EOL status. EOL software cannot receive security patches and violates PCI DSS Requirement 6.3.3. Prioritize CDE endpoints.

---

##### Req 11 — Regular Testing

###### `PCI-11.5.1` — Change Detection on CDE

**Severity:** **CRITICAL**

**What it checks:** Detects new, changed, or removed software on CDE-tagged endpoints within a 24-hour lookback window using Sentora's delta detection engine. Any unauthorized change in the CDE may compromise cardholder data security.

**Parameters:** `lookback_hours`: `24`
**Scope:** Tags: `PCI-CDE`

**How to fix a failure:** Review all software changes on CDE systems in the Anomalies view filtered to PCI-CDE groups. Verify each change was authorized through the change management process. Escalate unauthorized changes immediately.

---

###### `PCI-11.5.1-ALL` — Fleet-Wide Change Detection

**Severity:** MEDIUM

**What it checks:** Detects new, changed, or removed software across all managed endpoints within a 48-hour lookback window. Fleet-wide change detection catches unauthorized installations that may eventually reach the CDE.

**Parameters:** `lookback_hours`: `48`

**How to fix a failure:** Review fleet-wide software changes in the Anomalies view. Verify that all detected changes were authorized. Investigate unexpected installations or removals.

---

##### Req 12 — Security Policy

###### `PCI-12.5.1` — Complete System Component Inventory

**Severity:** **HIGH**

**What it checks:** Checks that at least 90% of applications across all managed endpoints have been classified. A complete, classified software inventory is the foundation for PCI DSS security policy enforcement.

**Parameters:** `min_classified_percent`: `90`

**How to fix a failure:** Run the classification engine from the Classification view to process unclassified applications. Review results in the App Overview and assign categories using the Taxonomy Editor.

---

###### `PCI-12.5.1-UNCL` — Unclassified Software Below Threshold

**Severity:** MEDIUM

**What it checks:** Flags endpoints where more than 5% of installed applications are unclassified. Unclassified software represents unknown risk that cannot be assessed against the organization's security policy.

**Parameters:** `max_unclassified_percent`: `5`

**How to fix a failure:** Review unclassified applications on flagged endpoints in the App Overview. Use the Taxonomy Editor to classify unknown software or create fingerprints for recurring applications.

---

###### `PCI-12.5.2` — Required Security Software

**Severity:** **HIGH**

**What it checks:** Verifies that configured mandatory security tools are installed on all PCI-CDE tagged endpoints. Requires tenant-specific configuration of which security applications are mandatory for PCI compliance.

**Parameters:** `required_apps`: `[]`
**Scope:** Tags: `PCI-CDE`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the required applications for this control in Compliance > Settings > PCI DSS > PCI-12.5.2. Specify the security software names that must be present on all CDE endpoints (e.g. 'BitLocker', 'CrowdStrike'). Then deploy missing software.

---

### HIPAA Security Rule

**Version:** 45 CFR 164

Health Insurance Portability and Accountability Act — Security Rule for electronic Protected Health Information (ePHI)

> **Disclaimer**
> HIPAA compliance is determined by the U.S. Department of Health and Human Services. Sentora provides technical safeguard monitoring for endpoint software management.

<!-- TODO: Write framework_hipaa section in docs/handbook_content/framework_hipaa.md -->

#### Controls

| Control ID | Title | Check Type | Severity | Config Required |
|---|---|---|---|---|
| `HIPAA-308a1` | Risk Analysis — Software Inventory | `classification_coverage_check` | **HIGH** | No |
| `HIPAA-308a1-SYNC` | Risk Analysis — Data Currency | `sync_freshness_check` | **HIGH** | No |
| `HIPAA-308a5` | Security Awareness — Training Software | `custom_app_presence_check` | low | Yes |
| `HIPAA-308a6` | Security Incident — EDR Active | `agent_online_check` | **CRITICAL** | No |
| `HIPAA-312a1` | Access Control — Authorised Software Only | `prohibited_app_check` | **CRITICAL** | No |
| `HIPAA-312a1-UNCL` | Access Control — Unclassified Threshold | `unclassified_threshold_check` | **HIGH** | No |
| `HIPAA-312a2iv` | Encryption Software Installed | `custom_app_presence_check` | **CRITICAL** | No |
| `HIPAA-312b` | Audit Controls — Software Change Tracking | `delta_detection_check` | **HIGH** | No |
| `HIPAA-312c1` | Integrity Controls — Unauthorised Changes | `delta_detection_check` | **HIGH** | No |
| `HIPAA-312e1` | Transmission Security — VPN Software | `custom_app_presence_check` | MEDIUM | Yes |
| `HIPAA-312a1-EOL` | EOL Software Access Risk | `eol_software_check` | **HIGH** | No |
| `HIPAA-312d` | Person Authentication — EDR Version | `agent_version_check` | **HIGH** | No |
| `HIPAA-AVAIL-1` | ePHI System Availability | `agent_online_check` | **HIGH** | No |
| `HIPAA-SW-CURR` | ePHI Software Currency | `app_version_check` | MEDIUM | No |
| `HIPAA-REQ-SW` | Required Security Software on ePHI | `required_app_check` | **HIGH** | Yes |
| `HIPAA-CLASS-COV` | ePHI Classification Coverage | `classification_coverage_check` | **HIGH** | No |

#### Control Details

##### §164.308 — Administrative Safeguards

###### `HIPAA-308a1` — Risk Analysis — Software Inventory

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** §164.308(a)(1) requires an accurate risk analysis of ePHI systems. This control verifies that the classification engine has processed at least 90% of applications on ePHI endpoints, ensuring the software inventory is complete enough for risk analysis.

**Parameters:** `min_classified_percent`: `90`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Run the classification engine on all unprocessed ePHI endpoints. Review the Agents view and filter by scope tag 'HIPAA' to find endpoints with low classification coverage.

---

###### `HIPAA-308a1-SYNC` — Risk Analysis — Data Currency

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** §164.308(a)(1) requires ongoing risk analysis based on current data. This control checks that the most recent data sync completed within 24 hours, ensuring the software inventory reflects the current state of ePHI endpoints.

**Parameters:** `max_hours_since_sync`: `24`

**How to fix a failure:** Check the Sync view for errors or stalled sync runs. Ensure sync schedules are active and the SentinelOne API connection is functional.

---

###### `HIPAA-308a5` — Security Awareness — Training Software

**Severity:** low
 | **HIPAA Type:** Addressable

**What it checks:** §164.308(a)(5) requires security awareness and training. This control checks whether the configured training software is installed on ePHI endpoints. Requires tenant-specific configuration of which training software to check.

**Parameters:** `app_pattern`: ``, `must_exist`: `True`
**Scope:** Tags: `HIPAA`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the training software name in Compliance > Settings > HIPAA > HIPAA-308a5. Specify the app_pattern (e.g. 'KnowBe4*'). Until configured, this control shows not_applicable.

---

###### `HIPAA-308a6` — Security Incident — EDR Active

**Severity:** **CRITICAL**
 | **HIPAA Type:** Required

**What it checks:** §164.308(a)(6) requires security incident procedures. This control verifies that the SentinelOne agent has checked in within 1 day on all ePHI endpoints, ensuring EDR-based incident detection is not interrupted by offline agents.

**Parameters:** `max_offline_days`: `1`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Investigate offline ePHI endpoints immediately. Check network connectivity, verify the SentinelOne agent service is running, and restore communication with the management console.

---

###### `HIPAA-CLASS-COV` — ePHI Classification Coverage

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** ePHI endpoints require a higher classification threshold than the general fleet. This control checks that at least 95% of applications are classified on ePHI endpoints, ensuring near-complete visibility into the software landscape.

**Parameters:** `min_classified_percent`: `95`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Run the classification engine on ePHI endpoints with low coverage. Use the taxonomy editor to classify unknown software or create fingerprints for recurring unclassified applications.

---

##### §164.312 — Technical Safeguards

###### `HIPAA-312a1` — Access Control — Authorised Software Only

**Severity:** **CRITICAL**
 | **HIPAA Type:** Required

**What it checks:** §164.312(a)(1) requires access controls for ePHI systems. This control detects any applications classified as Prohibited on ePHI endpoints, enforcing that only authorized software is installed on systems processing electronic health information.

**Parameters:** None
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Remove all prohibited applications from affected ePHI endpoints immediately. Review the taxonomy to ensure the prohibited classification is current. Investigate how unauthorized software was installed.

---

###### `HIPAA-312a1-UNCL` — Access Control — Unclassified Threshold

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** §164.312(a)(1) requires that only authorized persons access ePHI. This control checks that the percentage of unclassified applications per ePHI endpoint stays below 5%, ensuring all software is categorized and authorization status is known.

**Parameters:** `max_unclassified_percent`: `5`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Review unclassified applications on flagged ePHI endpoints. Use the taxonomy editor to classify unknown software or create fingerprints for recurring unclassified applications.

---

###### `HIPAA-312a2iv` — Encryption Software Installed

**Severity:** **CRITICAL**
 | **HIPAA Type:** Addressable

**What it checks:** §164.312(a)(2)(iv) addresses encryption of ePHI. This control checks whether full-disk encryption software matching the configured pattern is installed on all ePHI endpoints, defaulting to BitLocker detection.

**Parameters:** `app_pattern`: `BitLocker*`, `must_exist`: `True`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Deploy BitLocker (Windows) or FileVault (macOS) on all ePHI endpoints. To check for FileVault instead, update the app_pattern in Compliance > Settings > HIPAA > HIPAA-312a2iv.

---

###### `HIPAA-312b` — Audit Controls — Software Change Tracking

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** §164.312(b) requires audit controls for ePHI systems. This control detects software additions and removals within the last 24 hours on ePHI endpoints, maintaining a change audit trail for compliance evidence.

**Parameters:** `lookback_hours`: `24`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Review detected software changes in the Anomalies view. Ensure sync schedules are active so the audit trail remains continuous. Investigate any unexpected changes on ePHI systems.

---

###### `HIPAA-312c1` — Integrity Controls — Unauthorised Changes

**Severity:** **HIGH**
 | **HIPAA Type:** Addressable

**What it checks:** §164.312(c)(1) requires integrity controls for ePHI. This control detects unauthorized software modifications within a 12-hour window on ePHI endpoints, using a tighter lookback than the audit trail control to catch rapid changes.

**Parameters:** `lookback_hours`: `12`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Review all software changes on ePHI systems in the Anomalies view. Verify that changes were authorized. Escalate unauthorized modifications per incident response procedures.

---

###### `HIPAA-312e1` — Transmission Security — VPN Software

**Severity:** MEDIUM
 | **HIPAA Type:** Addressable

**What it checks:** §164.312(e)(1) addresses transmission security for ePHI. This control checks whether the configured VPN or secure communication software is installed on remote ePHI endpoints. Requires tenant-specific configuration of which VPN client to check.

**Parameters:** `app_pattern`: ``, `must_exist`: `True`
**Scope:** Tags: `HIPAA`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the VPN client name in Compliance > Settings > HIPAA > HIPAA-312e1. Specify the app_pattern (e.g. 'Cisco AnyConnect*'). Until configured, this control shows not_applicable.

---

###### `HIPAA-312a1-EOL` — EOL Software Access Risk

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** End-of-Life software on ePHI endpoints represents an access control risk as it no longer receives security patches. This control detects EOL software using endoflife.date lifecycle data.

**Parameters:** `flag_security_only`: `True`, `min_match_confidence`: `0.8`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Replace End-of-Life software on ePHI endpoints with supported versions. EOL software cannot be patched and poses a risk to ePHI confidentiality and integrity.

---

###### `HIPAA-312d` — Person Authentication — EDR Version

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** §164.312(d) requires person or entity authentication. This control checks that the SentinelOne agent version is current across all ePHI endpoints, ensuring the security platform provides up-to-date identity-based threat detection.

**Parameters:** None
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Update the SentinelOne agent to the current fleet baseline version on all ePHI endpoints. Use the SentinelOne console to schedule agent upgrades.

---

###### `HIPAA-AVAIL-1` — ePHI System Availability

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** HIPAA requires availability of ePHI. This control verifies that all ePHI endpoints have checked in within 3 days, detecting systems that may have lost connectivity and can no longer be monitored or protected.

**Parameters:** `max_offline_days`: `3`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Investigate ePHI endpoints offline for more than 3 days. Verify whether the endpoint is decommissioned, has connectivity issues, or requires agent reinstallation.

---

###### `HIPAA-SW-CURR` — ePHI Software Currency

**Severity:** MEDIUM
 | **HIPAA Type:** Addressable

**What it checks:** Keeping software current on ePHI endpoints mitigates known vulnerabilities. This control checks that no more than 10% of installed applications are running outdated versions compared to the library baseline.

**Parameters:** `max_outdated_percent`: `10`
**Scope:** Tags: `HIPAA`

**How to fix a failure:** Update outdated applications on ePHI endpoints to their current versions. Use the Library view to compare installed versions against the baseline and prioritize updates for applications with known vulnerabilities.

---

###### `HIPAA-REQ-SW` — Required Security Software on ePHI

**Severity:** **HIGH**
 | **HIPAA Type:** Required

**What it checks:** All ePHI endpoints must have mandatory security software installed. This control verifies that the configured required applications are present on all ePHI endpoints. Requires tenant-specific configuration of which applications to check.

**Parameters:** `required_apps`: `[]`
**Scope:** Tags: `HIPAA`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the required security software in Compliance > Settings > HIPAA > HIPAA-REQ-SW. Specify the application names that must be present on ePHI endpoints.

---

### BSI IT-Grundschutz

**Version:** Edition 2023

Bundesamt für Sicherheit in der Informationstechnik — IT-Grundschutz-Kompendium für systematische Informationssicherheit

> **Disclaimer**
> BSI IT-Grundschutz-Konformität erfordert eine vollständige Grundschutz-Prüfung durch einen zertifizierten BSI-Auditor. Sentora überwacht die Endpoint-Software-Management-Anforderungen und liefert Evidenz für Audits.

<!-- TODO: Write framework_bsi_grundschutz section in docs/handbook_content/framework_bsi_grundschutz.md -->

#### Controls

| Control ID | Title | Check Type | Severity | Config Required |
|---|---|---|---|---|
| `BSI-SYS.2.1.A3` | Aktivierung von Auto-Update-Mechanismen | `app_version_check` | **HIGH** | No |
| `BSI-SYS.2.1.A4` | Regelmäßige Datensicherung | `custom_app_presence_check` | MEDIUM | Yes |
| `BSI-SYS.2.1.A6` | Einsatz von Virenschutzprogrammen | `agent_version_check` | **CRITICAL** | No |
| `BSI-SYS.2.1.A6-ONLINE` | Virenschutz — Agent-Erreichbarkeit | `agent_online_check` | **CRITICAL** | No |
| `BSI-SYS.2.1.A42` | Nutzung von Allowlists | `prohibited_app_check` | **HIGH** | No |
| `BSI-SYS.2.1.A42-UNCL` | Allowlists — Unklassifizierte Apps | `unclassified_threshold_check` | MEDIUM | No |
| `BSI-APP.6.A1` | Planung des Software-Einsatzes | `classification_coverage_check` | **HIGH** | No |
| `BSI-APP.6.A1-SYNC` | Software-Inventar — Aktualität | `sync_freshness_check` | **HIGH** | No |
| `BSI-APP.6.A2` | Erstellung eines Anforderungskatalogs | `required_app_check` | MEDIUM | Yes |
| `BSI-APP.6.A4` | Sicherstellung der Integrität von Software | `delta_detection_check` | **HIGH** | No |
| `BSI-APP.6.A5` | Deinstallation nicht benötigter Software | `unclassified_threshold_check` | MEDIUM | No |
| `BSI-OPS.1.1.3.A1` | Konzept für Patch- und Änderungsmanagement | `app_version_check` | **HIGH** | No |
| `BSI-SYS.2.1-EOL` | End-of-Life Software Identification | `eol_software_check` | **HIGH** | No |
| `BSI-OPS.1.1.3.A15` | Regelmäßige Aktualisierung der IT | `app_version_check` | **HIGH** | No |
| `BSI-OPS.1.1.3.A15-EDR` | EDR-Agent Aktualisierung | `agent_version_check` | **CRITICAL** | No |
| `BSI-SYS.2.1.A9` | Festlegung einer Sicherheitsrichtlinie für Clients | `prohibited_app_check` | **HIGH** | No |

#### Control Details

##### SYS.2.1 — Allgemeiner Client

###### `BSI-SYS.2.1.A3` — Aktivierung von Auto-Update-Mechanismen

**Severity:** **HIGH**
 | **BSI Level:** Standard (SOLLTE)

**What it checks:** SYS.2.1.A3 fordert automatische Updates auf Clients. Diese Kontrolle prüft, ob der Anteil veralteter Anwendungen unter 15% liegt, indem installierte Versionen mit der Library-Baseline verglichen werden.

**Parameters:** `max_outdated_percent`: `15`

**How to fix a failure:** Veraltete Anwendungen auf aktuelle Versionen aktualisieren. In der Library-Ansicht können installierte Versionen mit der Baseline verglichen werden. Auto-Update-Mechanismen aktivieren.

---

###### `BSI-SYS.2.1.A4` — Regelmäßige Datensicherung

**Severity:** MEDIUM
 | **BSI Level:** Standard (SOLLTE)

**What it checks:** SYS.2.1.A4 fordert regelmäßige Datensicherung. Diese Kontrolle prüft, ob die konfigurierte Backup-Software auf allen Clients installiert ist. Erfordert mandantenspezifische Konfiguration der Backup-Software.

**Parameters:** `app_pattern`: ``, `must_exist`: `True`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Konfigurieren Sie den Namen der Backup-Software unter Compliance > Einstellungen > BSI > BSI-SYS.2.1.A4. Geben Sie das app_pattern an (z.B. 'Veeam*', 'Acronis*'). Bis zur Konfiguration zeigt diese Kontrolle 'not_applicable'.

---

###### `BSI-SYS.2.1.A6` — Einsatz von Virenschutzprogrammen

**Severity:** **CRITICAL**
 | **BSI Level:** Basis (MUSS)

**What it checks:** SYS.2.1.A6 fordert aktiven Virenschutz auf allen Clients. Diese Kontrolle prüft, ob der SentinelOne Agent als Virenschutzlösung auf der aktuellen Fleet-Baseline-Version läuft und damit vollständigen Echtzeitschutz bietet.

**Parameters:** None

**How to fix a failure:** SentinelOne Agent auf die aktuelle Fleet-Baseline-Version aktualisieren. Verwenden Sie die SentinelOne-Konsole, um Agent-Upgrades für nicht-konforme Endpoints zu planen.

---

###### `BSI-SYS.2.1.A6-ONLINE` — Virenschutz — Agent-Erreichbarkeit

**Severity:** **CRITICAL**
 | **BSI Level:** Basis (MUSS)

**What it checks:** SYS.2.1.A6 fordert lückenlosen Virenschutz. Diese Kontrolle prüft, ob alle SentinelOne Agents innerhalb von 3 Tagen eingecheckt haben — Offline-Agents können nicht überwacht oder geschützt werden.

**Parameters:** `max_offline_days`: `3`

**How to fix a failure:** Offline-Endpoints sofort untersuchen. Netzwerkkonnektivität prüfen, SentinelOne-Agent-Dienst verifizieren und Kommunikation mit der Management-Konsole wiederherstellen.

---

###### `BSI-SYS.2.1.A42` — Nutzung von Allowlists

**Severity:** **HIGH**
 | **BSI Level:** Erhöht (SOLLTE)

**What it checks:** SYS.2.1.A42 fordert den Einsatz von Allowlists bei erhöhtem Schutzbedarf. Diese Kontrolle erkennt Software, die als Prohibited klassifiziert ist, und stellt sicher, dass nur explizit genehmigte Anwendungen installiert sind.

**Parameters:** None

**How to fix a failure:** Alle als Prohibited klassifizierten Anwendungen von betroffenen Endpoints entfernen. In der Taxonomie prüfen, ob die Allowlist vollständig und aktuell ist. Untersuchen, wie nicht-genehmigte Software installiert wurde.

---

###### `BSI-SYS.2.1.A42-UNCL` — Allowlists — Unklassifizierte Apps

**Severity:** MEDIUM
 | **BSI Level:** Erhöht (SOLLTE)

**What it checks:** SYS.2.1.A42 ergänzend: Für funktionierende Allowlists muss die Klassifizierung nahezu vollständig sein. Diese Kontrolle prüft, ob der Anteil unklassifizierter Anwendungen unter 10% liegt.

**Parameters:** `max_unclassified_percent`: `10`

**How to fix a failure:** Unklassifizierte Anwendungen auf betroffenen Endpoints überprüfen. Im Taxonomie-Editor unbekannte Software klassifizieren oder Fingerprints für wiederkehrende Anwendungen erstellen.

---

###### `BSI-SYS.2.1-EOL` — End-of-Life Software Identification

**Severity:** **HIGH**
 | **BSI Level:** Basis (MUSS)

**What it checks:** EOL-Software erhält keine Sicherheitsupdates und MUSS identifiziert werden. Diese Kontrolle nutzt endoflife.date Lebenszyklusdaten, um End-of-Life Software auf Endpoints zu erkennen.

**Parameters:** `flag_security_only`: `True`, `min_match_confidence`: `0.8`

**How to fix a failure:** EOL-Software durch unterstützte Versionen ersetzen. Informationen zu unterstützten Versionen unter endoflife.date.

---

###### `BSI-SYS.2.1.A9` — Festlegung einer Sicherheitsrichtlinie für Clients

**Severity:** **HIGH**
 | **BSI Level:** Basis (MUSS)

**What it checks:** SYS.2.1.A9 fordert die Durchsetzung der Sicherheitsrichtlinie für Clients. Diese Kontrolle erkennt Software, die als Prohibited klassifiziert ist, und erzwingt damit die Einhaltung der organisationsweiten Software-Richtlinie.

**Parameters:** None

**How to fix a failure:** Alle als Prohibited klassifizierten Anwendungen von betroffenen Endpoints entfernen. Untersuchen, wie die Software installiert wurde, und Sicherheitsrichtlinie durchsetzen.

---

##### APP.6 — Allgemeine Software

###### `BSI-APP.6.A1` — Planung des Software-Einsatzes

**Severity:** **HIGH**
 | **BSI Level:** Basis (MUSS)

**What it checks:** APP.6.A1 fordert eine Planung des Software-Einsatzes. Diese Kontrolle prüft, ob mindestens 85% der Anwendungen auf allen Endpoints klassifiziert sind, um ein vollständiges Software-Inventar sicherzustellen.

**Parameters:** `min_classified_percent`: `85`

**How to fix a failure:** Klassifizierungs-Engine auf allen unbearbeiteten Endpoints ausführen. In der Agents-Ansicht nach 'unclassified' filtern, um Endpoints mit geringer Klassifizierungsabdeckung zu finden.

---

###### `BSI-APP.6.A1-SYNC` — Software-Inventar — Aktualität

**Severity:** **HIGH**
 | **BSI Level:** Basis (MUSS)

**What it checks:** APP.6.A1 fordert ein aktuelles Software-Inventar. Diese Kontrolle prüft, ob der letzte Daten-Sync innerhalb von 24 Stunden abgeschlossen wurde, damit das Inventar den aktuellen Zustand der Endpoints widerspiegelt.

**Parameters:** `max_hours_since_sync`: `24`

**How to fix a failure:** In der Sync-Ansicht nach Fehlern oder blockierten Sync-Läufen prüfen. Sicherstellen, dass Sync-Zeitpläne aktiv sind und die SentinelOne-API-Verbindung funktioniert.

---

###### `BSI-APP.6.A2` — Erstellung eines Anforderungskatalogs

**Severity:** MEDIUM
 | **BSI Level:** Standard (SOLLTE)

**What it checks:** APP.6.A2 fordert einen Anforderungskatalog für Software. Diese Kontrolle prüft, ob die konfigurierten Pflicht-Anwendungen auf allen Clients installiert sind. Erfordert mandantenspezifische Konfiguration.

**Parameters:** `required_apps`: `[]`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Definieren Sie die Pflicht-Software unter Compliance > Einstellungen > BSI > BSI-APP.6.A2. Geben Sie die Anwendungsnamen an, die auf allen Clients vorhanden sein müssen.

---

###### `BSI-APP.6.A4` — Sicherstellung der Integrität von Software

**Severity:** **HIGH**
 | **BSI Level:** Basis (MUSS)

**What it checks:** APP.6.A4 fordert die Sicherstellung der Software-Integrität. Diese Kontrolle erkennt Software-Installationen und -Deinstallationen innerhalb der letzten 24 Stunden durch Vergleich aufeinanderfolgender Sync-Ergebnisse.

**Parameters:** `lookback_hours`: `24`

**How to fix a failure:** Erkannte Software-Änderungen in der Anomalien-Ansicht prüfen. Sicherstellen, dass alle Änderungen über den Änderungsmanagement-Prozess autorisiert wurden.

---

###### `BSI-APP.6.A5` — Deinstallation nicht benötigter Software

**Severity:** MEDIUM
 | **BSI Level:** Standard (SOLLTE)

**What it checks:** APP.6.A5 fordert die Deinstallation nicht benötigter Software. Diese Kontrolle prüft, ob der Anteil unklassifizierter Anwendungen unter 5% liegt — unklassifizierte Software gilt als potenziell nicht benötigt.

**Parameters:** `max_unclassified_percent`: `5`

**How to fix a failure:** Unklassifizierte Anwendungen auf betroffenen Endpoints prüfen. Im Taxonomie-Editor klassifizieren oder nicht-benötigte Software deinstallieren.

---

##### OPS.1.1.3 — Patch-Management

###### `BSI-OPS.1.1.3.A1` — Konzept für Patch- und Änderungsmanagement

**Severity:** **HIGH**
 | **BSI Level:** Basis (MUSS)

**What it checks:** OPS.1.1.3.A1 fordert ein Konzept für Patch-Management. Diese Kontrolle prüft, ob der Anteil veralteter Anwendungen unter 10% liegt, indem installierte Versionen gegen die Library-Baseline verglichen werden.

**Parameters:** `max_outdated_percent`: `10`

**How to fix a failure:** Veraltete Anwendungen auf aktuelle Versionen aktualisieren. In der Library-Ansicht installierte Versionen mit der Baseline vergleichen und Updates priorisieren.

---

###### `BSI-OPS.1.1.3.A15` — Regelmäßige Aktualisierung der IT

**Severity:** **HIGH**
 | **BSI Level:** Standard (SOLLTE)

**What it checks:** OPS.1.1.3.A15 fordert regelmäßige Aktualisierung der IT. Diese Kontrolle prüft mit einem strengeren Schwellenwert von 5%, ob installierte Software-Versionen aktuell sind, und unterstützt die Analyse der Software-Altersstruktur.

**Parameters:** `max_outdated_percent`: `5`

**How to fix a failure:** Veraltete und EOL-Software durch unterstützte Versionen ersetzen. In der Library-Ansicht die Altersstruktur der installierten Software analysieren.

---

###### `BSI-OPS.1.1.3.A15-EDR` — EDR-Agent Aktualisierung

**Severity:** **CRITICAL**
 | **BSI Level:** Basis (MUSS)

**What it checks:** OPS.1.1.3.A15 fordert aktuelle EDR-Agents im Rahmen des Patch-Managements. Diese Kontrolle prüft, ob der SentinelOne Agent auf allen Endpoints die aktuelle Fleet-Baseline-Version hat, damit Bedrohungserkennung auf dem neuesten Stand ist.

**Parameters:** None

**How to fix a failure:** SentinelOne Agent auf die aktuelle Fleet-Baseline-Version aktualisieren. Verwenden Sie die SentinelOne-Konsole, um Agent-Upgrades für nicht-konforme Endpoints zu planen.

---

### DORA — Digital Operational Resilience Act

**Version:** EU 2022/2554

The Digital Operational Resilience Act (DORA) is an EU regulation that strengthens the digital resilience of financial entities by standardizing ICT risk management, third-party oversight, incident reporting, and resilience testing. Sentora covers the endpoint software management aspects of DORA — specifically ICT asset identification (Art. 8), protection and prevention (Art. 9), detection (Art. 10), business continuity (Art. 11), and third-party software risk (Art. 28).

> **Disclaimer**
> Sentora evaluates DORA compliance exclusively from the perspective of endpoint software inventory, classification, and enforcement. DORA encompasses broader requirements including ICT incident reporting (Art. 17-19), digital operational resilience testing (Art. 24-27), ICT third-party contractual arrangements (Art. 28-30), and information sharing (Art. 45) that are outside Sentora's scope. This module does not constitute legal advice. Financial entities should consult qualified legal and compliance professionals for full DORA compliance assessment.

<!-- TODO: Write framework_dora section in docs/handbook_content/framework_dora.md -->

#### Controls

| Control ID | Title | Check Type | Severity | Config Required |
|---|---|---|---|---|
| `DORA-8.1-01` | ICT Asset Inventory Completeness | `classification_coverage_check` | **CRITICAL** | No |
| `DORA-8.1-02` | ICT Asset Classification Coverage | `unclassified_threshold_check` | **HIGH** | No |
| `DORA-8.4-01` | Critical ICT Asset Identification | `required_app_check` | **HIGH** | Yes |
| `DORA-8.6-01` | ICT Inventory Freshness | `sync_freshness_check` | **HIGH** | No |
| `DORA-8.2-01` | ICT Risk Source Detection | `delta_detection_check` | MEDIUM | No |
| `DORA-8.7-01` | Legacy ICT System Assessment | `eol_software_check` | **HIGH** | No |
| `DORA-9.1-01` | Endpoint Security Monitoring Active | `agent_online_check` | **CRITICAL** | No |
| `DORA-9.2-01` | EDR Protection on All Endpoints | `required_app_check` | **CRITICAL** | Yes |
| `DORA-9.2-02` | Encryption Software Present | `required_app_check` | **HIGH** | Yes |
| `DORA-9.3-01` | Unauthorized Software Restriction | `prohibited_app_check` | **CRITICAL** | No |
| `DORA-9.3-02` | ICT Change Detection | `delta_detection_check` | MEDIUM | No |
| `DORA-9.4-01` | Security Agent Version Currency | `agent_version_check` | **HIGH** | No |
| `DORA-9.4-02` | Software Patch Currency | `app_version_check` | MEDIUM | No |
| `DORA-10.1-01` | Software Change Anomaly Detection | `delta_detection_check` | **HIGH** | No |
| `DORA-10.1-02` | Unclassified Software Anomaly | `unclassified_threshold_check` | MEDIUM | No |
| `DORA-11.1-01` | Endpoint Monitoring Continuity | `agent_online_check` | **HIGH** | No |
| `DORA-11.2-01` | Data Collection Continuity | `sync_freshness_check` | MEDIUM | No |
| `DORA-28.1-01` | Third-Party Software Inventory | `classification_coverage_check` | **HIGH** | No |
| `DORA-28.1-02` | Unapproved Third-Party Software | `prohibited_app_check` | **CRITICAL** | No |
| `DORA-28.3-01` | Third-Party Software Documentation | `unclassified_threshold_check` | **HIGH** | No |

#### Control Details

##### ICT Asset Identification (Art. 8)

###### `DORA-8.1-01` — ICT Asset Inventory Completeness

**Severity:** **CRITICAL**

**What it checks:** Art. 8(1) requires financial entities to identify, classify, and document all ICT assets. This control verifies that the classification engine has processed all managed endpoints, ensuring no ICT assets remain unidentified in the inventory.

**Parameters:** `min_classified_percent`: `95`

**How to fix a failure:** Run the classification engine on all unprocessed agents. Review the Agents view and filter by 'unclassified' to find endpoints missing classification results.

---

###### `DORA-8.1-02` — ICT Asset Classification Coverage

**Severity:** **HIGH**

**What it checks:** Art. 8(1) mandates that ICT assets are classified. This control checks that the percentage of unclassified applications per endpoint remains below the threshold, ensuring applications are properly categorized as part of the ICT asset register.

**Parameters:** `max_unclassified_percent`: `5`

**How to fix a failure:** Review unclassified applications on flagged endpoints. Use the taxonomy editor to classify unknown software or create fingerprints for recurring unclassified applications.

---

###### `DORA-8.4-01` — Critical ICT Asset Identification

**Severity:** **HIGH**

**What it checks:** Art. 8(4) requires financial entities to identify and map all information and ICT assets, with special attention to critical assets. This control verifies that configured critical ICT applications are present on all managed endpoints. Requires tenant-specific configuration of which applications constitute critical ICT assets.

**Parameters:** `required_apps`: `[]`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the required critical ICT applications for this control in Compliance > Settings > DORA > DORA-8.4-01. Specify the application names that must be present on all endpoints (e.g. asset management agents, monitoring tools).

---

###### `DORA-8.6-01` — ICT Inventory Freshness

**Severity:** **HIGH**

**What it checks:** Art. 8(6) requires maintained inventories to be updated periodically and after major changes. This control checks that the most recent data sync completed within the configured time window, ensuring the ICT asset inventory reflects the current state of managed endpoints.

**Parameters:** `max_hours_since_sync`: `24`

**How to fix a failure:** Ensure sync schedules are active and completing successfully. Check the Sync view for errors or stalled sync runs. Verify the SentinelOne API connection is functional.

---

###### `DORA-8.2-01` — ICT Risk Source Detection

**Severity:** MEDIUM

**What it checks:** Art. 8(2) requires continuous identification of all sources of ICT risk. This control detects new or removed applications between sync windows, flagging changes in the ICT asset landscape that may introduce new risk sources.

**Parameters:** `lookback_hours`: `24`

**How to fix a failure:** Review newly detected applications in the Anomalies view. Classify new software and assess whether it introduces additional ICT risk. Investigate any unexpected removals.

---

###### `DORA-8.7-01` — Legacy ICT System Assessment

**Severity:** **HIGH**

**What it checks:** Art. 8(7) requires yearly ICT risk assessment on all legacy ICT systems. This control uses endoflife.date lifecycle data to detect End-of-Life software that qualifies as legacy ICT no longer receiving security patches.

**Parameters:** `flag_security_only`: `True`, `min_match_confidence`: `0.8`

**How to fix a failure:** Upgrade or replace End-of-Life software with supported alternatives. For legacy systems that cannot be updated, document compensating controls as required by Art. 8(7). See endoflife.date for supported version information.

---

##### ICT Protection & Prevention (Art. 9)

###### `DORA-9.1-01` — Endpoint Security Monitoring Active

**Severity:** **CRITICAL**

**What it checks:** Art. 9(1) requires continuous monitoring and control of the security of ICT systems. This control verifies that all managed endpoints have checked in within the configured time window, ensuring security monitoring coverage is not interrupted by offline agents.

**Parameters:** `max_offline_days`: `3`

**How to fix a failure:** Investigate offline endpoints immediately. Check network connectivity, verify the SentinelOne agent service is running, and restore communication with the management console. Offline endpoints cannot be monitored or protected.

---

###### `DORA-9.2-01` — EDR Protection on All Endpoints

**Severity:** **CRITICAL**

**What it checks:** Art. 9(2) requires deployment of ICT security tools that ensure resilience, continuity, and availability. This control verifies that the configured EDR solution is installed on all endpoints. Requires tenant-specific configuration of which EDR product to check.

**Parameters:** `required_apps`: `[]`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the required EDR software for this control in Compliance > Settings > DORA > DORA-9.2-01. Specify the EDR product name (e.g. 'SentinelOne'). Then deploy the EDR agent to all endpoints missing it.

---

###### `DORA-9.2-02` — Encryption Software Present

**Severity:** **HIGH**

**What it checks:** Art. 9(2) requires ICT security tools ensuring confidentiality of data. This control verifies that the configured encryption software is installed on all endpoints. Requires tenant-specific configuration of which encryption tool to check.

**Parameters:** `required_apps`: `[]`

> **Configuration required:** This control needs tenant-specific configuration before it produces results. Until configured, it returns `not_applicable`.

**How to fix a failure:** Configure the required encryption software for this control in Compliance > Settings > DORA > DORA-9.2-02. Specify the encryption product name (e.g. 'BitLocker', 'FileVault'). Then deploy encryption to all endpoints missing it.

---

###### `DORA-9.3-01` — Unauthorized Software Restriction

**Severity:** **CRITICAL**

**What it checks:** Art. 9(3c) requires limiting access to ICT assets to what is required for approved functions. This control detects any applications classified as Prohibited on managed endpoints, enforcing software authorization policies.

**Parameters:** None

**How to fix a failure:** Remove all prohibited applications from affected endpoints immediately. Review the taxonomy to ensure the prohibited classification is current. Investigate how unauthorized software was installed.

---

###### `DORA-9.3-02` — ICT Change Detection

**Severity:** MEDIUM

**What it checks:** Art. 9(3e) requires implementation of ICT change management. This control detects software changes between sync windows, supporting change management by flagging new installations and removals for review.

**Parameters:** `lookback_hours`: `24`

**How to fix a failure:** Review detected software changes in the Anomalies view. Verify that all changes were authorized through the organization's change management process.

---

###### `DORA-9.4-01` — Security Agent Version Currency

**Severity:** **HIGH**

**What it checks:** Art. 9(4) requires implementation of patch and update management. This control checks that the SentinelOne agent version is current across all managed endpoints, ensuring the security platform itself is not running outdated or vulnerable versions.

**Parameters:** None

**How to fix a failure:** Update the SentinelOne agent to the current fleet baseline version on all non-compliant endpoints. Use the SentinelOne console to schedule agent upgrades.

---

###### `DORA-9.4-02` — Software Patch Currency

**Severity:** MEDIUM

**What it checks:** Art. 9(4) requires patch and update management for all ICT systems. This control checks that installed application versions are current against the library baseline, detecting endpoints running outdated software that may contain known vulnerabilities.

**Parameters:** `max_outdated_percent`: `15`

**How to fix a failure:** Update outdated applications to their current versions. Prioritize updates for applications with known vulnerabilities. Use the Library view to compare installed versions against the baseline.

---

##### ICT Anomaly Detection (Art. 10)

###### `DORA-10.1-01` — Software Change Anomaly Detection

**Severity:** **HIGH**

**What it checks:** Art. 10(1) requires implementation of tools to detect anomalous activities and allocate resources to monitor user behavior and ICT anomalies. This control detects new or removed software between sync windows as potential anomalous changes in the ICT environment.

**Parameters:** `lookback_hours`: `24`

**How to fix a failure:** Review all software changes detected in the Anomalies view. Investigate unexpected installations or removals. Escalate anomalous changes per the organization's incident response procedures.

---

###### `DORA-10.1-02` — Unclassified Software Anomaly

**Severity:** MEDIUM

**What it checks:** Art. 10(1) requires monitoring for ICT anomalies. Unclassified software on endpoints represents potentially anomalous or unauthorized applications. This control flags endpoints where the proportion of unclassified applications exceeds the acceptable threshold.

**Parameters:** `max_unclassified_percent`: `10`

**How to fix a failure:** Classify unknown applications on flagged endpoints. Investigate whether unclassified software is authorized. Create fingerprints for legitimate applications to prevent future false positives.

---

##### ICT Business Continuity (Art. 11)

###### `DORA-11.1-01` — Endpoint Monitoring Continuity

**Severity:** **HIGH**

**What it checks:** Art. 11(1) requires ICT business continuity policies that ensure monitoring capabilities remain operational. This control checks that all agents have checked in within a wider tolerance window, detecting endpoints that have lost connectivity to the management platform.

**Parameters:** `max_offline_days`: `7`

**How to fix a failure:** Investigate endpoints offline for more than 7 days. Verify whether the endpoint is decommissioned, has connectivity issues, or requires agent reinstallation. Update the agent inventory to reflect current state.

---

###### `DORA-11.2-01` — Data Collection Continuity

**Severity:** MEDIUM

**What it checks:** Art. 11(2) requires backup policies and data restoration methods. This control verifies that data collection (sync) has completed within the configured window, ensuring continuous visibility into the endpoint fleet is maintained for business continuity purposes.

**Parameters:** `max_hours_since_sync`: `48`

**How to fix a failure:** Check the Sync view for errors or stalled sync runs. Ensure sync schedules are configured and the SentinelOne API connection is healthy. If syncs are failing, consult the troubleshooting guide.

---

##### ICT Third-Party Software Risk (Art. 28)

###### `DORA-28.1-01` — Third-Party Software Inventory

**Severity:** **HIGH**

**What it checks:** Art. 28(1) requires managing ICT third-party risk as an integral part of the ICT risk framework. This control verifies that the classification engine has processed all endpoints, ensuring third-party software is identified and inventoried across the managed fleet.

**Parameters:** `min_classified_percent`: `90`

**How to fix a failure:** Run the classification engine on all unprocessed agents to ensure third-party software is identified. Review classification results and update taxonomy categories for accurate third-party software tracking.

---

###### `DORA-28.1-02` — Unapproved Third-Party Software

**Severity:** **CRITICAL**

**What it checks:** Art. 28(1) requires managing third-party ICT risk. This control detects prohibited third-party software on managed endpoints, enforcing the organization's approved software policy for third-party applications.

**Parameters:** None

**How to fix a failure:** Remove all prohibited third-party applications from affected endpoints. Review the organization's approved software list and update the taxonomy to reflect current third-party software policies.

---

###### `DORA-28.3-01` — Third-Party Software Documentation

**Severity:** **HIGH**

**What it checks:** Art. 28(3) requires maintaining a register of all contractual arrangements with ICT third-party providers. This control checks that the proportion of unclassified applications is minimized, ensuring third-party software is documented and categorized in the taxonomy.

**Parameters:** `max_unclassified_percent`: `3`

**How to fix a failure:** Classify all unclassified applications on flagged endpoints. Map third-party software to their providers in the taxonomy. Ensure the software register aligns with the contractual arrangements register.

---

## Check Type Reference

### `prohibited_app_check` — Prohibited Application Check

**Implementation:** `backend/domains/compliance/checks/prohibited_app.py`

Detects applications classified as Prohibited on managed endpoints. Uses the installed_apps collection filtered by risk_level='prohibited', cross-referenced with the scoped agent set.

**Parameters:**

None required. Uses classification data from the taxonomy.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** No agents in scope have prohibited applications installed.

**Fail:** One or more agents have prohibited apps — each app/agent pair generates a violation.

**0 agents in scope:** Returns not_applicable with 'No agents in scope'.

**Data sources:** `agents, installed_apps (risk_level field), classification_results`

---

### `required_app_check` — Required Application Check

**Implementation:** `backend/domains/compliance/checks/required_app.py`

Verifies that all scoped endpoints have specific applications installed. Uses case-insensitive substring matching against the agent's installed_app_names.

**Parameters:**

- `required_apps` (list[str], required): Application name patterns to check. Empty list returns not_applicable.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** All agents in scope have every required application installed.

**Fail:** One or more agents are missing a required application.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents (installed_app_names field)`

---

### `agent_online_check` — Agent Online Check

**Implementation:** `backend/domains/compliance/checks/agent_online.py`

Identifies agents that have not checked in within a configurable number of days. Compares last_active timestamp against the configured threshold.

**Parameters:**

- `max_offline_days` (int, default 7): Maximum days since last check-in.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** All agents in scope checked in within max_offline_days.

**Fail:** One or more agents have not checked in within the threshold.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents (last_active field)`

---

### `agent_version_check` — Agent Version Check

**Implementation:** `backend/domains/compliance/checks/agent_version.py`

Compares SentinelOne agent versions against either a configured minimum version or the most common version in the fleet (auto-detected baseline).

**Parameters:**

- `min_version` (str, optional): Explicit minimum version string. If absent, the most common version across scoped agents is used as the baseline.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** All agents at or above the baseline version.

**Fail:** One or more agents running a version below the baseline.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents (agent_version field)`

---

### `app_version_check` — Application Version Check

**Implementation:** `backend/domains/compliance/checks/app_version.py`

Identifies endpoints running outdated application versions by comparing installed versions against the most common version per application (fleet standard).

**Parameters:**

- `max_outdated_percent` (float, default 20): Percentage threshold. Below this, the check warns; above, it fails.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** No endpoints have outdated application versions.

**Fail:** Outdated percentage exceeds max_outdated_percent threshold.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents, installed_apps (normalized_name, version fields)`

---

### `sync_freshness_check` — Sync Freshness Check

**Implementation:** `backend/domains/compliance/checks/sync_freshness.py`

Verifies that the most recent completed data sync is within the configured time window. This is a global check — it evaluates the last sync run, not per-agent freshness.

**Parameters:**

- `max_hours_since_sync` (int, default 24): Maximum hours since last completed sync.

**Scope behavior:** Global check. Scope filter only affects agent count in evidence summary.

**Pass:** Last completed sync is within max_hours_since_sync.

**Fail:** No completed syncs, or last sync exceeds the time window.

**0 agents in scope:** Still evaluates (global check). Returns fail if no syncs exist.

**Data sources:** `sync_runs (status, completed_at fields)`

---

### `classification_coverage_check` — Classification Coverage Check

**Implementation:** `backend/domains/compliance/checks/classification_coverage.py`

Verifies that a sufficient percentage of scoped agents have classification results. Agents without classification represent unknown risk.

**Parameters:**

- `min_classified_percent` (float, default 90): Minimum coverage percentage. Below 80% of threshold = fail; between 80%-100% of threshold = warning; above = pass.

**Scope behavior:** Resolves scoped agent IDs via agents, then counts matching classification_results.

**Pass:** Classification coverage meets or exceeds min_classified_percent.

**Fail:** Coverage is below 80% of the threshold.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents, classification_results (agent_id field)`

---

### `unclassified_threshold_check` — Unclassified Threshold Check

**Implementation:** `backend/domains/compliance/checks/unclassified_threshold.py`

Monitors the percentage of unclassified applications per endpoint. Uses app_summaries to determine which applications have been classified.

**Parameters:**

- `max_unclassified_percent` (float, default 10): Maximum allowed percentage of unclassified apps per endpoint.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** All endpoints have unclassified app percentage below threshold.

**Fail:** One or more endpoints exceed the unclassified threshold.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents (installed_app_names), app_summaries (normalized_name, category)`

---

### `delta_detection_check` — Delta Detection Check

**Implementation:** `backend/domains/compliance/checks/delta_detection.py`

Detects new application installations within a configurable lookback window. New apps are identified by last_synced_at timestamp on installed_apps.

**Parameters:**

- `lookback_hours` (int, default 24): Window to check for new installations.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** No new applications detected in the lookback window.

**Fail:** N/A — this check returns warning (not fail) when changes are detected.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents, installed_apps (last_synced_at field)`

---

### `custom_app_presence_check` — Custom Application Presence Check

**Implementation:** `backend/domains/compliance/checks/custom_app_presence.py`

Verifies that a specific application (by glob-style pattern) is present or absent on scoped endpoints. Supports both must-exist and must-not-exist modes.

**Parameters:**

- `app_pattern` (str, required): Glob-style pattern (e.g. 'BitLocker*'). Empty pattern returns not_applicable.
- `must_exist` (bool, default True): If True, app must be present; if False, app must be absent.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** All endpoints match the presence/absence requirement.

**Fail:** One or more endpoints violate the presence/absence requirement.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents (installed_app_names field)`

---

### `eol_software_check` — End-of-Life Software Check

**Implementation:** `backend/domains/compliance/checks/eol_software.py`

Identifies applications that have reached End-of-Life status using pre-computed EOL match data from the endoflife.date lifecycle database. Only considers CPE and manual matches above the confidence threshold.

**Parameters:**

- `flag_security_only` (bool, default True): Also flag apps in security-only phase.
- `min_match_confidence` (float, default 0.8): Minimum match confidence threshold.
- `exclude_products` (list[str], optional): Product IDs to skip.

**Scope behavior:** Respects scope_tags and scope_groups via agents filter.

**Pass:** No EOL software detected on scoped endpoints.

**Fail:** One or more scoped endpoints have EOL software installed.

**0 agents in scope:** Returns not_applicable.

**Data sources:** `agents, installed_apps, app_summaries (eol_match field)`

---

## Configuration Guide

### Configuring Scope Per Control

Every control can be scoped to a subset of your endpoint fleet using SentinelOne tags and groups.

1. Go to **Compliance > Settings > [Framework] > [Control ID]**
2. **Scope Tags**: Enter one or more SentinelOne tags. Only agents with at least one matching tag are checked.
3. **Scope Groups**: Enter one or more SentinelOne group names. Only agents in these groups are checked.
4. If both tags and groups are specified, an agent must match at least one tag AND be in one of the specified groups.
5. Leave both empty to check all managed endpoints.

### Adjusting Thresholds

Many controls use configurable thresholds. To adjust:

1. Go to **Compliance > Settings > [Framework] > [Control ID]**
2. Modify the threshold parameter (e.g. `max_offline_days`, `min_classified_percent`)
3. Click **Save**
4. Run a compliance check to see the updated results

**Examples:**
- Lower `max_unclassified_percent` from 10% to 5% for stricter classification requirements
- Increase `max_offline_days` from 7 to 14 if your organization has endpoints that go offline for extended periods (e.g. field laptops)
- Set `min_version` explicitly instead of using auto-detected fleet baseline

### Enabling/Disabling Individual Controls

1. Go to **Compliance > Settings > [Framework]**
2. Toggle the control on or off
3. Disabled controls do not run, do not appear in results, and do not affect the framework score

### Creating Custom Controls

You can create additional controls that use the same check types as built-in controls:

1. Go to **Compliance > Settings > Custom Controls**
2. Click **Create Custom Control**
3. Fill in:
   - **ID**: Must start with `custom-` (e.g. `custom-vpn-check`)
   - **Framework**: Which framework this control belongs to
   - **Check Type**: Which check to run
   - **Parameters**: Configure the check parameters
   - **Scope**: Optional tags and groups
4. Click **Create**

### Schedule Configuration

1. Go to **Compliance > Settings > Schedule**
2. Configure:
   - **Run after sync**: Automatically run compliance checks after each data sync (default: on)
   - **Cron expression**: Optional additional schedule (e.g. `0 6 * * *` for daily at 06:00 UTC)
   - **Enabled**: Master toggle for the schedule

## Troubleshooting

### Control Shows "not_applicable"

**Cause:** The control has no agents in scope, or it requires configuration.

**Fix:**
1. Check if the control has scope tags/groups that don't match any agents
2. Check if the control needs configuration (e.g. empty `required_apps` or `app_pattern`)
3. Verify that agents exist in the database — run a sync if the fleet is empty

### Control Shows "error"

**Cause:** The check execution failed due to a runtime error.

**Fix:**
1. Check the evidence_summary for the error message
2. Common causes:
   - MongoDB connectivity issues during check execution
   - Corrupt data in agent or app collections
   - Invalid parameter values (e.g. non-numeric threshold)
3. Re-run the compliance check. If the error persists, check the backend logs.

### Score Seems Wrong

**Debug steps:**
1. Go to **Compliance > Dashboard** and note the framework score
2. Click the framework card to see individual control results
3. Verify: Score = Passed / (Total - Not Applicable) x 100
4. Check if disabled controls are correctly excluded
5. Check if `not_applicable` controls are correctly excluded from the denominator
6. If a control shows `pass` but you expect `fail` (or vice versa), click into the control detail to see violations

### Violations Appearing for Wrong Agents

**Cause:** Scope configuration may not match your expectations.

**Fix:**
1. Check the control's scope configuration in **Compliance > Settings**
2. Verify agent tags in SentinelOne match the scope tags configured in Sentora
3. Remember: empty scope = all agents. If you recently removed a scope restriction, the control now checks everything.

### Stale Results (Last Checked Too Long Ago)

**Cause:** Compliance checks haven't run recently.

**Fix:**
1. Check **Compliance > Settings > Schedule** — is the schedule enabled?
2. Check **Sync** view — are syncs completing? Compliance runs after sync by default.
3. Trigger a manual run from **Compliance > Dashboard > Run Checks**

### Performance: Compliance Checks Running Too Slow

Sentora's compliance engine deduplicates identical checks across frameworks. If multiple controls use the same check type with the same parameters and scope, the query runs only once.

**If checks are still slow:**
1. Check your fleet size — 150K+ endpoints will naturally take longer
2. Ensure MongoDB indexes are created (they are applied on startup)
3. Consider disabling frameworks you don't need to reduce the number of active controls
4. Check MongoDB performance metrics for slow queries

## Audit & Evidence

### Exporting Compliance Results

To export violations for auditor review:

1. Go to **Compliance > Violations**
2. Filter by framework and/or severity as needed
3. Click **Export CSV**

The CSV includes: Framework, Control ID, Control Name, Severity, Agent ID, Hostname, Violation Detail, Application, Version, Remediation, Checked At.

### Interpreting the Dashboard for Audit Evidence

The compliance dashboard provides evidence of:
- **Continuous monitoring**: Timestamps showing regular compliance check execution
- **Control coverage**: Number of controls evaluated per framework
- **Compliance posture**: Pass/fail/warning breakdown per framework
- **Violation tracking**: Specific non-compliant endpoints with remediation guidance

**For SOC 2 audits**: The dashboard demonstrates Trust Services Criteria monitoring. Export results before and after remediation to show progress.

**For PCI DSS assessments**: Filter to the PCI DSS framework. CDE-scoped controls demonstrate focused protection of cardholder data environments.

**For HIPAA assessments**: Filter to the HIPAA framework. ePHI-scoped controls show safeguards applied specifically to systems processing electronic Protected Health Information.

**For BSI IT-Grundschutz**: Filter to the BSI framework. Controls are mapped to specific Bausteine and Anforderungen with the requirement level (Basis/Standard/Erhöht) indicated.

**For DORA assessments**: Filter to the DORA framework. Controls map to specific DORA articles covering ICT asset identification, protection, detection, and business continuity.

### What Sentora Reports vs. What the Auditor Still Needs

| Sentora Provides | Auditor Must Verify Independently |
|---|---|
| Software inventory completeness | Network architecture and segmentation |
| Application classification status | Access control policies and procedures |
| EDR agent deployment and version | Incident response plans and testing |
| Prohibited software detection | Employee training and awareness programs |
| Change detection (software) | Physical security controls |
| Patch currency (application versions) | Vendor management and contracts |
| End-of-Life software identification | Risk assessment methodology |
| Data sync freshness | Backup and recovery testing |

### Per-Framework Disclaimer Text

**Include these disclaimers when presenting Sentora compliance data to auditors:**

**SOC 2**: "These checks support evidence collection for SOC 2 audits. They do not constitute SOC 2 certification. Full compliance requires assessment by a licensed CPA firm."

**PCI DSS**: "PCI DSS compliance requires validation by a Qualified Security Assessor (QSA). Sentora provides evidence and monitoring for endpoint-related requirements, not certification."

**HIPAA**: "HIPAA compliance is determined by the U.S. Department of Health and Human Services. Sentora provides technical safeguard monitoring for endpoint software management."

**BSI IT-Grundschutz**: "BSI IT-Grundschutz-Konformitat erfordert eine vollstandige Grundschutz-Prufung durch einen zertifizierten BSI-Auditor. Sentora uberwacht die Endpoint-Software-Management-Anforderungen und liefert Evidenz fur Audits."

**DORA**: "Sentora evaluates DORA compliance exclusively from the perspective of endpoint software inventory, classification, and enforcement. DORA encompasses broader requirements that are outside Sentora's scope. This module does not constitute legal advice."

## Glossary

| Term | Definition |
|---|---|
| **Agent** | A SentinelOne agent installed on a managed endpoint. Sentora syncs agent data from the SentinelOne management console. |
| **Approved** | An application classification indicating the software is authorized for use on managed endpoints. |
| **BSI IT-Grundschutz** | The German federal standard for information security published by the Bundesamt fur Sicherheit in der Informationstechnik (BSI). |
| **CDE** | Cardholder Data Environment — systems that store, process, or transmit cardholder data (PCI DSS term). |
| **Check Type** | The implementation that evaluates a compliance control. Each check type queries specific data and produces a pass/fail/warning result. |
| **Classification** | The process of categorizing installed applications as Approved, Flagged, Prohibited, or leaving them unclassified. |
| **Compliance Score** | Percentage of passing controls out of all applicable controls for a framework. Formula: Passed / (Total - Not Applicable) x 100. |
| **Control** | A specific compliance requirement mapped to an automated check. Each control belongs to one framework. |
| **DORA** | Digital Operational Resilience Act — EU regulation (2022/2554) for digital resilience of financial entities. |
| **Endpoint** | A managed device (workstation, laptop, server) with a SentinelOne agent installed. |
| **End-of-Life (EOL)** | Software that no longer receives security patches or updates from the vendor. |
| **ePHI** | Electronic Protected Health Information — health data in electronic form protected under HIPAA. |
| **Enforcement** | Sentora's rule-based violation detection module. Distinct from compliance but feeds into the unified violations view. |
| **Fleet** | The entire set of managed endpoints visible to Sentora through SentinelOne. |
| **Fleet Baseline** | The most common version of an application or agent across the fleet, used as the comparison standard. |
| **Flagged** | An application classification indicating the software is under review or warrants attention. |
| **Framework** | A compliance standard (SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA) with its set of controls. |
| **HIPAA** | Health Insurance Portability and Accountability Act — U.S. federal law protecting electronic health information. |
| **not_applicable** | A check result status indicating the control cannot be evaluated (no agents in scope, or unconfigured). Does not affect the compliance score. |
| **PCI DSS** | Payment Card Industry Data Security Standard — requirements for protecting cardholder data. |
| **Prohibited** | An application classification indicating the software must not be installed on managed endpoints. |
| **Scope** | The subset of endpoints a control checks, defined by SentinelOne tags and/or groups. |
| **SOC 2** | Service Organization Control 2 — AICPA framework for security, availability, processing integrity, confidentiality, and privacy. |
| **Sync** | The data synchronization process that pulls agent and application data from SentinelOne into Sentora. |
| **Taxonomy** | Sentora's application classification system for categorizing software. |
| **Violation** | A specific finding where an endpoint does not meet a control's requirements. |
