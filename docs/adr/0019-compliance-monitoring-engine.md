# ADR-0019: Compliance Monitoring Engine

**Status**: Accepted
**Date**: 2026-03-15

## Context

Enterprise customers deploying Sentora in regulated environments need to demonstrate
continuous compliance with frameworks like SOC 2 Type II, PCI DSS 4.0.1, HIPAA Security
Rule, and BSI IT-Grundschutz. Rather than building one-off audit exports, Sentora needed
a reusable compliance engine that could evaluate controls programmatically and produce
evidence snapshots.

The existing classification, sync, and auth infrastructure already implements many of the
technical controls these frameworks require. What was missing was a way to evaluate and
report on them continuously -- giving operators real-time visibility into their compliance
posture without waiting for periodic manual audits.

## Decision

Build a compliance monitoring engine into Sentora with the following design:

1. **Pre-built controls.** 61 controls across 4 frameworks (SOC 2, PCI DSS 4.0.1, HIPAA
   Security Rule, BSI IT-Grundschutz). Each control maps to one of 10 automated check
   types:

   - `sync_freshness` -- verifies sync has completed within a configured window
   - `classification_coverage` -- checks that endpoints have classified software inventories
   - `fingerprint_coverage` -- checks that known software has fingerprint matches
   - `rbac_enabled` -- verifies RBAC is active and roles are assigned
   - `tls_configured` -- confirms TLS is enabled on API and database connections
   - `audit_log_active` -- verifies audit logging is operational with hash-chain integrity
   - `password_policy` -- checks password complexity and rotation requirements
   - `mfa_adoption` -- measures MFA enrollment rate against a configurable threshold
   - `backup_freshness` -- verifies backup recency within RPO targets
   - `endpoint_compliance` -- evaluates agent-level policy compliance

2. **MongoDB storage model.** Three collections hold the configuration:
   - `compliance_framework_config` -- framework definitions and metadata
   - `compliance_control_config` -- per-control definitions with check type, severity, and scope
   - `compliance_custom_controls` -- operator-defined controls with custom parameters

   Check results are stored as snapshots in the `compliance_results` collection with a
   90-day TTL index for automatic cleanup.

3. **Scheduling.** Controls can be evaluated on three triggers:
   - After sync completion (event-driven)
   - On a cron expression (e.g., `0 6 * * *` for daily at 06:00)
   - Manual trigger via API

4. **Custom controls.** Operators can define additional controls with custom parameters
   and scoping, allowing tenants to extend the engine with organization-specific
   requirements without code changes.

5. **Scope filtering.** Controls can be scoped to specific S1 groups or agent tags,
   preventing false positives on out-of-scope endpoints.

6. **Severity levels.** Each control has a configurable severity: `critical`, `high`,
   `medium`, or `low`.

7. **Framework disclaimers.** Each framework result includes a disclaimer that automated
   checks are supplementary to formal audits and do not constitute certification.

8. **Evidence trail.** Results include an `evidence_summary` field and a `violations`
   array, providing the audit trail external auditors need to evaluate control effectiveness.

## Consequences

### Positive

- Continuous compliance posture visibility without manual audits
- Reusable engine -- adding new frameworks requires only control definitions, not code
  changes
- Evidence snapshots provide an audit trail for external auditors
- Custom controls allow tenants to extend with organization-specific requirements
- Scope filtering prevents false positives on out-of-scope endpoints

### Negative

- 61 controls across 4 frameworks increase the maintenance surface for control definitions
  and check logic
- Automated checks cannot replace human judgement for procedural controls (e.g., employee
  training, vendor reviews)
- 90-day TTL means historical compliance data is not preserved long-term; operators
  needing longer retention must export results
- Check execution adds MongoDB load proportional to fleet size

## Alternatives Considered

1. **External compliance platform integration (ServiceNow, Drata).** Rejected -- adds
   vendor dependency, requires per-platform API integration, and does not work in
   air-gapped on-premises deployments.

2. **Static compliance reports (PDF export).** Rejected -- provides no continuous
   monitoring; reports are stale by the time they are reviewed.

3. **Compliance as classification labels.** Rejected -- conflates software classification
   with compliance status. Compliance posture is a cross-cutting concern, not a property
   of individual software entries.
