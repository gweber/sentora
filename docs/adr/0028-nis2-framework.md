# ADR-0028: NIS2 Compliance Framework

**Status:** Accepted
**Date:** 2026-03-17

## Context

NIS2 (EU Directive 2022/2555) establishes cybersecurity obligations for ~160,000 essential and important entities across the EU. National transposition was due by October 2024. CISOs explicitly search for "NIS2 compliance" — separate framework visibility is important despite overlap with ISO 27001 and DORA, because NIS2 is a distinct regulatory requirement with its own reporting obligations and penalties.

## Decision

Add NIS2 as the 8th compliance framework with 13 controls mapped to five of the ten measures in Article 21(2): risk analysis (a), supply chain security (d), acquisition/development/maintenance security (e), basic cyber hygiene (h), and cryptography/encryption (i). Measures covering incident handling (b), business continuity (c), effectiveness assessment (f), incident reporting (g), and MFA (j) are outside endpoint monitoring scope. All controls reuse existing check types.

## Consequences

### Positive
- Addresses the largest regulatory compliance demand in the EU (~160k entities)
- Separate NIS2 dashboard visibility satisfies CISO reporting requirements
- 13 controls bring the total to 128+ across 8 frameworks

### Negative
- Overlap with ISO 27001 and DORA is intentional but means some controls generate near-duplicate evaluations
- National NIS2 implementations may add requirements not covered by the EU directive text

## Alternatives Considered

Treating NIS2 as a tag on ISO 27001 controls: rejected — CISOs need separate NIS2 framework visibility for board reporting and regulator communication.
