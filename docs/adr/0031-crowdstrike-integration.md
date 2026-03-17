# ADR-0031: CrowdStrike Falcon Integration

**Status:** Accepted
**Date:** 2026-03-17

## Context

Sentora's initial source-agnostic Canonical Data Model (ADR-0030) was implemented with SentinelOne as the first adapter. Single-vendor dependency was identified as the largest risk factor (-20% in valuation). CrowdStrike Falcon holds approximately 25% of the EDR market, making it the natural second integration target.

The CrowdStrike API architecture differs significantly from SentinelOne:
- **Authentication:** OAuth2 Client Credentials Flow (vs. API token for S1)
- **Pagination:** Scroll-based cursors for Hosts API, cursor-based for Discover API
- **Application Inventory:** Requires separate Falcon Discover license and API
- **Regions:** Four distinct API regions (US-1, US-2, EU-1, US-GOV-1)
- **No native delta endpoint:** Must use FQL `modified_timestamp` filters

## Decision

### SDK Choice
Use **FalconPy** (`crowdstrike-falconpy`), the official CrowdStrike Python SDK maintained by CrowdStrike. It handles OAuth2 token lifecycle automatically.

### API Strategy
- **Hosts:** `QueryDevicesByFilterScroll` (cursor-based, no maximum) + `GetDeviceDetailsV2` (batch of 5000)
- **Applications:** `query_combined_applications` via Falcon Discover (cursor-based, 100/page)
- **Groups:** `query_combined_host_groups` (offset-based, 500/page)

### Sync Strategy
- **Full Sync:** No FQL filter — scroll through all hosts and all applications
- **Incremental Refresh:** FQL filter `modified_timestamp:>'<last_sync>'` for hosts; `last_updated_timestamp:>'<last_sync>'` for applications
- **Resume:** CrowdStrike scroll cursors expire after ~2 minutes, so resume uses `modified_timestamp` filtering from the last successful batch timestamp rather than persisting expired cursors

### Architecture
- CrowdStrike phase runners (`cs_groups`, `cs_agents`, `cs_apps`) extend the existing `PhaseRunner` base class
- Phase names are prefixed with `cs_` to coexist alongside S1 phases in `SyncManager`
- Each source uses its own `sync_meta` document (keyed by source name) for independent timestamps
- Stale-record deletion is scoped by `source: "crowdstrike"` to prevent cross-source interference

### Frontend
- Tabbed `IntegrationsView` wraps the existing `SyncView` component
- `SyncView` accepts `source`, `sourceLabel`, and `phaseKeys` props for source-specific rendering
- When only one source is configured, the tab bar is hidden

## Consequences

### Positive
- Sentora supports 2 EDR sources (SentinelOne + CrowdStrike Falcon)
- S1 dependency drops from 100% to ~50%
- Addressable market roughly doubles
- Source Adapter Pattern is validated with a real second implementation

### Negative
- Falcon Discover license required for application inventory (without it, only host data is available)
- Application sync for large fleets (150k+ hosts) can take hours due to API pagination limits
- FalconPy is synchronous — all calls wrapped in `asyncio.to_thread()` (minor performance overhead)

### Neutral
- New dependency: `crowdstrike-falconpy>=1.4.0`
- CrowdStrike does not have S1-style "sites" — the `site_id` field is empty on CS agents
- CrowdStrike uses "contained" as a host status (new canonical status value alongside "online"/"offline")
