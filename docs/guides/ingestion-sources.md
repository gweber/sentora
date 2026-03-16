# Library Ingestion Sources

This guide explains how to populate the fingerprint library from public software databases.

---

## Available Sources

| Source | Adapter | What it provides | API key required? |
|--------|---------|-----------------|-------------------|
| **NIST CPE Dictionary** | `nist_cpe` | Software entries from the National Vulnerability Database Common Platform Enumeration. Covers ~1M application, OS, and hardware definitions. Only applications (`cpe:2.3:a:*`) are ingested. | No (recommended for heavy use) |
| **MITRE ATT&CK** | `mitre` | Malware and tool definitions from the MITRE ATT&CK STIX 2.1 bundle. Includes names, aliases, and descriptions. | No |
| **Chocolatey** | `chocolatey` | Popular Windows packages from the Chocolatey community repository. Filtered by minimum download count. | No |
| **Homebrew** | `homebrew` | macOS/Linux formula names and aliases from the Homebrew JSON API. | No |

---

## Triggering Ingestion

### Via the Admin UI

1. Navigate to **Library Sources** in the admin sidebar.
2. Each source card shows its description, last run status, and entry counts.
3. Click **Run Ingestion** on any source card to trigger a run.
4. The ingestion runs in the background. Refresh the page or check the history table for completion status.

### Via the API

```bash
# Trigger a specific source
curl -X POST http://localhost:5002/api/v1/library/sources/nist_cpe/ingest \
  -H "Authorization: Bearer <admin-token>"

# List available sources
curl http://localhost:5002/api/v1/library/sources/ \
  -H "Authorization: Bearer <admin-token>"

# View run history
curl http://localhost:5002/api/v1/library/ingestion-runs/ \
  -H "Authorization: Bearer <admin-token>"
```

---

## Automatic Ingestion

To enable scheduled background ingestion, configure these settings (via `.env` or the Settings UI):

```dotenv
# Enable the ingestion scheduler
LIBRARY_INGESTION_ENABLED=true

# Run every 24 hours (range: 1–168)
LIBRARY_INGESTION_INTERVAL_HOURS=24

# Which sources to run automatically
LIBRARY_INGESTION_SOURCES=nist_cpe,mitre,chocolatey,homebrew
```

The scheduler runs enabled sources sequentially at the configured interval. Manual triggers via the API or UI always work regardless of this setting.

---

## How Pattern Generation Works

Each adapter converts upstream data into glob patterns that can match against Sentora's normalized app names.

### NIST CPE

CPE URIs like `cpe:2.3:a:google:chrome:*:*:*:*:*:*:*:*` are parsed into:

| Pattern | Weight | Confidence |
|---------|--------|------------|
| `*google*chrome*` | 1.0 | Vendor-qualified — high precision |
| `*chrome*` | 0.8 | Broad — may match unrelated apps |

Rules:
- Only applications (`part=a`) are ingested; OS and hardware entries are skipped.
- Product names shorter than 4 characters are excluded from broad patterns (too noisy).
- Underscores in vendor/product names are converted to spaces.
- Deduplication by `vendor:product` pair prevents redundant entries.

### MITRE ATT&CK

Malware and tool names become patterns directly:
- Entry name → `*{name}*`
- Each alias → `*{alias}*`
- Revoked and deprecated entries are skipped.

### Chocolatey / Homebrew

Package names and titles become patterns:
- Package ID → `*{id}*`
- Title (if different) → `*{title}*`

---

## Ingestion Run Tracking

Each run creates an `IngestionRun` document with:

| Field | Description |
|-------|-------------|
| `source` | Adapter name |
| `status` | `running`, `completed`, or `failed` |
| `entries_created` | New library entries created |
| `entries_updated` | Existing entries updated (version bumped) |
| `entries_skipped` | Entries skipped (no changes detected) |
| `errors` | Error messages from the run |
| `started_at` / `completed_at` | Timestamps |

View run history in the Library Sources admin UI or via `GET /api/v1/library/ingestion-runs/`.

---

## Rate Limiting

The **NIST CPE** adapter enforces rate limits to comply with NVD API policies:
- **Without API key**: 6-second delay between requests.
- **With API key**: 0.6-second delay between requests.

To obtain an NVD API key, visit: https://nvd.nist.gov/developers/request-an-api-key

Other adapters use reasonable delays but are not subject to strict rate limiting.

---

## Concurrency Protection

Only one ingestion run can execute at a time (per adapter). The ingestion manager uses an `asyncio.Lock` to prevent concurrent runs. If you trigger ingestion while another run is active, you'll receive an error indicating the current source being ingested.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Ingestion already running" | A previous run hasn't completed | Wait for it to finish, or check for stuck runs in the history |
| "Unknown source: xyz" | Invalid adapter name | Use one of: `nist_cpe`, `mitre`, `chocolatey`, `homebrew` |
| NIST CPE returns 0 entries | NVD API rate limiting or outage | Check NVD status; try again later or add an API key |
| MITRE returns 0 entries | GitHub raw content CDN issue | Verify connectivity to `raw.githubusercontent.com` |
| Many entries created but patterns look wrong | CPE-to-glob mapping heuristic | Review entries in the Library browser; edit or deprecate inaccurate ones |
