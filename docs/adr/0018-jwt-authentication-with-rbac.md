# ADR-0018: JWT Authentication with RBAC

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-03-15 |
| **Deciders** | Engineering |
| **Supersedes** | [ADR-0010: No Authentication in v1](0010-no-authentication-in-v1.md) |

## Context

ADR-0010 deferred application-layer authentication to post-v1, relying on network-level
controls (VPNs, firewall perimeters) as the primary security boundary. As Sentora matured
and moved toward enterprise deployment, this trade-off was no longer acceptable.
Application-layer auth became essential for several reasons:

- **Multi-role access control.** Enterprise organizations have distinct personas — platform
  operators, tenant administrators, security analysts, and read-only auditors — each
  requiring different levels of access to synced data, fingerprints, taxonomy, and
  configuration.

- **Stateless, token-based authentication.** Sentora's horizontal scaling model
  (ADR-0015) runs multiple uvicorn workers behind a single port. Server-side sessions
  would require sticky sessions or a shared session store, adding infrastructure
  complexity. A stateless token-based approach was preferred.

- **Enterprise SSO integration.** Customers deploying Sentora in regulated environments
  require integration with their existing identity providers (OIDC, SAML 2.0) to
  eliminate standalone credential management and satisfy compliance requirements
  (ADR-0016).

- **Optional multi-factor authentication.** Compliance frameworks (SOC 2 CC6.1, ISO
  27001 A.8.5) recommend or require MFA for privileged access.

- **Stolen-token detection.** Long-lived tokens (API keys, non-rotating refresh tokens)
  create a wide window of exposure if exfiltrated. The system needed a mechanism to
  detect and revoke compromised tokens without maintaining server-side session state.

- **Dual deployment support.** The authentication model must work cleanly for both
  on-prem single-tenant and SaaS multi-tenant deployment modes (ADR-0017) without code
  forks.

## Decision

Implement JWT-based authentication with role-based access control (RBAC), refresh token
rotation with family-based revocation, optional TOTP 2FA, and enterprise SSO support.

### Token Architecture

- **Access tokens**: JWT signed with HS256, 15-minute TTL. Contains user ID, email, role,
  and tenant context. Validated on every authenticated request via the `Authorization:
  Bearer <token>` header.

- **Refresh tokens**: Opaque tokens with 7-day TTL. Stored in MongoDB with family-based
  grouping. Each refresh exchanges the current token for a new access/refresh pair and
  invalidates the old refresh token. If a previously rotated refresh token is reused
  (indicating potential theft), the entire token family is revoked immediately.

### RBAC Model

Four hierarchical roles with increasing privilege:

| Role | Scope | Capabilities |
|---|---|---|
| `viewer` | Tenant | Read-only access to dashboards, reports, and classification results |
| `analyst` | Tenant | Viewer permissions plus fingerprint management, sync triggers, and taxonomy edits |
| `admin` | Tenant | Analyst permissions plus user management, configuration, and tenant settings |
| `super_admin` | Platform | Admin permissions plus tenant management, library source administration, and platform configuration (SaaS only) |

### FastAPI Integration

- **`get_current_user()`** — A FastAPI dependency that extracts and validates the Bearer
  token, checks the user revocation cache, and returns the authenticated user. Injected
  into all protected routes.

- **`require_role(*roles)`** — A dependency factory that wraps `get_current_user()` and
  verifies the user holds one of the specified roles. Used for route-level RBAC
  enforcement (e.g., `require_role("admin", "super_admin")`).

- **`require_platform_role()`** — Resolves to `admin` in on-prem mode or `super_admin`
  in SaaS mode (ADR-0017). Used for platform-level operations such as library source
  ingestion, eliminating scattered deployment-mode conditionals in routers.

- **`OptionalAuth`** — A permissive dependency for endpoints that must remain publicly
  accessible (health checks, deployment info). Returns the authenticated user if a valid
  token is present, or `None` otherwise. Preserves backward compatibility with
  pre-authentication clients.

### User Revocation Cache

A background task refreshes the set of disabled/revoked user IDs from MongoDB
approximately every 30 seconds. `get_current_user()` checks this cache on every request,
rejecting disabled users even if their JWT has not yet expired. This bounds the worst-case
revocation delay to ~30 seconds rather than the full 15-minute access token TTL.

