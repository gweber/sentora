# ADR-0016: SOC 2 / ISO 27001 Compliance

## Status

Accepted

## Date

2026-03-15

## Context

Sentora processes sensitive organizational data from SentinelOne EDR environments,
including agent inventories (hostnames, IP addresses, OS details), installed application
catalogs, and software classification results. Enterprise customers deploying
Sentora require assurance that the platform meets recognized security and compliance
standards.

Two frameworks are particularly relevant:

1. **SOC 2 Type II** — the AICPA Trust Service Criteria framework, widely expected
   by US-based enterprise customers for SaaS and data processing applications. SOC 2
   evaluates the operating effectiveness of controls over a defined audit period.

2. **ISO 27001:2022** — the international standard for information security management
   systems (ISMS), expected by global enterprise customers and often a procurement
   requirement.

Both frameworks overlap significantly in their control requirements. Mapping Sentora's
existing security controls to both frameworks simultaneously reduces duplication and
identifies gaps more efficiently than addressing each framework independently.

### Existing Controls

Sentora already implements many controls that align with these frameworks:

- JWT authentication with RBAC (admin, analyst, viewer, super_admin)
- TOTP 2FA and OIDC/SAML SSO
- Audit logging with hash-chain integrity and 90-day TTL
- Prometheus metrics, health probes, structured logging
- Security headers (CSP, HSTS, X-Frame-Options)
- Rate limiting and account lockout
- Pydantic input validation on all API boundaries
- CI/CD pipeline with linting, type checking, tests, and vulnerability scanning
- Docker deployment with non-root user and resource limits
- MongoDB replica set support for HA
- Checkpoint-based sync resume for resilience

### Gaps Identified

A preliminary assessment identified the following gaps requiring documentation or
implementation:

- No formal data classification policy
- No documented incident response plan
- No business continuity / disaster recovery plan
- No vendor management policy for third-party dependencies
- No formal change management documentation
- No access control policy document (controls exist but are not formally documented)
- Control mappings to SOC 2 and ISO 27001 not established

## Decision

We will create a comprehensive compliance documentation suite mapping Sentora's
existing controls to SOC 2 Type II Trust Service Criteria and ISO 27001:2022 Annex A
controls. The documentation will be maintained in `docs/compliance/` and consists of:

1. **SOC 2 Type II Control Mapping** (`soc2-type2-controls.md`) — Maps controls to
   CC1-CC9, A1, PI1, C1 criteria with implementation evidence and gap analysis.

2. **ISO 27001:2022 Annex A Control Mapping** (`iso27001-controls.md`) — Maps controls
   to A.5 through A.8 themes with Statement of Applicability.

3. **Data Classification Policy** (`data-classification.md`) — Four-tier classification
   (Public, Internal, Confidential, Restricted) applied to all Sentora data types.

4. **Access Control Policy** (`access-control-policy.md`) — Formal documentation of
   RBAC model, authentication mechanisms, session management, and access review process.

5. **Incident Response Plan** (`incident-response.md`) — Six-phase IR plan with
   severity classification, runbooks, and communication templates.

6. **Change Management Policy** (`change-management.md`) — Development lifecycle,
   CI/CD pipeline, deployment process, and ADR documentation requirements.

7. **Business Continuity Plan** (`business-continuity.md`) — HA architecture, backup
   strategy, disaster recovery procedures, and RPO/RTO targets.

8. **Vendor Management Policy** (`vendor-management.md`) — Dependency inventory,
   risk assessment framework, vulnerability management, and update strategy.

All documents include:
- Document ID and version tracking
- Last review date and next review date
- Classification label
- Compliance cross-references to both SOC 2 and ISO 27001

### Approach: Documentation-First

Rather than implementing new technical controls, this decision focuses on formally
documenting the controls that already exist. The gap analyses in the SOC 2 and ISO
27001 mappings identify where additional technical controls may be needed, tracked as
remediation items with priority and target dates.

## Consequences

### Positive

- Enterprise customers can evaluate Sentora's security posture against recognized
  frameworks
- Gap analysis provides a prioritized roadmap for security improvements
- Semi-annual review cycle ensures documentation stays current
- Cross-referencing between documents reduces duplication and inconsistency
- Compliance documentation serves as onboarding material for new team members
- Prepares the project for a formal SOC 2 Type II audit if needed

### Negative

- Eight compliance documents require ongoing maintenance (semi-annual reviews)
- Documentation may drift from implementation if review schedule is not followed
- Compliance documentation may create a false sense of security if not validated
  against actual system behavior
- Additional process overhead for change management and access reviews

### Mitigations

- Review dates embedded in each document with clear ownership
- CI/CD pipeline enforces technical controls regardless of documentation state
- Gap analysis items tracked with target dates and priorities
- Automated controls (rate limiting, RBAC, audit logging) operate independently
  of documentation
