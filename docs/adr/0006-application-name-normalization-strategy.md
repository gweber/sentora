# ADR-0006: Application Name Normalization Strategy

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

SentinelOne reports application names as raw strings extracted from OS installer metadata. These strings contain version numbers ("V7.5 SP2", "8.0.1.2345"), architecture tags ("(x64)", "32-bit", "ARM64"), locale codes ("en-US"), noise tokens ("Update 1", "Hotfix KB123456"), and inconsistent publisher prefixes ("Siemens" vs "SIEMENS AG" vs empty). Using raw names for glob pattern matching would require patterns to account for all of this variation, making markers fragile and verbose. Using raw names for TF-IDF scoring (ADR-0003) would treat "WinCC V7.5" and "WinCC V8.0" as distinct apps, diluting the signal.

## Decision

Sentora stores two name fields on every installed application record: `name` contains the original string from S1 exactly as received (used for display and audit); `normalized_name` contains the output of a pure normalization function that lowercases the string, strips version numbers, removes architecture and locale tags, and collapses noise tokens. Glob pattern matching (ADR-0004) and TF-IDF scoring (ADR-0003) operate exclusively on `normalized_name`. The normalization function has exhaustive unit test coverage and is version-controlled as a standalone module.

## Consequences

### Positive
- Patterns stay concise: `*wincc*` matches all WinCC versions without embedding version predicates.
- TF-IDF scores aggregate all versions of an app into a single term, producing cleaner suggestions.
- Original names are preserved for display, ensuring no information is lost from the S1 payload.
- Normalization is a pure function (string in, string out) — trivially testable and debuggable.
- Separating the display field from the match field allows the normalization rules to evolve without changing stored display data.

### Negative
- Two fields per app record increase document size slightly.
- Normalization rules must be maintained as S1 changes its naming conventions or new noise token patterns are discovered.
- A bug in the normalization function affects matching across all agents simultaneously; rollback requires a re-sync.

### Risks
- Over-aggressive normalization could collapse two genuinely distinct products into the same `normalized_name` (e.g., "WinCC" and "WinCC Runtime Professional" if the normalization is too broad). Mitigated by retaining publisher token and core product name after stripping.
- Normalization is applied at sync time; changing the normalization algorithm requires a full re-sync to update stored `normalized_name` values.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Normalize at query time (store raw only) | Recomputes normalization on every match operation; cannot be indexed; normalization errors are only visible during queries |
| Store only normalized name | Loses original S1 data; makes the UI display less useful and prevents audit of normalization correctness |
| Per-publisher normalization rules | Too complex to maintain; requires identifying publisher strings reliably, which is itself a normalization problem |
| No normalization (use raw names) | Patterns must encode every version variant; TF-IDF treats version increments as distinct apps; marker maintenance becomes unmanageable |