### Account Lockout

Failed login attempts are tracked per account. After 5 failed attempts within a 15-minute
window, the account is temporarily locked. This mitigates brute-force and credential
stuffing attacks without requiring CAPTCHA infrastructure.

### TOTP Two-Factor Authentication

Optional TOTP-based 2FA implemented with `pyotp` for code generation/verification and
`qrcode` for provisioning QR codes. When enabled on an account, the login flow requires
a valid TOTP code after successful password verification. 2FA can be enforced at the role
level by administrators.

### SSO Integration

- **OIDC (OpenID Connect)** — Authorization code flow with PKCE. Configurable via
  environment variables for issuer URL, client ID, and client secret. Supports standard
  claims mapping for email, name, and role.

- **SAML 2.0** — Service Provider-initiated flow. Metadata-based configuration with
  support for signed assertions. Attribute mapping configurable for role and tenant
  assignment.

Both SSO providers support subject-based auto-provisioning: if an authenticated SSO user
does not yet exist in Sentora, an account is created automatically with a configurable
default role.

### First User Bootstrap

The first user to register is automatically promoted to `admin` (on-prem mode) or
`super_admin` (SaaS mode). This eliminates the need for a separate bootstrap CLI command
or seed script, enabling zero-configuration first-run experiences.

## Consequences

### Positive

- **Horizontal scalability.** Stateless JWT validation requires no shared session storage,
  aligning with the multi-worker architecture (ADR-0015).
- **Stolen-token detection.** Family-based refresh token revocation detects token theft
  without server-side session tracking. A reused rotated token triggers immediate
  revocation of all tokens in the family.
- **Enterprise-grade RBAC.** The four-role hierarchy matches enterprise organizational
  structures, with `require_platform_role()` cleanly bridging on-prem and SaaS modes.
- **SSO integration.** OIDC and SAML support eliminates standalone credential management
  for enterprise customers, satisfying compliance requirements.
- **Backward compatibility.** `OptionalAuth` preserves public access to health and
  deployment-info endpoints. Existing unauthenticated clients continue to work for
  those endpoints without modification.
- **Compliance alignment.** JWT + RBAC + 2FA + audit logging directly satisfies SOC 2
  CC6.1/CC6.2/CC6.3 and ISO 27001 A.8.2/A.8.3/A.8.5 controls (ADR-0016).

### Negative

- **Shared secret management.** HS256 requires a symmetric signing key (`JWT_SECRET`)
  shared across all workers. This secret must be securely generated, stored, and rotated
  in production environments.
- **Revocation delay.** Access tokens are valid for up to 15 minutes after user
  deactivation. The revocation cache reduces this to ~30 seconds in practice, but a
  small window remains.
- **External IdP dependency.** OIDC and SAML integration introduces a dependency on
  external identity providers. IdP outages can prevent SSO-only users from
  authenticating. Mitigated by supporting local fallback accounts.
- **Configuration complexity.** SSO requires per-environment configuration (issuer URLs,
  client credentials, certificate paths). Misconfiguration can lock out users or create
  security gaps.
- **TOTP recovery burden.** If a user loses their authenticator device, recovery requires
  administrator intervention to disable 2FA on the account. No backup codes are
  generated in the current implementation.

## Alternatives Considered

1. **Session-based authentication (server-side sessions).** Rejected — requires sticky
   sessions or a shared session store (Redis, database-backed sessions) to work across
   multiple workers. Adds infrastructure complexity and contradicts the stateless
   horizontal scaling model (ADR-0015).

2. **API key authentication.** Rejected — API keys carry no user identity, provide no
   role granularity, and cannot integrate with enterprise SSO. Suitable for
   service-to-service communication but not for user-facing access control.

3. **OAuth 2.0 with external authorization server.** Rejected — requires deploying and
   operating a separate authorization server (Keycloak, Auth0, etc.). Over-engineered for
   single-application deployment and adds an infrastructure dependency that conflicts with
   on-prem simplicity goals.

4. **Asymmetric JWT (RS256/ES256).** Rejected — requires key pair management (private key
   for signing, public key for verification). Adds operational complexity with no benefit
   when the token issuer and verifier are the same application process. RS256 would be
   reconsidered if Sentora ever separates the auth service from the API service.
