# ADR-0029: CIS Controls v8 Compliance Framework

**Status:** Accepted
**Date:** 2026-03-17

## Context

CIS Critical Security Controls v8 define 18 prioritized security controls with 153 safeguards organized into three Implementation Groups (IG1 Basic, IG2 Foundational, IG3 Advanced). CIS Controls are the most popular baseline framework among MSSPs — Sentora's core target audience. Adding CIS Controls provides direct value to MSSPs managing SentinelOne deployments.

## Decision

Add CIS Controls v8 as the 9th compliance framework with 14 safeguards mapped to four CIS Controls: Control 1 (Enterprise Asset Inventory — 2 safeguards), Control 2 (Software Asset Inventory — 6 safeguards), Control 7 (Continuous Vulnerability Management — 3 safeguards), and Control 10 (Malware Defenses — 3 safeguards). Controls 3-6, 8-9, and 11-18 cover access management, data protection, email security, and other areas outside endpoint software inventory scope. Implementation Group assignments (IG1/IG2/IG3) are documented in each control description. All controls reuse existing check types.

## Consequences

### Positive
- Direct value for MSSP customers — CIS is their operational standard
- Control 2 (Software Asset Inventory) has the deepest mapping — 6 safeguards with genuine endpoint evidence
- Implementation Group metadata helps MSSPs prioritize by maturity level
- 14 safeguards bring the total to 142+ across 9 frameworks

### Negative
- CIS safeguard 7.3 (OS Patch Management) uses agent_version as a proxy — honest but imperfect
- Controls 3-18 cannot be evaluated through endpoint data — this limits CIS Controls coverage to ~8% of safeguards

## Alternatives Considered

Adding placeholder controls for CIS Controls 3-18 with permanent not_applicable status: rejected — inflates the framework without providing value.
