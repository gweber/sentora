# ADR-0010: No Authentication in v1

**Status**: Superseded by JWT + RBAC implementation (2026-03)
**Date**: 2025-01-01
**Deciders**: Architecture team
**Superseded**: 2026-03-15 — Full authentication is now implemented: JWT access/refresh tokens, RBAC (super_admin/admin/analyst/viewer), TOTP 2FA, OIDC/SAML SSO, server-side sessions, account lifecycle management (ADR-0018, ADR-0021). API key authentication for external integrations with scope-based access control (ADR-0022). All API endpoints require authentication. See `backend/domains/auth/`, `backend/domains/api_keys/`, and `backend/middleware/auth.py`.

## Context

Sentora is an internal IT operations tool deployed within corporate networks, accessed by security analysts and IT administrators who already operate behind VPNs, jump hosts, and firewall perimeters. The primary security boundary is network access, not application-layer authentication. In v1, the tool stores SentinelOne agent metadata (group memberships, installed application lists) but not credentials, PII, or S1 API tokens at rest. Implementing authentication — even basic API key or session-based auth — before the core classification workflow is validated would slow initial delivery without addressing the primary risk vector (network access by unauthorized users).

## Decision

Sentora v1 ships without application-layer authentication. The FastAPI middleware stack is structured with a placeholder auth layer that accepts any request but is designed to be replaced by an API key, OIDC, or LDAP middleware in a future version with minimal refactoring. Deployment documentation explicitly states that Sentora must not be exposed to untrusted networks and describes the expected network-level controls (VLAN restriction, reverse proxy with IP allowlist).

## Consequences

### Positive
- No auth implementation accelerates delivery of the core fingerprinting and classification features.
- Avoids the need to design a credential storage strategy, session management, or token rotation before the product is validated.
- Internal users are not blocked by credential provisioning on first deployment.
- The middleware placeholder ensures auth can be retrofitted without touching domain or router code.

### Negative
- Any user with network access to the Sentora host can read all synced S1 metadata, trigger syncs, and modify fingerprints and taxonomy.
- No audit trail of which user performed which action — all operations appear as anonymous.
- If Sentora is mistakenly exposed to a wider network segment, there is no application-layer fallback.

### Risks
- Deployment teams may skip the documented network-level controls, exposing S1 agent metadata to unintended users. Mitigated by making the deployment guide the default entry point and adding a startup warning banner if the app detects it is listening on a non-loopback interface without any auth middleware active.
- A future auth retrofit may require adding user context to the data model (e.g., audit fields on fingerprints); this is not accounted for in the v1 schema, meaning a migration will be needed.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
| HTTP Basic Auth | Credentials transmitted in every request header; requires HTTPS to be safe; adds credential management before value is validated |
| API key in request header | Reasonable for v2; deferred because key distribution and rotation must be designed before shipping, slowing v1 delivery |
| OIDC / SSO integration | Correct long-term solution for enterprise deployment; requires knowledge of the customer's identity provider; too complex for v1 internal use |
| mTLS | Strong network-layer auth but requires PKI infrastructure; not available in the target deployment environments |
