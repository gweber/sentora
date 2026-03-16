# ADR-0021: Forensic Audit Hash-Chain

**Status:** Accepted
**Date:** 2026-03-15
**Decision Makers:** Platform Team

## Context

Sentora's audit log records all state mutations across 18+ event types. However, an administrator with direct database access can modify or delete entries without detection. Regulatory frameworks (SOC 2, ISO 27001, BSI C5) require tamper-evident logging with provable integrity guarantees.

## Decision

Implement a SHA-256 hash-chain with epoch-based segmentation over the existing audit log system. Each entry's hash includes the previous entry's hash, creating a cryptographic chain where any modification breaks all subsequent hashes.

### Key Design Choices

1. **Hash-chain, not blockchain** — No consensus, no distributed ledger. This is a local cryptographic chain providing tamper-evidence, not tamper-resistance.

2. **Epoch-based segmentation** — The chain is divided into configurable epochs (default 1,000 entries). Epochs enable independent verification, bounded memory usage during checks, and are the unit for cold-storage export.

3. **Clean-cut migration (Option A)** — Existing unchained entries remain as-is. The chain starts fresh with a genesis entry. No retroactive hashing (which would be dishonest about when integrity guarantees began).

4. **Air-gapped verification** — A standalone CLI tool (`tools/sentora_verify/`) with zero external dependencies (Python stdlib only) verifies exported epochs without network access. This allows auditors to verify chain integrity without trusting the Sentora server.

5. **Graceful degradation** — If chain operations fail, the audit writer falls back to plain (unchained) logging. Audit reliability is prioritised over chain completeness.

6. **CQRS separation** — Commands handle chain writes (sequence allocation, hash computation, epoch management). Queries handle verification, status, and export. Repository layer abstracts MongoDB access.

## Consequences

### Positive
- Tamper-evident audit trail satisfying SOC 2 CC7.2 and ISO 27001 A.12.4.3
- Deletion or modification of any entry is cryptographically detectable
- Epoch-based export enables offline archival and third-party verification
- Air-gapped verification tool removes trust dependency on the server
- Existing audit functionality is preserved — chain is additive

### Negative
- Sequence allocation adds a small write latency (~1 additional MongoDB roundtrip per audit event)
- Chain integrity depends on correct hash computation — the hasher module must remain identical between backend and CLI tool
- TTL-based auto-deletion conflicts with chain integrity (entries deleted by TTL break the chain). Resolution: chain verification reports the verifiable range, not the full 90-day TTL window.

## Technical Details

### Collections
- `audit_log` — Extended with `sequence`, `epoch`, `hash`, `previous_hash`, `is_epoch_start`, `is_epoch_end`, `previous_epoch_hash` fields
- `audit_chain_meta` — Stores sequence counter, epoch configuration, verification results, export records

### API Endpoints
- `POST /api/v1/audit/chain/verify` — Verify chain integrity (full or single epoch)
- `GET /api/v1/audit/chain/status` — Current chain statistics
- `GET /api/v1/audit/chain/epochs` — List completed epochs
- `POST /api/v1/audit/chain/export/{epoch}` — Download epoch as JSON archive
- `POST /api/v1/audit/chain/initialize` — Create genesis entry (idempotent)

### File Structure
```
backend/audit/chain/
├── __init__.py       # Package docstring
├── hasher.py         # SHA-256 hash computation (shared with CLI)
├── entities.py       # Domain entities (ChainedAuditEntry, VerificationResult, etc.)
├── dtos.py           # API request/response DTOs
├── repository.py     # MongoDB data access
├── commands.py       # Write operations (initialize, append)
├── queries.py        # Read operations (verify, status, export)
└── router.py         # FastAPI endpoints

tools/sentora_verify/
├── __init__.py       # Version
├── __main__.py       # CLI entry point
├── hasher.py         # Identical to backend/audit/chain/hasher.py
└── verifier.py       # Verification logic (stdlib only)
```
