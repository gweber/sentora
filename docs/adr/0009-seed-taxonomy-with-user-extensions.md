# ADR-0009: Seed Taxonomy with User Extensions

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

Sentora's taxonomy bounded context stores known software categories (e.g., SCADA, MES, HMI, historian, labeling, industrial networking) used to classify and label fingerprint verdicts. Without a pre-populated taxonomy, the tool has no classification vocabulary on first launch — users would need to manually enter every category and associated app before running their first sync, which is a significant barrier to adoption. Industrial automation environments share a well-known set of software titles (Siemens WinCC, Ignition, FactoryTalk, OSIsoft PI, Zebra ZDesigner, etc.) that can be curated in advance. At the same time, users operate in heterogeneous environments with proprietary or niche software not covered by any seed list.

## Decision

Sentora ships a curated YAML seed file containing 100+ industrial software taxonomy entries covering SCADA, MES, HMI, historian, labeling, networking, and safety system categories. Seed entries are loaded at application startup if the `taxonomy` collection is empty and are marked `user_added: false`. Users can add, edit, and delete entries at runtime via the UI; user-added entries are marked `user_added: true`. Seed entries can be edited or deleted by users; re-seeding only occurs on first run and never overwrites user modifications.

## Consequences

### Positive
- The tool is immediately useful on first launch without any manual configuration.
- Industrial professionals get a familiar vocabulary (SCADA, MES, historian) out of the box.
- Seed entries use glob patterns (ADR-0004), making them tolerant of version changes without requiring seed file updates.
- The `user_added` flag allows the UI to distinguish curated from custom entries and supports future features (reset to defaults, seed update diffs).
- YAML format is human-readable and diff-friendly — seed updates are reviewable in pull requests.

### Negative
- Seed data can become outdated as industrial software vendors rename or discontinue products.
- A seed entry with an overly broad glob pattern could produce false-positive taxonomy matches for a specific customer's environment.
- Customers who delete seed entries and then upgrade Sentora will not receive updated seed entries automatically (by design — to avoid overwriting their modifications).

### Risks
- A seed entry that collides with a customer's proprietary app name (via a broad glob) could produce misleading classification results. Mitigated by keeping seed patterns publisher-anchored where possible (e.g., `siemens*wincc*` rather than `*wincc*`).
- The seed file growing beyond 500+ entries could slow startup if the taxonomy collection is re-initialized frequently in development environments.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| No seed data (blank taxonomy) | Requires users to manually configure the full taxonomy before the tool provides any value; unacceptable onboarding friction |
| Seed via SQL migration / Alembic | Project uses MongoDB, not a relational database; a migration framework adds tooling for a one-time initialization problem |
| Remote taxonomy service (pull from update server) | Requires internet access and a hosted service; incompatible with air-gapped industrial deployments |
| Hard-coded taxonomy (not user-extensible) | Customers cannot add proprietary or regional software; limits the tool's applicability beyond the seed list |
