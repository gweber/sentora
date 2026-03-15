# Audit Chain API

Endpoints for forensic hash-chain verification, status monitoring, epoch management, and cold-storage export.

## Endpoints

### GET /api/v1/audit/chain/status

Returns current chain statistics.

**Auth:** analyst, admin, super_admin

**Response:**
```json
{
  "total_entries": 12847,
  "current_epoch": 12,
  "current_sequence": 12846,
  "genesis_hash": "a3f8...",
  "latest_hash": "7b2c...",
  "chain_valid": true,
  "last_verified_at": "2026-03-15T12:00:00Z"
}
```

### POST /api/v1/audit/chain/verify

Run chain verification. Checks sequence continuity and hash integrity.

**Auth:** admin, super_admin

**Request:**
```json
{
  "epoch": null
}
```

- `epoch: null` — Verify entire chain
- `epoch: 3` — Verify only epoch 3

**Response:**
```json
{
  "status": "valid",
  "verified_entries": 12847,
  "first_sequence": 0,
  "last_sequence": 12846,
  "epochs_verified": 13,
  "broken_at_sequence": null,
  "broken_reason": null,
  "verification_time_ms": 2340
}
```

Possible `status` values: `valid`, `broken`, `gap_detected`
Possible `broken_reason` values: `hash_mismatch`, `sequence_gap`, `missing_entry`

### GET /api/v1/audit/chain/epochs

List all completed epochs with summary information.

**Auth:** analyst, admin, super_admin

**Response:**
```json
{
  "epochs": [
    {
      "epoch": 0,
      "first_sequence": 0,
      "last_sequence": 999,
      "entry_count": 1000,
      "first_timestamp": "2026-03-01T00:12:34Z",
      "last_timestamp": "2026-03-07T23:45:12Z",
      "epoch_final_hash": "7b2c...",
      "previous_epoch_hash": null,
      "exported": false
    }
  ],
  "total": 1
}
```

### POST /api/v1/audit/chain/export/{epoch_number}

Export a completed epoch as a downloadable JSON archive for air-gapped verification.

**Auth:** admin, super_admin

**Response:** JSON file download (`Content-Disposition: attachment`)

```json
{
  "export_metadata": {
    "sentora_version": "1.1.0",
    "tenant_id": "...",
    "epoch": 7,
    "epoch_size": 1000,
    "first_sequence": 7000,
    "last_sequence": 7999,
    "entry_count": 1000,
    "previous_epoch_hash": "a8f3...",
    "epoch_final_hash": "7b2c...",
    "exported_at": "2026-03-15T12:00:00Z",
    "exported_by": "admin@...",
    "chain_algorithm": "SHA-256",
    "export_hash": "..."
  },
  "entries": [...]
}
```

**Error Responses:**
- `404` — Epoch not found
- `409` — Epoch not yet complete

### POST /api/v1/audit/chain/initialize

Create the genesis entry. Idempotent — returns existing genesis if already initialized.

**Auth:** admin, super_admin

**Response (201):**
```json
{
  "sequence": 0,
  "epoch": 0,
  "action": "system.genesis",
  "hash": "..."
}
```

## Air-Gapped Verification CLI

```bash
# Verify single epoch
python -m sentora_verify audit_epoch_7.json

# Verify cross-epoch chain
python -m sentora_verify audit_epoch_7.json audit_epoch_6.json
```

Requirements: Python 3.10+ (stdlib only, no pip install needed)
