# Incident Response Plan

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-IR-001                                |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Security & Compliance Team                 |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Purpose

This Incident Response (IR) plan establishes procedures for detecting, responding to,
and recovering from information security incidents affecting the Sentora platform.
The plan follows NIST SP 800-61 Rev. 2 guidelines and implements a six-phase approach
to incident management.

---

## 2. Scope

This plan covers security incidents related to:

- Unauthorized access to Sentora systems or data
- Data breaches involving classified information (see `docs/compliance/data-classification.md`)
- Denial of service attacks against Sentora infrastructure
- Compromise of authentication credentials (JWT secrets, API tokens, user passwords)
- Malicious exploitation of application vulnerabilities
- Insider threats and policy violations
- Supply chain attacks via compromised dependencies
- SentinelOne API integration security events

---

## 3. Incident Severity Classification

| Severity | Label | Description | Response Time | Examples |
|----------|-------|-------------|---------------|----------|
| P1 | **Critical** | Active exploitation, data breach, complete system compromise | Immediate (< 15 min) | Restricted data exfiltration, authentication bypass, database compromise |
| P2 | **High** | Confirmed vulnerability being exploited, significant data exposure risk | < 1 hour | Unauthorized admin access, credential stuffing success, S1 token compromise |
| P3 | **Medium** | Attempted attack detected, limited exposure, contained threat | < 4 hours | Brute force detected and blocked, rate limiting triggered abnormally, suspicious API patterns |
| P4 | **Low** | Policy violation, minor misconfiguration, informational security event | < 24 hours | Dormant account access attempt, failed 2FA verification spike, CORS violation logged |

---

## 4. Roles and Responsibilities

| Role | Title | Responsibilities |
|------|-------|------------------|
| **Incident Commander (IC)** | Security Lead / Super Admin | Overall incident ownership, decision authority, communications |
| **Technical Lead** | Senior Developer | Technical investigation, containment implementation, system recovery |
| **Communications Lead** | Product Owner | Stakeholder notification, status updates, external communications |
| **Forensics Analyst** | Security Engineer | Evidence collection, log analysis, root cause investigation |
| **Scribe** | Assigned team member | Real-time documentation of actions, decisions, and timeline |

---

## 5. Phase 1 — Preparation

### 5.1 Detection Infrastructure

The following Sentora components provide incident detection capabilities:

| Component | Location | Detection Capability |
|-----------|----------|---------------------|
| Audit logging | MongoDB `audit_logs` collection | Security event recording with hash-chain integrity |
| Prometheus metrics | `/metrics` endpoint, `backend/middleware/metrics.py` | Anomalous request pattern detection (rate spikes, error rate increases) |
| Structured logging | `RequestLoggingMiddleware` | Correlation ID tracing, JSON-format analysis |
| Health probes | `/health`, `/health/ready` | System availability monitoring |
| Rate limiting | Per-IP sliding window middleware | Automated abuse detection and blocking |
| Account lockout | Auth service | Brute force detection (5 failed attempts) |
| OpenTelemetry | `backend/middleware/tracing.py` (opt-in) | Distributed request tracing |

### 5.2 Communication Channels

| Channel | Purpose | Participants |
|---------|---------|-------------|
| Primary (secure messaging) | Real-time incident coordination | IR team |
| Secondary (email) | Stakeholder notifications, status updates | Extended team, management |
| Webhook notifications | Automated alerting | Monitoring integrations |
| Out-of-band (phone) | Escalation when primary channels compromised | IC, Technical Lead |

### 5.3 Preparation Checklist

- [ ] IR team contact information current and accessible offline
- [ ] Runbooks for common incident types reviewed within last quarter
- [ ] Backup and restore procedures tested within last quarter
- [ ] Audit log collection verified functional
- [ ] Rate limiting and lockout thresholds reviewed
- [ ] Dependency vulnerability scans running in CI (`pip-audit`, `npm audit`)
- [ ] Access to MongoDB backup snapshots confirmed
- [ ] JWT_SECRET_KEY rotation procedure documented and tested
- [ ] S1_API_TOKEN rotation procedure documented
- [ ] Incident response tabletop exercise conducted within last 6 months

