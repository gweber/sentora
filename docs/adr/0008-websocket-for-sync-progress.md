# ADR-0008: WebSocket for Sync Progress

**Status**: Accepted
**Date**: 2025-01-01
**Deciders**: Architecture team

## Context

A full SentinelOne sync in large environments takes between 2 and 10 minutes. The S1 applications endpoint is rate-limited and must be polled in batches of 100 agents at a time, with paging across the full agent inventory. Users who trigger a sync from the Sentora UI need real-time visibility into progress — which phase is running (agent fetch, app fetch, normalization, fingerprint update), how many agents have been processed, and whether errors are occurring — to avoid triggering duplicate syncs or abandoning a long-running operation. A purely asynchronous fire-and-forget model would leave users with no feedback.

## Decision

Sentora exposes a `/ws/sync/progress` WebSocket endpoint. When a sync is in progress, the backend publishes structured progress events (`{ phase, processed, total, message, error? }`) over the socket at meaningful intervals. The Vue 3 frontend opens the WebSocket connection when the user initiates a sync and closes it on completion or error. All currently connected clients receive broadcast progress events, so multiple browser tabs remain consistent.

## Consequences

### Positive
- Users receive live progress feedback without polling the server repeatedly.
- Structured event payloads allow the Vue UI to render a progress bar, phase label, and count without parsing free-text strings.
- Error events during sync (e.g., S1 rate limit hit, timeout on a batch) are surfaced immediately rather than discovered only on completion.
- WebSocket infrastructure is already required for future planned features (live classification updates on fingerprint edit) — the investment is not single-use.
- FastAPI's native WebSocket support (`fastapi.WebSocket`) requires no additional framework.

### Negative
- WebSocket connections require persistent server-side state (connection registry) that complicates horizontal scaling.
- Browser WebSocket connections are subject to proxy and firewall timeout policies common in corporate networks; reconnection logic must be implemented in the Vue client.
- Testing WebSocket endpoints requires a different approach than standard HTTP endpoint tests.

### Risks
- If the backend process is restarted mid-sync, connected WebSocket clients will be disconnected with no automatic recovery; the sync state must be queryable via a fallback HTTP endpoint.
- Corporate network proxies that do not support WebSocket upgrades will silently fail; the UI must detect and report this degraded state.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| HTTP polling (client polls `/sync/status` every N seconds) | Wasteful on both client and server; introduces up to N seconds of display lag; requires the server to maintain sync state between polls regardless |
| Server-Sent Events (SSE) | Technically adequate for unidirectional progress events but uses a separate protocol path; since WebSocket is needed for future bidirectional features, SSE adds a second real-time transport to maintain |
| Long polling | High per-request overhead; harder to implement bounded-context event fan-out compared to a persistent WebSocket connection |
| Callback / webhook on completion | Only signals done/failed, not incremental progress; does not solve the user experience problem for long-running syncs |
