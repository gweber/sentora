# ADR-0004: Glob Patterns over Exact Match

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

SentinelOne reports application names as raw strings from the OS installer metadata, which routinely include version numbers, service pack suffixes, architecture tags, locale codes, and publisher prefixes. A single industrial application title can appear as "WinCC V7.5 SP2", "WinCC V8.0 Update 1", "Siemens WinCC Runtime Professional V8.0", and "SIEMENS WinCC V7.5 SP2 (x64)" across different agents in the same environment. Without pattern matching, a fingerprint marker for WinCC would need one exact string per observed variant, turning marker maintenance into a continuous manual task as customers upgrade software.

## Decision

Fingerprint markers use glob patterns (e.g., `siemens*wincc*`, `*wincc*runtime*`) matched against normalised application names. Matching is performed by Python's `fnmatch` module, which supports `*` (any sequence) and `?` (single character) wildcards. Patterns are always matched case-insensitively against the normalised name produced by the pipeline defined in ADR-0006.

## Consequences

### Positive
- A single pattern like `*wincc*` covers all observed WinCC variants past and future, eliminating per-version marker maintenance.
- Glob syntax is readable and writable by IT professionals without programming knowledge.
- Pattern authoring is supported by the Vue 3 UI with a live match-preview panel that shows which installed apps the pattern would currently match.
- `fnmatch` is in the Python standard library — no additional dependency.
- Normalisation (ADR-0006) reduces the surface area patterns must cover by stripping version tokens before matching.

### Negative
- Overly broad patterns (e.g., `*pro*`) can produce false positives across unrelated products.
- Glob patterns cannot express alternation or lookaheads, limiting expressiveness for complex naming schemes.
- Pattern debugging requires the live-preview UI; a bare pattern string gives no immediate feedback.

### Risks
- A publisher could release a product whose normalised name collides with an existing broad pattern, silently matching unintended software.
- If S1 changes its app name reporting format significantly, existing broad patterns may stop matching until updated.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| Exact string match | Requires one entry per observed name variant; maintenance burden grows with every software update in the environment |
| Regular expressions | More expressive but significantly harder to author and review for non-developer IT staff; increases misconfiguration risk |
| Version-stripping + exact match | Strips version tokens before exact comparison, but misses publisher prefix variations and locale-specific name changes |
| Fuzzy / Levenshtein matching | Matching score is opaque and unpredictable; a typo in a product name could match unrelated software with no clear threshold to set |
| Publisher-normalised canonical names | Would require a continuously maintained database of publisher-to-canonical mappings; S1 does not provide a stable software ID |
