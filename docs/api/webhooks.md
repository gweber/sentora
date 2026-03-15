# Webhook Events Catalog

Sentora fires webhook notifications when significant application events occur. Webhooks are configured via **Settings > Webhooks** in the UI or via the REST API.

## Delivery Format

All webhook deliveries are HTTP POST requests with:

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `X-Webhook-Event` | Event name (e.g. `sync.completed`) |
| `X-Webhook-Signature` | HMAC-SHA256 hex digest of the payload |

**Payload envelope:**
```json
{
  "event": "event.name",
  "timestamp": "2026-03-15T12:00:00Z",
  "data": { /* event-specific payload */ }
}
```

**Signature verification:** Compute `HMAC-SHA256(secret, compact_json_body)` and compare against `X-Webhook-Signature`.

## Event Catalog

### Sync Events

#### `sync.completed`
Fired after a successful sync run.

```json
{
  "sites_synced": 3,
  "sites_total": 3,
  "groups_synced": 6,
  "groups_total": 6,
  "agents_synced": 135,
  "agents_total": 135,
  "apps_synced": 1042,
  "apps_total": 1042,
  "tags_synced": 12,
  "tags_total": 12
}
```

#### `sync.failed`
Fired when a sync run fails. Same payload as `sync.completed` with partial counts.

---

### Classification Events

#### `classification.completed`
Fired after a classification run completes.

#### `classification.anomaly_detected`
Fired when classification detects anomalous results.

---

### Enforcement Events

#### `enforcement.check.completed`
Fired after an enforcement check run completes.

```json
{
  "run_id": "...",
  "rules_checked": 20,
  "rules_passed": 18,
  "rules_failed": 2,
  "total_violations": 5,
  "new_violations": 3,
  "resolved_violations": 1,
  "source": "enforcement"
}
```

#### `enforcement.violation.new`
Fired when new violations are detected (aggregated per rule).

```json
{
  "rule_id": "...",
  "rule_name": "EDR Required",
  "severity": "critical",
  "affected_agents": 3,
  "top_hostnames": ["ws-alpha", "ws-beta", "ws-gamma"],
  "source": "enforcement"
}
```

#### `enforcement.violation.resolved`
Fired when previously violating agents become compliant.

```json
{
  "rule_id": "...",
  "rule_name": "EDR Required",
  "severity": "critical",
  "affected_agents": 2,
  "top_hostnames": ["ws-alpha", "ws-beta"],
  "source": "enforcement"
}
```

---

### Compliance Events

#### `compliance.check.completed`
Fired after a compliance check run completes.

```json
{
  "run_id": "...",
  "controls_evaluated": 45,
  "controls_passed": 39,
  "controls_failed": 4,
  "controls_warning": 2,
  "new_violations": 3,
  "resolved_violations": 1,
  "source": "compliance"
}
```

#### `compliance.violation.new`
Fired when new compliance violations are detected (aggregated per control).

```json
{
  "framework": "pci-dss",
  "control_id": "PCI-5.2.1",
  "control_name": "Anti-malware solution deployed",
  "severity": "critical",
  "affected_agents": 12,
  "summary": "EDR missing on 12 PCI-CDE endpoints",
  "source": "compliance"
}
```

#### `compliance.violation.resolved`
Fired when previously failing controls now pass.

```json
{
  "control_id": "PCI-5.2.1",
  "previously_affected": 12,
  "source": "compliance"
}
```

#### `compliance.score.degraded`
Fired when a framework's compliance score drops below a threshold (default: 80%).

```json
{
  "framework": "soc2",
  "previous_score": 87,
  "current_score": 72,
  "threshold": 80,
  "source": "compliance"
}
```

---

### Audit Chain Events

#### `audit.chain.integrity_failure`
Fired when chain verification detects tampering or corruption.

```json
{
  "broken_at_sequence": 4721,
  "reason": "hash_mismatch",
  "epoch": 4,
  "verified_entries": 4721,
  "source": "audit"
}
```

Possible `reason` values: `hash_mismatch`, `sequence_gap`, `missing_entry`

---

## Configuration

### REST API

```
POST /api/v1/webhooks/          Create a webhook
GET  /api/v1/webhooks/          List all webhooks
GET  /api/v1/webhooks/{id}      Get webhook details
PUT  /api/v1/webhooks/{id}      Update webhook
DELETE /api/v1/webhooks/{id}    Delete webhook
POST /api/v1/webhooks/{id}/test Send test event
```

All endpoints require admin role.

### Failure Handling

- Webhooks are auto-disabled after 10 consecutive delivery failures
- Re-enabling a webhook resets the failure counter
- Delivery timeout: 5 seconds
- SSRF protection validates target URLs

### Payload Schema Consistency

All violation events (compliance and enforcement) include a `source` field (`"compliance"` or `"enforcement"`) for unified processing by receivers.