---

## 6. Phase 2 — Detection and Analysis

### 6.1 Detection Sources

| Source | Indicators | Monitoring Method |
|--------|-----------|-------------------|
| Audit logs | Unusual login patterns, privilege escalation, mass data access | Log analysis / SIEM |
| Prometheus metrics | Request rate anomalies, error rate spikes, latency increases | Alerting rules |
| Rate limiting | IP addresses hitting rate limits repeatedly | Rate limit event logs |
| Account lockout | Multiple accounts locked in short timeframe | Audit log correlation |
| Health probes | Unexpected 503 responses on readiness probe | Uptime monitoring |
| CI/CD pipeline | New CVE detected in dependency scan | `pip-audit` / `npm audit` alerts |
| External reports | Vulnerability report via `SECURITY.md` process | Security email / form |

### 6.2 Analysis Procedures

#### 6.2.1 Initial Triage

1. **Verify the event:** Confirm the alert is not a false positive
   - Check audit logs for the reported timeframe
   - Correlate with Prometheus metrics for anomalous patterns
   - Use correlation IDs to trace specific requests
2. **Classify severity:** Assign P1-P4 based on criteria in Section 3
3. **Assign IC:** Designate Incident Commander based on severity and availability
4. **Open incident record:** Create incident document with initial findings

#### 6.2.2 Evidence Collection

| Evidence Type | Source | Collection Method | Preservation |
|---------------|--------|-------------------|--------------|
| Audit logs | MongoDB `audit_logs` | `mongoexport` with timeframe filter | Hash-chain verification before export |
| Application logs | stdout / log aggregator | Export with correlation ID filter | Timestamped archive |
| Prometheus metrics | `/metrics` scrape data | Query Prometheus for timeframe | Snapshot export |
| Request traces | OpenTelemetry (if enabled) | Trace ID lookup | Export trace spans |
| MongoDB query logs | MongoDB profiler | Enable profiler; export slow query log | Timestamped archive |
| Network logs | Docker / host | Container network logs | Timestamped archive |

> **Important:** Audit logs use hash-chain integrity. Always verify the chain is intact
> before relying on log data for forensic analysis. A broken chain indicates possible
> tampering.

#### 6.2.3 Correlation Analysis

Use correlation IDs from `RequestLoggingMiddleware` to trace request flows:

1. Identify the suspicious request's correlation ID from audit or application logs
2. Search all log sources for the same correlation ID
3. Reconstruct the full request lifecycle (auth, processing, response)
4. Identify any lateral movement or privilege escalation attempts

---

## 7. Phase 3 — Containment

### 7.1 Immediate Containment (Short-term)

| Incident Type | Containment Action | Command / Procedure |
|---------------|-------------------|---------------------|
| Compromised user account | Disable account, revoke all tokens | Admin API: disable user; clear user sessions in DB |
| Compromised JWT secret | Rotate JWT_SECRET_KEY | Update environment variable; restart backend (all existing tokens invalidated) |
| Compromised S1 API token | Rotate token in SentinelOne console | Update `S1_API_TOKEN` environment variable; restart backend |
| Brute force attack | Verify rate limiting active; block IP at network level | Check rate limit logs; update network firewall rules |
| SQL/NoSQL injection attempt | Verify Pydantic validation blocking; review affected endpoints | Check audit logs for 422 responses; review DTO validation |
| Dependency vulnerability | Assess exploitability; pin safe version if available | Run `pip-audit` / `npm audit`; update `requirements.txt` / `package.json` |
| DDoS | Verify rate limiting; enable upstream protection | Monitor Prometheus metrics; engage CDN/WAF if available |

### 7.2 Extended Containment

If immediate containment is insufficient:

1. **Isolate affected components:** Stop the affected container(s) while keeping others running
2. **Enable enhanced monitoring:** Increase log verbosity; enable OpenTelemetry if not active
3. **Restrict access:** Temporarily require 2FA for all roles; reduce session timeouts
4. **Preserve evidence:** Take MongoDB snapshots before any recovery actions
5. **Notify stakeholders:** Communicate containment status per severity escalation matrix

