# ADR-0003: TF-IDF for Software Fingerprinting

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

Sentora must automatically surface the software that best characterises each SentinelOne agent group — the apps that are common within the group but rare across all other groups. This is structurally identical to the information retrieval problem of finding keywords that distinguish one document corpus from another. Asking users to manually curate marker suggestions for every group is not scalable: environments can have dozens of groups, hundreds of distinct app titles, and the installed base changes with every S1 sync. A data-driven scoring approach is required.

## Decision

Sentora implements a TF-IDF-inspired scoring function for fingerprint suggestion. For each app observed in a group, the score is computed as `group_frequency × inverse_group_frequency`, where `group_frequency` is the proportion of agents in the group that have the app installed, and `inverse_group_frequency` is the log-scaled inverse of the proportion of all groups in which the app appears. Apps with high scores appear frequently within the group and rarely across other groups, making them strong fingerprint candidates.

## Consequences

### Positive
- Automatically surfaces discriminating software without manual curation effort.
- Handles environments with arbitrary numbers of groups and apps — scales with data.
- Scores are interpretable: a high score means "common here, rare elsewhere."
- Reuses a well-understood algorithm with predictable behaviour; no ML model training or infrastructure required.
- Suggestions update automatically whenever a new sync refreshes the agent/app corpus.

### Negative
- Does not capture app combinations: a pair of apps that always co-occur but never appear individually is not detected.
- The inverse_group_frequency component requires a meaningful number of groups to produce useful signal; single-group environments get no discrimination benefit.
- Score thresholds for surfacing suggestions require manual tuning per environment; there is no universal cut-off.
- Ubiquitous apps (Windows Defender, 7-Zip) score near zero and are correctly suppressed, but borderline infrastructure tools may need manual review.

### Risks
- If group membership is highly uneven (one group with 10k agents, others with 5), raw frequency counts may bias scores; normalisation must account for group size.
- Algorithm change requests from users who expect ML-based clustering may require a migration path.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Manual marker curation only | Does not scale; requires per-group domain knowledge and constant maintenance as the installed base changes |
| Simple frequency ranking (within-group only) | Ranks ubiquitous apps (browsers, runtimes) first; no cross-group discrimination |
| Cosine similarity / clustering | Treats apps as vectors for agent similarity, not for group characterisation; harder to explain to non-technical users |
| ML classification (supervised) | Requires labelled training data that does not exist at deployment time; operationally complex |
| Jaccard index | Measures overlap between sets; does not express the "common here, rare elsewhere" property required for fingerprinting |
