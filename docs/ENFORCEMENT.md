# Enforcement Rules

Enforcement rules define software policies using Sentora's taxonomy system. Each rule links a taxonomy category to an enforcement mode and a scope — telling Sentora which software must be present, which must be absent, and which endpoints to check.

---

## Rule Types

### Required

Every agent in scope must have **at least one** installed application that matches a taxonomy entry in the specified category.

**Example:** "EDR must be installed on all endpoints"
- Taxonomy category: `required_edr` (contains entries with patterns like `SentinelOne*`, `CrowdStrike*`)
- Type: Required
- Scope: All agents
- An agent without any EDR application matching those patterns is a violation.

### Forbidden

**No** agent in scope may have an application matching a taxonomy entry in the specified category.

**Example:** "No P2P software"
- Taxonomy category: `forbidden_p2p` (contains entries with patterns like `*torrent*`, `*eMule*`)
- Type: Forbidden
- Scope: All agents
- An agent with uTorrent installed is a violation (one violation per forbidden app found).

### Allowlist

Every application installed on agents in scope must match **at least one** taxonomy entry in the specified category. Any application that doesn't match is a violation.

**Example:** "Only approved software on PCI endpoints"
- Taxonomy category: `pci_approved` (contains entries for all approved applications)
- Type: Allowlist
- Scope: Agents in group `PCI-CDE`
- Any application not matching an entry in `pci_approved` is a violation.

---

## Creating a Rule

1. Navigate to **Enforcement** in the sidebar.
2. Click **Create Rule**.
3. Fill in the form:
   - **Name** — a descriptive name (e.g. "EDR Required")
   - **Taxonomy Category** — select from the dropdown (shows all categories from Taxonomy)
   - **Type** — Required, Forbidden, or Allowlist
   - **Severity** — Critical, High, Medium, or Low
   - **Scope Groups** — select specific S1 groups (leave empty for all agents)
   - **Scope Tags** — select specific agent tags (leave empty for all agents)
   - **Labels** — optional framework references (e.g. `PCI-DSS 5.2.1`, `BSI SYS.2.1.A6`)
4. Click **Create Rule**.

The rule is immediately active and will be evaluated on the next check run.

---

## How Checks Work

1. The engine loads all glob patterns from taxonomy entries in the rule's category.
2. It compiles the patterns to case-insensitive regex for fast matching.
3. It queries all agents matching the scope filter (groups and/or tags).
4. For each agent, it checks the `installed_app_names` array against the compiled patterns.
5. The result (pass/fail) and violations are stored in `enforcement_results` with a 90-day TTL.

### Performance

Checks iterate agents using MongoDB cursors — they do not load the entire fleet into memory. Pattern compilation is cached. At 150k agents, a full check with 20 rules completes in under 10 seconds.

---

## Automatic Execution

Enforcement checks run automatically after every successful data sync. No additional scheduling is required.

You can also trigger checks manually:
- **Run All** — click the "Run All Checks" button on the Enforcement page
- **Single Rule** — use the API: `POST /api/v1/enforcement/check/{rule_id}`

---

## Webhooks

Enforcement fires three webhook events:

| Event | When |
|-------|------|
| `enforcement.check.completed` | After every check run (summary of rules checked, passed, failed) |
| `enforcement.violation.new` | When new violations are detected (not present in the previous check) |
| `enforcement.violation.resolved` | When previously non-compliant agents become compliant |

Webhook payload example:
```json
{
  "event": "enforcement.violation.new",
  "timestamp": "2026-03-15T12:00:00Z",
  "data": {
    "rule_id": "...",
    "rule_name": "EDR Required",
    "severity": "critical",
    "affected_agents": 3,
    "top_hostnames": ["ws-alpha", "ws-beta", "ws-gamma"],
    "source": "enforcement"
  }
}
```

Configure webhooks under **Settings > Webhooks**. See [Webhook Events Catalog](api/webhooks.md) for full payload schemas.

---

## Viewing Violations

Enforcement violations appear in the **unified violations feed** on the Compliance Dashboard. Filter by source "Enforcement" to see only enforcement findings.

Each violation shows:
- The hostname and agent ID of the affected endpoint
- What the violation is (missing required app, forbidden app found, unapproved app)
- The rule that triggered it
- Severity level

---

## Taxonomy Integration

Enforcement rules reference taxonomy categories. The taxonomy must have entries with glob patterns for the enforcement engine to match against.

**Recommended category structure:**
```
Required / EDR          → SentinelOne*, CrowdStrike*, Trellix*
Required / Encryption   → BitLocker*, FileVault*, VeraCrypt*
Required / Backup       → Veeam*, Acronis*, CrashPlan*
Forbidden / P2P         → *torrent*, *eMule*, *LimeWire*
Forbidden / Remote      → TeamViewer*, AnyDesk*, LogMeIn*
PCI Approved            → (all approved apps for PCI scope)
```

If a rule references a category with no taxonomy entries, the check passes with a warning ("No taxonomy patterns found").

---

## API Reference

All enforcement endpoints are under `/api/v1/enforcement/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/rules` | List all rules |
| POST | `/rules` | Create a new rule |
| GET | `/rules/{id}` | Get rule detail |
| PUT | `/rules/{id}` | Update a rule |
| DELETE | `/rules/{id}` | Delete a rule |
| PUT | `/rules/{id}/toggle` | Enable/disable a rule |
| POST | `/check` | Run all enabled rules |
| POST | `/check/{rule_id}` | Run a single rule |
| GET | `/results/latest` | Latest result per rule |
| GET | `/results/{rule_id}` | Result history for a rule |
| GET | `/summary` | Aggregated summary |
| GET | `/violations` | Current violations (paginated) |
