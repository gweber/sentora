# End-of-Life (EOL) Software Detection

Sentora detects End-of-Life software across your managed fleet using lifecycle
data from [endoflife.date](https://endoflife.date), a community-maintained
database tracking 445+ products with lifecycle dates.

## How It Works

### Data Source: endoflife.date

endoflife.date provides structured lifecycle data for software products
including release dates, active support end dates, and security support (EOL)
end dates. Sentora syncs this data daily and stores it in the `eol_products`
collection.

### Sync Schedule

- **Automatic**: Once daily (configurable)
- **Manual**: Via Library Sources UI → endoflife.date → "Sync Now"
- **Offline fallback**: If the API is unreachable, cached data is used

### Product Matching

Sentora uses a two-layer matching strategy to map installed applications to
endoflife.date products:

**Layer 1: CPE-based matching (high confidence)**
Applications already matched to NIST CPE entries are mapped via a curated
static mapping table (`CPE_TO_EOL_MAP`). This covers ~100 common products
with 90%+ confidence.

**Layer 2: Fuzzy name matching (lower confidence)**
For apps without CPE matches, normalized app names are compared against
endoflife.date product names using token overlap scoring. Fuzzy matches are
flagged for human review and **never auto-included in compliance results**.

### Match Review

Fuzzy matches appear in the Match Review section of the endoflife.date
source detail view. MSPs can:
- **Confirm**: Promotes the match to `manual` source with 100% confidence,
  including it in compliance checks
- **Dismiss**: Removes the match entirely

### Compliance Check: `eol_software_check`

The 11th compliance check type. For each agent in scope, it checks all
installed apps with confirmed EOL matches:

- **EOL**: App's matched cycle has passed its security support end date →
  VIOLATION
- **Security-only**: Active support ended but security support continues →
  WARNING (if `flag_security_only` is enabled)

#### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `flag_security_only` | bool | `true` | Also flag apps in security-only phase |
| `min_match_confidence` | float | `0.8` | Only consider matches above this threshold |
| `exclude_products` | list | `[]` | Product IDs to exclude from checking |

### Framework Controls

EOL controls are included in all 5 compliance frameworks:

| Framework | Control ID | Severity |
|---|---|---|
| DORA | `DORA-8.7-01` | high |
| SOC 2 | `SOC2-CC6.1-EOL` | high |
| PCI DSS | `PCI-6.3.3-EOL` | critical |
| HIPAA | `HIPAA-312a1-EOL` | high |
| BSI | `BSI-SYS.2.1-EOL` | high |

## Adding Manual Matches

For products not in endoflife.date or not auto-matched, MSPs can:
1. Navigate to Library Sources → endoflife.date
2. Find the product in the products table
3. Use the Match Review section to confirm fuzzy matches
4. Confirmed matches are promoted to `manual` source

## Architecture

```
endoflife.date API
     ↓ (daily sync)
eol_products collection
     ↓ (after sync / after S1 sync)
EOL matching engine
     ↓ (persisted on app_summaries)
eol_match field on each app summary
     ↓ (read by compliance engine)
eol_software_check results
```