---

## 8. Phase 4 — Eradication

### 8.1 Root Cause Elimination

| Root Cause Category | Eradication Steps |
|--------------------|-------------------|
| Application vulnerability | Patch code; add test coverage; update ADR documentation |
| Dependency vulnerability | Update to patched version; add to CI vulnerability checks |
| Misconfiguration | Correct configuration; add validation; document in troubleshooting guide |
| Credential compromise | Rotate all potentially affected credentials; review access logs for unauthorized actions |
| Insider threat | Revoke access; review all actions by the account; assess data exposure |

### 8.2 Verification

After eradication:

1. Run the full test suite (`cd backend && pytest` + `cd frontend && npm run test`)
2. Verify security controls are functioning:
   - Authentication working correctly
   - Rate limiting active
   - Audit logging capturing events
   - Health probes returning expected status
3. Run `pip-audit` and `npm audit` to confirm no known vulnerabilities remain
4. Review Prometheus metrics for return to normal patterns

---

## 9. Phase 5 — Recovery

### 9.1 Service Restoration

| Step | Action | Verification |
|------|--------|-------------|
| 1 | Deploy patched/corrected code | CI pipeline passes; Docker build successful |
| 2 | Restore data if needed | Restore from backup; verify data integrity via audit log hash chain |
| 3 | Re-enable services | Start containers; verify health probes pass |
| 4 | Gradual traffic restoration | Monitor Prometheus metrics for error rates |
| 5 | Re-enable user access | Communicate to users; monitor for recurrence |

### 9.2 Data Recovery

If data restoration is required:

1. Identify the most recent clean backup prior to the incident
2. Verify backup integrity (checksums, encryption)
3. Restore to the test database (`sentora_test`) first for validation
4. Verify restored data completeness and integrity
5. Restore to production database with the application offline
6. Re-run sync from SentinelOne to capture any changes since backup
7. Verify fingerprint and classification state consistency

**Reference:** `docs/compliance/business-continuity.md` for detailed backup/restore procedures.

### 9.3 Post-Recovery Monitoring

Enhanced monitoring period of 72 hours after recovery:

| Metric | Threshold | Action if Exceeded |
|--------|-----------|-------------------|
| Error rate | > 5% of requests | Investigate; prepare for re-containment |
| Auth failure rate | > 10% above baseline | Check for continued attack; review lockout logs |
| Response latency P99 | > 2x baseline | Investigate resource contention or data corruption |
| Rate limit triggers | > 5x baseline | Check for continued abuse |

---

## 10. Phase 6 — Lessons Learned

### 10.1 Post-Incident Review

A post-incident review must be conducted within 5 business days of incident closure.

**Attendees:** All IR team members involved in the incident, plus relevant stakeholders.

**Agenda:**

1. Timeline reconstruction (using Scribe notes)
2. What was the root cause?
3. How was the incident detected? Could detection have been faster?
4. Were containment procedures effective? What could be improved?
5. Was the IR plan followed? Where did it fall short?
6. What preventive measures should be implemented?
7. Does any documentation need updating?

### 10.2 Deliverables

| Deliverable | Timeline | Owner |
|-------------|----------|-------|
| Post-incident report | Within 5 business days | IC |
| Updated IR plan (if gaps found) | Within 10 business days | Security team |
| ADR for systemic improvements | Within 10 business days | Technical Lead |
| Updated runbooks | Within 10 business days | Technical Lead |
| Follow-up action items tracked | Ongoing | IC |

### 10.3 Metrics Tracked

| Metric | Purpose |
|--------|---------|
| Mean Time to Detect (MTTD) | How quickly was the incident identified? |
| Mean Time to Contain (MTTC) | How quickly was the threat contained? |
| Mean Time to Recover (MTTR) | How quickly was service restored? |
| Total incident duration | End-to-end from detection to closure |
| Data records affected | Scope of impact |
| Root cause category | Trend analysis for preventive investment |

---

## 11. Incident Response Runbooks

### 11.1 Runbook: Compromised User Account

