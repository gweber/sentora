# ADR-0012: Weight-Based Marker Scoring

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

A fingerprint consists of a set of markers, each of which is a glob pattern that either matches or does not match a given agent's installed application list. Not all markers are equally indicative of the target software profile. The presence of "WinCC" is a strong signal that an agent hosts an OT workstation; the presence of "7-Zip" or "Microsoft Visual C++ Redistributable" is near-ubiquitous across all Windows endpoints and provides almost no discriminating signal. A binary scoring model — where every matched marker contributes equally — would dilute strong signals with noise markers and produce inaccurate verdicts. Users accumulate domain knowledge about which markers are reliable in their specific environment and need a mechanism to encode that knowledge.

## Decision

Every marker in a fingerprint carries a `weight` field in the range 0.0 to 1.0 (default 1.0). The classification score for an agent against a fingerprint is computed as `Σ(weight of matched markers) / Σ(weight of all markers in the fingerprint)`. A score of 1.0 means all markers matched with full weight; a score of 0.0 means no markers matched. The classification verdict is determined by comparing this score against a configurable threshold per fingerprint. Users adjust marker weights via a slider in the Vue 3 fingerprint editor; a live score preview recalculates as weights are adjusted.

## Consequences

### Positive
- Domain experts can encode their knowledge: a SCADA integrator who knows WinCC is definitive can weight it at 1.0 and weight runtime dependencies at 0.2.
- Score is normalized to [0.0, 1.0] regardless of how many markers a fingerprint contains, making thresholds comparable across fingerprints of different sizes.
- Default weight of 1.0 means fingerprints work correctly without any weight configuration — zero barrier to basic use.
- Weight adjustments are immediately reflected in the live preview without requiring a full reclassification run.
- The scoring formula is trivial to audit and explain to non-technical stakeholders.

### Negative
- Users must understand the weight concept to use it correctly; a poorly weighted fingerprint (e.g., all noise markers at 1.0) produces worse results than binary scoring.
- Weight tuning is empirical; there is no automated guidance on optimal weights for a given environment.
- Score normalization means adding more low-weight markers can slightly increase the score for agents that match them, even if those markers are not meaningful.

### Risks
- A fingerprint with all markers at weight 0.0 would produce a division-by-zero in the scoring formula. The engine must guard against this with a validation rule and a runtime check.
- Users may interpret a score of 0.85 as "85% confident" (a probabilistic reading) rather than as a weighted coverage ratio (the correct reading). UI copy must clarify the formula.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Binary scoring (each matched marker = 1, unmatched = 0, score = matched / total) | Treats all markers equally; noise markers (7-Zip, C++ redistributable) dilute strong signals; known to produce inaccurate verdicts in heterogeneous Windows environments |
| Per-marker threshold (each marker independently decides pass/fail) | Requires configuring two parameters per marker (weight and threshold); cognitive load is too high for non-developer users managing 10+ markers per fingerprint |
| ML-based confidence scoring | No training data at deployment time; requires labelled verdicts to learn from; operationally complex and opaque |
| Ordinal marker tiers (critical / normal / informational) | Simpler UX than a continuous slider but loses precision; "critical" could mean weight 1.0, 0.8, or 0.5 depending on convention — ambiguous for cross-team fingerprint sharing |
