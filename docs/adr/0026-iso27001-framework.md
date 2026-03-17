# ADR-0026: ISO/IEC 27001:2022 Compliance Framework

**Status:** Accepted
**Date:** 2026-03-17

## Context

ISO/IEC 27001 is the most widely adopted international standard for
information security management systems (ISMS).  It is the de-facto
requirement for organizations seeking certification in Europe, Asia,
and increasingly globally.  While Sentora already supports SOC 2
(US-centric), PCI DSS (payment industry), HIPAA (US healthcare), BSI
IT-Grundschutz (DACH), and DORA (EU financial), the absence of ISO 27001
limits Sentora's appeal to organizations whose primary compliance driver
is ISO certification.

### Key differences from existing frameworks

1. **Statement of Applicability (SoA)**: ISO 27001 requires organizations
   to define which controls are applicable and justify any exclusions.
   This is unique among the five existing frameworks — none required a
   justification when disabling a control.

2. **Annex A scope**: ISO 27001:2022 Annex A contains 93 controls across
   four themes (Organizational A.5, People A.6, Physical A.7,
   Technological A.8).  Most are procedural or physical and cannot be
   validated through endpoint software data.

3. **Certification sensitivity**: ISO 27001 carries certification weight.
   Users could misinterpret a dashboard score as certification-readiness.
   Disclaimers must be prominent.

## Decision

### Add ISO 27001 as the 6th compliance framework

- **16 controls** mapped to Annex A sections A.5 and A.8
- **Reuse all existing check types** — no new engine logic required
- **No new check types or engine changes**

### Control selection criteria

Only controls where endpoint software inventory data provides
**defensible evidence** are included:

| Annex A | Controls included | Rationale |
|---------|------------------|-----------|
| A.5 Organizational | 4 | Asset inventory (A.5.9), acceptable use (A.5.10), information transfer (A.5.14) |
| A.6 People | 0 | HR/training controls — no endpoint data |
| A.7 Physical | 0 | Physical security — no endpoint data |
| A.8 Technological | 12 | Endpoint devices, malware, vulnerabilities, config, software installation, monitoring, change management |

Controls explicitly excluded:
- **A.5.37** (Documented Operating Procedures): Sync freshness cannot
  validate that SOPs exist
- **A.8.28** (Secure Coding): Tool presence cannot validate coding practices

### Add `disable_reason` field to ControlConfiguration

A new optional `disable_reason: str | None` field on
`ControlConfiguration` allows tenants to document why a control is
excluded.  This supports ISO 27001 SoA requirements but benefits all
frameworks (e.g., PCI controls excluded for non-CDE endpoints).

Changes:
- `entities.py`: New field on `ControlConfiguration`
- `dto.py`: Added to `ConfigureControlRequest` and `ControlResponse`
- `commands.py`: Accepted and passed through
- `repository.py`: Persisted/read from MongoDB
- `queries.py`: Included in framework detail response
- Frontend: Disable prompt shows text input; saved reason displayed on
  disabled controls

### Dashboard disclaimer rendering

Per-framework disclaimer text (already in `ComplianceFramework.disclaimer`)
is now rendered on framework score cards in the dashboard view, not only
in the settings view.  This prevents misinterpretation of dashboard scores
as certification status.

## Consequences

### Positive

- Sentora now covers the globally most recognized ISMS standard
- `disable_reason` provides audit-ready SoA justification for all frameworks
- No engine changes — zero risk to existing framework evaluations
- 16 controls bring the total to 100 across 6 frameworks

### Negative

- 16 additional controls increase maintenance surface
- ISO 27001 controls overlap with existing frameworks (prohibited_app,
  agent_online, etc.) — deduplication via check-result caching mitigates
  performance impact
- Disclaimer must be carefully worded to prevent certification confusion

### Risks

- Users may request A.6/A.7 controls that cannot be meaningfully
  automated — these should remain out of scope
- The `disable_reason` field adds one optional column to the control
  configuration collection — minimal storage impact

## Alternatives Considered

1. **Map all 93 Annex A controls**: Rejected — most A.5/A.6/A.7 controls
   cannot be validated through endpoint data.  Including them as permanent
   `not_applicable` would inflate the framework without providing value.

2. **Separate SoA entity**: Rejected — a `disable_reason` field on the
   existing `ControlConfiguration` is simpler, uses the same CRUD
   endpoints, and avoids a new collection.

3. **ISO 27001 as premium/paid tier**: Out of scope for this decision —
   pricing is not an architectural concern.
