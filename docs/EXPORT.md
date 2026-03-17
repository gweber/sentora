# CPE-Enriched Software Inventory Export

Sentora provides a REST API endpoint that exports its software inventory
enriched with NIST CPE identifiers and EOL lifecycle data. This positions
Sentora as a **data source** for external vulnerability management tools.

## Endpoint

```
GET /api/v1/export/software-inventory
```

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `format` | `json\|csv` | `json` | Output format |
| `include_eol` | bool | `true` | Include EOL lifecycle data |
| `include_cpe` | bool | `true` | Include CPE identifiers |
| `scope_groups` | string | — | Comma-separated S1 group names |
| `scope_tags` | string | — | Comma-separated tags |
| `classification` | string | — | `approved\|flagged\|prohibited\|unclassified` |
| `page` | int | `1` | Page number |
| `page_size` | int | `1000` | Items per page (max 5000) |

### JSON Response

```json
{
  "export_metadata": {
    "tenant_id": "",
    "generated_at": "2026-03-16T12:00:00Z",
    "total_agents": 15234,
    "total_unique_apps": 4892,
    "filters_applied": {}
  },
  "software_inventory": [
    {
      "app_name": "Google Chrome",
      "app_version": "123.0.6312.86",
      "publisher": "Google LLC",
      "classification": "Approved Software/Browsers",
      "install_count": 12847,
      "agent_count": 12847,
      "cpe": {
        "cpe_uri": "cpe:2.3:a:google:chrome:123.0.6312.86:*:*:*:*:*:*:*",
        "vendor": "google",
        "product": "chrome"
      },
      "eol": {
        "product_id": "chrome",
        "cycle": "123",
        "eol_date": "2024-06-12",
        "is_eol": true,
        "is_security_only": false
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 1000,
    "total_items": 4892,
    "total_pages": 5
  }
}
```

### CSV Format

Flat CSV with headers matching the JSON field names. Nested objects are
flattened with underscore-separated prefixes (e.g., `cpe_uri`, `eol_product_id`).

## Authentication & Permissions

- Requires JWT authentication (standard session token)
- Requires `admin` or `viewer` role
- Tenant isolation enforced — only exports data for the authenticated tenant
- Every export request is logged in the audit log

## Caching

Export results are cached for 1 hour per unique filter combination. The cache
is stored in the `export_cache` MongoDB collection.

## Feeding Into External Tools

### Nucleus / Tenable / Qualys

Export as CSV with CPE identifiers. Most vulnerability management tools can
ingest CSV files with CPE URIs to correlate against their CVE databases.

### Dependency-Track

Export as JSON. Dependency-Track can process the software inventory to track
component versions and identify known vulnerabilities.

## Rate Limiting

The export endpoint shares the standard Sentora rate limit configuration.
For large exports (5000+ apps), use pagination to fetch results in batches.