1. Disable the account via admin API
2. Revoke all active sessions and tokens for the user
3. Review audit log for all actions by the compromised account
4. Determine scope: what data was accessed or modified?
5. If Restricted data accessed: escalate to P1
6. Reset password; require 2FA re-enrollment
7. Notify the user via out-of-band communication
8. Document in incident record

### 11.2 Runbook: JWT Secret Compromise

1. Generate new `JWT_SECRET_KEY`
2. Update environment variable on all instances
3. Restart all backend instances (invalidates ALL existing tokens)
4. All users will need to re-authenticate
5. Review audit logs for suspicious token usage before rotation
6. If tokens were forged: treat as P1 data breach
7. Document rotation in configuration change log

### 11.3 Runbook: S1 API Token Compromise

1. Immediately rotate the token in SentinelOne Management Console
2. Update `S1_API_TOKEN` environment variable
3. Restart backend to load new token
4. Review S1 audit logs for unauthorized API usage
5. Verify sync resumes normally with new token
6. Document in incident record

### 11.4 Runbook: Dependency Vulnerability (CVE)

1. Assess CVSS score and exploitability in Sentora context
2. If CVSS >= 9.0 or actively exploited: treat as P2
3. If CVSS >= 7.0: treat as P3
4. Check if `pip-audit` or `npm audit` flagged it in CI
5. Update to patched version if available
6. If no patch: assess mitigating controls; add to risk register
7. Run full test suite after update
8. Deploy updated containers
9. Document in incident record and update vendor management policy

### 11.5 Runbook: Database Compromise

1. Immediately isolate MongoDB (stop network access)
2. Assess scope: which collections were accessed?
3. Check audit log hash-chain integrity
4. If chain broken: assume logs tampered; rely on external log copies
5. Classify incident based on highest data classification accessed
6. Rotate all database credentials
7. Restore from last known-good backup
8. Re-sync from SentinelOne
9. Rotate JWT_SECRET_KEY (tokens may reference compromised user data)
10. Notify affected users if PII was accessed

---

## 12. External Communication Templates

### 12.1 Initial Notification (P1/P2)

```
Subject: [Sentora Security Incident] Initial Notification

We have identified a security incident affecting the Sentora platform.

Severity: [P1/P2]
Detected: [timestamp]
Current Status: [Investigating/Contained]

Impact: [Brief description of what is affected]

We are actively investigating and will provide updates every [1 hour / 4 hours].

Actions taken so far:
- [List containment actions]

Recommended user actions:
- [e.g., Change passwords, re-authenticate]

Next update: [timestamp]
```

### 12.2 Resolution Notification

```
Subject: [Sentora Security Incident] Resolved

The security incident reported on [date] has been resolved.

Root Cause: [Brief description]
Duration: [start] to [end]
Data Impact: [Description of any data affected]

Remediation actions completed:
- [List actions taken]

Preventive measures implemented:
- [List improvements]

If you have questions or concerns, please contact [security contact].
```

---

## 13. Compliance Mapping

| Requirement | Framework | Control Reference |
|-------------|-----------|-------------------|
| Incident management planning | SOC 2 CC7.3-CC7.4 | This document, Phases 1-6 |
| Incident response procedures | ISO 27001 A.5.24-A.5.27 | This document, Phases 3-6 |
| Evidence collection | ISO 27001 A.5.28 | Phase 2, Section 6.2.2 |
| Security event monitoring | SOC 2 CC4.1 | Phase 2, detection sources |
| Communication procedures | SOC 2 CC2.3 | Section 12, templates |
| Recovery mechanisms | SOC 2 CC7.4 | Phase 5 |

---

## 14. Plan Maintenance

| Activity | Frequency | Responsible |
|----------|-----------|-------------|
| Full plan review | Semi-annually | Security team |
| Contact list update | Quarterly | IC |
| Tabletop exercise | Semi-annually | Security team |
| Runbook review | Quarterly | Technical Lead |
| Detection infrastructure test | Monthly | Operations team |

---

*This plan is reviewed semi-annually and after every P1 or P2 incident. All IR team
members must acknowledge receipt of the current version.*
