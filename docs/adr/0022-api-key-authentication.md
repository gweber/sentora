# ADR-0022: API Key Authentication for External Integrations

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-03-15 |
| **Deciders** | Engineering |
| **Extends** | [ADR-0018: JWT Authentication with RBAC](0018-jwt-authentication-with-rbac.md), [ADR-0021: Enterprise Auth Hardening](0021-enterprise-auth-hardening.md) |

## Context

Enterprise customers want to integrate Sentora data into their SIEM, dashboards, and
ticketing systems. The existing authentication system is user-based (JWT + SSO),
requiring an interactive login session. External integrations need a non-interactive,
long-lived credential that can be scoped, rate-limited, and revoked independently.

### Requirements

- Tenant-bound credentials (no user context required)
- Granular scope control (which endpoints, read vs write)
- Per-key rate limiting (independent from user rate limits)
- Immediate revocation (no cache delay)
- Full audit trail for key lifecycle events
- Key rotation without downtime (grace period)
- Secret-scanner-friendly format (grep-able prefix)

## Decision

Implement a tenant-scoped API key system as a new bounded context (`domains/api_keys/`)
alongside the existing JWT auth system.

### Key Format

```
sentora_sk_live_{48 hex chars}
```

- `sentora_sk_live_` prefix enables GitHub/GitGuardian/truffleHog detection
- 192-bit entropy (48 hex chars via `secrets.token_hex(24)`)
- Only the SHA-256 hash is stored; the plaintext key is shown once at creation

### Authentication Flow

The auth middleware detects API keys by their `sentora_sk_` prefix in either:
1. `Authorization: Bearer sentora_sk_live_...`
2. `X-API-Key: sentora_sk_live_...`

If no API key prefix is detected, the request falls through to JWT auth.

### Scope System

14 individual scopes (9 read, 3 write) plus 2 convenience groups (`read:all`, `write:all`).
Scope enforcement applies only to API key auth — JWT users are governed by RBAC.

### Key Management Security

Key CRUD endpoints require JWT user auth with admin role. API keys cannot create,
modify, or revoke other API keys — this prevents privilege escalation.

### Rate Limiting

Per-key sliding-window rate limiters (separate from global IP-based rate limiting).
Configurable per-minute and per-hour limits with sensible defaults (60/min, 1000/hr).

### Key Rotation

`POST /api-keys/{id}/rotate` creates a new key with identical configuration and
revokes the old key with a 5-minute grace period, enabling zero-downtime rotation.

## Consequences

### Positive

- **Non-interactive integration.** SIEM/dashboard/automation tools authenticate
  without a user session.
- **Least privilege.** Scopes limit each key to only the data it needs.
- **Immediate revocation.** Every request validates the key hash against the DB.
- **Audit trail.** Key creation, rotation, revocation, and first-use events are logged.
- **Secret scanning.** The `sentora_sk_live_` prefix is detectable by all major
  secret scanners, reducing the risk of accidental key exposure.

### Negative

- **DB lookup per request.** API key auth requires a MongoDB query per request
  (vs stateless JWT). This is acceptable for integration traffic volumes and
  can be cached with a short TTL if needed.
- **Key management surface.** New CRUD endpoints and UI increase the attack surface.
  Mitigated by requiring admin JWT auth for all management operations.

### Risks

- **Key leakage.** If a key is leaked, it provides access until revoked. Mitigated
  by: never storing the plaintext, showing it only once, grep-able prefix for
  scanning, and immediate revocation capability.
- **Rate limit memory.** Per-key rate limiters consume in-memory state. With
  typical integration key counts (<100), this is negligible.

## Alternatives Considered

1. **OAuth 2.0 Client Credentials.** Rejected — adds significant complexity
   (token exchange flow, refresh logic) for a use case that only needs static
   bearer tokens. API keys are simpler for M2M integration.

2. **Service accounts (user-type entities).** Rejected — blurs the line between
   human users and integrations. API keys explicitly have no user context,
   making the audit trail clearer.

3. **HMAC-signed requests.** Rejected — significantly increases integration
   complexity for consumers. Bearer tokens are the de facto standard for
   REST API integrations.
