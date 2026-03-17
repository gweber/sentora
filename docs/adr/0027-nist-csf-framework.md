# ADR-0027: NIST CSF 2.0 Compliance Framework

**Status:** Accepted
**Date:** 2026-03-17

## Context

NIST CSF 2.0 (published February 2024) is the de-facto cybersecurity standard in the United States, applicable to organizations of all sizes and sectors. Adding CSF 2.0 extends Sentora's addressable market beyond EU/DACH regulations into the US market where CSF is the primary compliance reference for organizations without specific industry regulation.

## Decision

Add NIST CSF 2.0 as the 7th compliance framework with 15 controls mapped to three of the six CSF Functions: Identify (ID.AM asset management), Protect (PR.DS data security, PR.IR infrastructure resilience, PR.PS platform security), and Detect (DE.CM continuous monitoring). Govern, Respond, and Recover require organizational processes outside endpoint monitoring scope. All controls reuse existing check types — no engine changes required.

## Consequences

### Positive
- Opens the US market — CSF is the most-requested framework by US-based CISOs
- 15 controls bring the total to 115+ across 7 frameworks
- Zero engine changes

### Negative
- Some CSF subcategories (PR.DS-01 for encryption) can only verify tool presence, not encryption state
- Overlap with ISO 27001 A.8 controls is intentional but increases total control count

## Alternatives Considered

Mapping all 106 CSF subcategories: rejected — most require governance, incident response, or recovery capabilities outside endpoint data scope.
