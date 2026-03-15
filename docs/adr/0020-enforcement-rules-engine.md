# ADR-0020: Enforcement Rules Engine

## Status

Accepted

## Date

2026-03-15

## Context

Sentora's classification engine identifies what software is installed where, but
enterprise security teams also need to define and enforce software policies: which
software is required, which is forbidden, and which is in an approved allowlist.

Without enforcement, classification results are informational only — operators must
manually compare results against policy.

Enforcement needs to integrate with the existing taxonomy system (software categories)
and support scoping to specific S1 groups or agent tags. Violations must be actionable:
webhook notifications for PSA/ITSM integration, exportable for auditor delivery.

## Decision

Introduce three rule types anchored to taxonomy categories:

- **Required** — software in this category MUST be present on scoped agents (e.g.,
  "Endpoint Protection" required on all production servers).
- **Forbidden** — software in this category MUST NOT be present (e.g., "Remote Access
  Tools" forbidden on SCADA endpoints).
- **Allowlist** — ONLY software in approved categories may be present; anything else
  is a violation.

### Data Model

Rules are stored in the `enforcement_rules` collection with the following fields:

- `name` — human-readable rule name
- `taxonomy_category_id` — reference to the taxonomy category this rule targets
- `type` — one of `required`, `forbidden`, `allowlist`
- `severity` — one of `critical`, `high`, `medium`, `low`
- `scope_groups` — optional list of S1 group IDs the rule applies to
- `scope_tags` — optional list of agent tags the rule applies to
- `labels` — freeform key-value pairs for organizational grouping
- `enabled` — boolean toggle

Enforcement results are stored as snapshots in the `enforcement_results` collection
with a 90-day TTL. Each result contains:

- `rule_id` — reference to the evaluated rule
- `status` — one of `pass`, `fail`, `error`
- `total_agents` — number of agents in scope
- `compliant_agents` — number of agents passing the rule
- `non_compliant_agents` — number of agents failing the rule
- `violations` — array with per-agent detail (agent ID, hostname, matched/missing
  applications)

### Webhook Integration

Violations trigger webhook events:

- `enforcement.violation_detected` — fired when a new violation is identified
- `enforcement.violation_resolved` — fired when a previously failing agent becomes
  compliant

### Unified Violations Feed

A unified violations view combines enforcement and compliance violations in a single
filterable feed with CSV export, giving operators and auditors a single pane of glass.

### Scheduling

Enforcement checks run alongside compliance checks on a configurable schedule.

## Consequences

### Positive

- Declarative policy definitions — no code changes needed to add new policies
- Taxonomy-anchored rules leverage existing software categorization
- Scoping prevents over-broad rules from generating noise
- Webhook integration enables automated ITSM ticket creation
- Unified violations view gives operators a single pane of glass

### Negative

- Rule evaluation scales with (rules x agents x applications) — large fleets with
  many rules may see slower checks
- Allowlist rules can be noisy if taxonomy coverage is incomplete
- 90-day TTL means violation history is not preserved indefinitely

## Alternatives Considered

1. **Tag-based enforcement only (S1 tags as policy).** Rejected — too coarse, no
   category semantics, no required/forbidden distinction.

2. **External policy engine (OPA/Rego).** Rejected — powerful but adds infrastructure
   dependency and learning curve.

3. **Classification verdict-based enforcement** (e.g., "all agents must be classified").
   Rejected — too blunt, doesn't capture category-level policy requirements.
