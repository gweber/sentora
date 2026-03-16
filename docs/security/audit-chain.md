# Forensic Audit Hash-Chain

## Overview

Sentora implements a SHA-256 hash-chain over the audit log to provide tamper-evident logging. Every audit entry is cryptographically linked to its predecessor, making any modification, deletion, or insertion detectable.

## Architecture

### Hash-Chain

Each audit entry includes:
- **`sequence`** — Monotonically increasing, gapless counter per tenant
- **`epoch`** — Segment number (configurable, default 1,000 entries per epoch)
- **`previous_hash`** — SHA-256 hash of the preceding entry (chain link)
- **`hash`** — SHA-256 hash of this entry (includes previous_hash)

```
Entry 0 (Genesis):  hash_0 = SHA-256(data + "GENESIS")
Entry 1:            hash_1 = SHA-256(data + hash_0)
Entry N:            hash_N = SHA-256(data + hash_{N-1})
```

### Epochs

The chain is segmented into epochs for practical verification:
- Each epoch contains a fixed number of entries (default 1,000)
- Epochs can be verified independently (internal chain)
- Cross-epoch links chain epochs together (epoch-to-epoch)
- Epochs are the unit for cold-storage export

### Genesis Entry

The first entry (sequence 0) anchors the entire chain:
- Created automatically on application startup
- Has `previous_hash = null` (uses `"GENESIS"` sentinel in hash computation)
- Contains chain configuration (algorithm, epoch size, version)
- One genesis per tenant (multi-tenant) or per instance (on-prem)

## Hash Computation

The hash covers these fields in canonical JSON form (`sort_keys=True, ensure_ascii=True`):

| Field | Source |
|-------|--------|
| `sequence` | Monotonic counter |
| `epoch` | Computed from sequence / epoch_size |
| `timestamp` | UTC datetime (isoformat) |
| `domain` | Functional area |
| `action` | Event identifier |
| `actor` | Who triggered the event |
| `status` | Outcome |
| `summary` | Description |
| `details` | Structured metadata |
| `tenant_id` | Tenant identifier |
| `previous_hash` | Previous entry hash or `"GENESIS"` |

Fields explicitly excluded: `_id` (MongoDB internal), `is_epoch_end` (set retroactively).

## Verification

### Online Verification

```
POST /api/v1/audit/chain/verify
Body: { "epoch": null }     # null = full chain, or specific epoch number
```

Verifies:
1. Sequence continuity (no gaps = no deletions)
2. Hash integrity (no modifications)
3. Epoch boundary links (no epoch-level tampering)

### Air-Gapped Verification

The CLI tool verifies exported epoch files without network access:

```bash
python -m sentora_verify audit_epoch_7.json [audit_epoch_6.json]
```

Zero external dependencies — uses only Python standard library.

## Epoch Export

```
POST /api/v1/audit/chain/export/{epoch_number}
```

Produces a self-contained JSON archive:
- All entries with full hash-chain data
- Export metadata (timestamps, entry count, algorithm)
- `export_hash` — SHA-256 integrity hash over the entries array

## Threat Model

| Threat | Detection |
|--------|-----------|
| Admin modifies an entry in MongoDB | Hash mismatch at modified entry |
| Admin deletes an entry | Sequence gap detected |
| Admin inserts a fake entry | Hash chain breaks at insertion point |
| Admin replaces entire chain | Genesis hash mismatch in exported epochs |
| Admin modifies exported file | export_hash mismatch in CLI verification |
| Admin modifies and re-hashes | Cannot reproduce without previous hash (chain link) |

### Limitations

- Does **not** prevent a sufficiently privileged attacker from rebuilding the entire chain from scratch (would require rewriting all entries and the genesis hash)
- TTL auto-deletion of entries older than 90 days will break the chain for deleted entries — verification reports the verifiable range
- No external trust anchor (timestamping service) — a future enhancement

## API Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/audit/chain/status` | GET | analyst+ | Current chain statistics |
| `/audit/chain/verify` | POST | admin | Run chain verification |
| `/audit/chain/epochs` | GET | analyst+ | List completed epochs |
| `/audit/chain/export/{epoch}` | POST | admin | Export epoch as JSON |
| `/audit/chain/initialize` | POST | admin | Create genesis (idempotent) |
