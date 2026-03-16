# Access Control Policy

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-AC-001                                |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Security & Compliance Team                 |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Purpose

This policy defines the access control requirements for the Sentora platform. It
governs how users are authenticated, authorized, and managed throughout their lifecycle.
The policy implements the principle of least privilege and separation of duties across
all system components.

---

## 2. Scope

This policy applies to:

- All human users accessing Sentora (via browser or API)
- Service accounts and API integrations
- Administrative access to infrastructure (MongoDB, Docker, host OS)
- The SentinelOne API integration service account

---

## 3. Role-Based Access Control (RBAC) Model

### 3.1 Role Definitions

Sentora implements a hierarchical RBAC model with four roles. Higher roles inherit
all permissions of lower roles. Available roles depend on the deployment mode.

| Role | Level | Description | Typical User | Availability |
|------|-------|-------------|--------------|--------------|
| `super_admin` | 4 | Full platform control including tenant management, library source ingestion, and cross-tenant configuration | SaaS platform operator | SaaS only |
| `admin` | 3 | User management, taxonomy management, full data access, sync control. In on-prem mode, this is the highest role and includes library source management | IT administrator, team lead | Both modes |
| `analyst` | 2 | Fingerprint review, classification management, read/write operational data | Security analyst, software asset manager | Both modes |
| `viewer` | 1 | Read-only access to dashboards, reports, and inventory data | Auditor, manager, stakeholder | Both modes |

> **Deployment modes:** Sentora supports two deployment modes controlled by `DEPLOYMENT_MODE`:
> - **On-prem** (`onprem`): Single-tenant deployment. `admin` is the top role. The first registered user is auto-promoted to `admin`. Library source management is accessible to `admin`. Tenant management is not available.
> - **SaaS** (`saas`): Multi-tenant deployment with database-per-tenant isolation. `super_admin` manages the platform. The first registered user is auto-promoted to `super_admin`. Each tenant has its own `admin`, `analyst`, and `viewer` users.

### 3.2 Permission Matrix

| Resource / Action | viewer | analyst | admin | super_admin |
|-------------------|--------|---------|-------|-------------|
| **Dashboard** | | | | |
| View dashboard statistics | Read | Read | Read | Read |
| **Agents** | | | | |
| View agent inventory | Read | Read | Read | Read |
| View agent details | Read | Read | Read | Read |
| **Applications** | | | | |
| View installed applications | Read | Read | Read | Read |
| **Fingerprints** | | | | |
| View fingerprint results | Read | Read | Read | Read |
| Review fingerprint proposals | -- | Read/Write | Read/Write | Read/Write |
| Approve/reject proposals | -- | Write | Write | Write |
| Create manual fingerprints | -- | Write | Write | Write |
| **Classification** | | | | |
| View classifications | Read | Read | Read | Read |
| Manage classification rules | -- | Read/Write | Read/Write | Read/Write |
| Run classification | -- | Execute | Execute | Execute |
| **Taxonomy** | | | | |
| View taxonomy | Read | Read | Read | Read |
| Create/edit categories | -- | -- | Write | Write |
| Create/edit vendors | -- | -- | Write | Write |
| Manage software library | -- | -- | Write | Write |
| Seed taxonomy data | -- | -- | Execute | Execute |
| **Sync** | | | | |
| View sync status | Read | Read | Read | Read |
| Trigger manual sync | -- | -- | Execute | Execute |
| View sync WebSocket | Read | Read | Read | Read |
| Configure sync settings | -- | -- | Write | Write |
| **Tags** | | | | |
| View tags | Read | Read | Read | Read |
| Manage tag rules | -- | Read/Write | Read/Write | Read/Write |
| **Users** | | | | |
| View own profile | Read | Read | Read | Read |
| Update own profile | Write | Write | Write | Write |
| View all users | -- | -- | Read | Read |
| Create users | -- | -- | Write | Write |
| Modify user roles | -- | -- | Write | Write |
| Delete users | -- | -- | Write | Write |
| Promote to admin | -- | -- | -- | Write |
| **Configuration** | | | | |
| View runtime config | -- | -- | Read | Read |
| Modify runtime config | -- | -- | -- | Write |
| **Library Sources** | | | | |
| Browse library entries | Read | Read | Read | Read |
| Subscribe group to library | -- | Write | Write | Write |
| Manage ingestion sources | -- | -- | Write (on-prem) | Write |
| Trigger ingestion | -- | -- | Execute (on-prem) | Execute |
| **Tenants** (SaaS only) | | | | |
| View/manage tenants | -- | -- | -- | Write |
| **API Keys** | | | | |
| View API keys | -- | -- | Read | Read |
| Create API key | -- | -- | Write | Write |
| Update API key (name, scopes, limits) | -- | -- | Write | Write |
| Rotate API key | -- | -- | Write | Write |
| Revoke API key | -- | -- | Write | Write |
| Use API key (self-info) | via API key | via API key | via API key | via API key |
| **Webhooks** | | | | |
| View webhooks | -- | -- | Read | Read |
| Create/edit/delete webhooks | -- | -- | Write | Write |
| Test webhook delivery | -- | -- | Execute | Execute |
| **Audit Logs** | | | | |
| View audit logs | -- | -- | Read | Read |
| Export audit logs | -- | -- | Read | Read |
| **System** | | | | |
| View health/metrics | Read | Read | Read | Read |
| View API documentation | Read | Read | Read | Read |

### 3.3 Role Assignment Rules

1. New users are assigned the `viewer` role by default
2. Role changes require `admin` or higher privileges
3. Promotion to `admin` requires `super_admin` privileges (SaaS mode)
4. The `super_admin` role cannot be self-assigned; it is only available in SaaS mode
5. The first registered user is auto-promoted: `admin` in on-prem mode, `super_admin` in SaaS mode
6. In on-prem mode, at least one `admin` must exist at all times
7. In SaaS mode, at least one `super_admin` must exist at all times
8. Role changes are recorded in the audit log with the acting user, target user, previous role, and new role

---

## 4. Authentication

### 4.1 Password Authentication

#### 4.1.1 Password Requirements

| Requirement | Value |
|-------------|-------|
| Minimum length | 12 characters |
| Maximum length | 128 characters |
| Uppercase letters | At least 1 required |
| Lowercase letters | At least 1 required |
| Digits | At least 1 required |
| Special characters | Not required by default (NIST SP 800-63B recommends against; configurable via `PASSWORD_REQUIRE_SPECIAL`) |
| Breach database check | Passwords checked against HaveIBeenPwned via k-Anonymity API (configurable via `PASSWORD_CHECK_BREACHED`) |
| Password history | Last 5 passwords cannot be reused (configurable via `PASSWORD_HISTORY_COUNT`) |
| Maximum age | No expiry by default (NIST-compliant; configurable via `PASSWORD_MAX_AGE_DAYS`) |

#### 4.1.2 Password Storage

- Passwords are hashed using bcrypt 5.x with an appropriate work factor
- Plaintext passwords are never stored, logged, or transmitted in responses
- Password hashes are stored in the MongoDB `users` collection
- The password field is excluded from all DTO response models

**Implementation:** `backend/domains/auth/service.py`

### 4.2 JWT Token Lifecycle

#### 4.2.1 Token Types

| Token Type | Lifetime | Storage | Purpose |
|------------|----------|---------|---------|
| Access token | 15 minutes | `localStorage` (`sentora_token`) | API authorization |
| Refresh token | 7 days | `localStorage` (`sentora_refresh_token`) | Access token renewal |

#### 4.2.2 Token Claims

Access tokens contain IdP-grade claims (ADR-0021):

```
{
  "sub": "<username>",
  "role": "<user_role>",
  "type": "access",
  "iss": "sentora",
  "aud": "sentora-api",
  "jti": "<unique_token_id>",
  "sid": "<server_side_session_id>",
  "exp": <expiration_timestamp>
}
```

The `sid` claim links the token to a server-side session. If the session is
revoked (via admin action, password change, or user self-service), the token
is rejected immediately — without waiting for JWT expiry.

#### 4.2.3 Token Rotation

- Each refresh token can only be used once
- Using a refresh token issues a new access token AND a new refresh token
- The previous refresh token is invalidated upon use
- If a previously-used refresh token is presented, all tokens for that user are revoked (replay detection)
- Token revocation is logged in the audit trail

#### 4.2.4 Token Signing

| Parameter | Value |
|-----------|-------|
| Algorithm | HS256 (default) or RS256 (when asymmetric keys configured) |
| Secret source | `JWT_SECRET_KEY` environment variable |
| Key rotation | Supported via key versioning in token header |

**Implementation:** `backend/domains/auth/service.py`, `backend/middleware/auth.py`

### 4.3 TOTP Two-Factor Authentication

#### 4.3.1 Enrollment Process

1. User requests 2FA enrollment via `POST /api/v1/auth/2fa/enroll`
2. Server generates a TOTP secret and returns a provisioning URI (for QR code)
3. User scans QR code with authenticator app (Google Authenticator, Authy, etc.)
4. User submits a verification code via `POST /api/v1/auth/2fa/verify`
5. Server validates the code and enables 2FA on the account
6. Recovery codes are generated and returned (one-time display)

#### 4.3.2 TOTP Parameters

| Parameter | Value |
|-----------|-------|
| Algorithm | SHA-1 (RFC 6238 standard) |
| Digits | 6 |
| Period | 30 seconds |
| Window | +/- 1 period (to account for clock skew) |
| Recovery codes | 10 single-use codes generated at enrollment |

#### 4.3.3 Login with 2FA

1. User submits email and password via `POST /api/v1/auth/login`
2. If 2FA is enabled, server returns `{ "requires_2fa": true, "temp_token": "..." }`
3. User submits TOTP code with temp token via `POST /api/v1/auth/2fa/authenticate`
4. Server validates TOTP code and issues full JWT tokens
5. If TOTP validation fails, attempt is counted toward account lockout

#### 4.3.4 2FA Enforcement

| Role | 2FA Requirement |
|------|----------------|
| super_admin | Mandatory |
| admin | Mandatory |
| analyst | Recommended (configurable enforcement) |
| viewer | Optional |

### 4.4 OIDC Single Sign-On

#### 4.4.1 Configuration

| Parameter | Source | Description |
|-----------|--------|-------------|
| `OIDC_ISSUER_URL` | Environment variable | Identity provider issuer URL |
| `OIDC_CLIENT_ID` | Environment variable | Application client ID |
| `OIDC_CLIENT_SECRET` | Environment variable | Application client secret (Restricted) |
| `OIDC_REDIRECT_URI` | Environment variable | Callback URL after authentication |
| `OIDC_SCOPES` | Environment variable | Requested scopes (default: `openid profile email`) |

#### 4.4.2 Authentication Flow

1. User clicks "Sign in with SSO" on the login page
2. Frontend redirects to `GET /api/v1/auth/oidc/authorize`
3. Backend redirects to IdP authorization endpoint with PKCE challenge
4. User authenticates with IdP
5. IdP redirects back to `GET /api/v1/auth/oidc/callback` with authorization code
6. Backend exchanges code for tokens at IdP token endpoint
7. Backend validates ID token claims (issuer, audience, expiration, nonce)
8. Backend maps IdP claims to Sentora user (creates account if auto-provisioning enabled)
9. Backend issues Sentora JWT tokens
10. Frontend receives tokens and establishes session

#### 4.4.3 Claim Mapping

| IdP Claim | Sentora Field | Notes |
|-----------|------------------|-------|
| `sub` | External user ID | Unique identifier from IdP |
| `email` | User email | Must be verified (`email_verified: true`) |
| `name` | Display name | Optional |
| `groups` | Role mapping | Configurable group-to-role mapping |

### 4.5 SAML Single Sign-On

#### 4.5.1 Configuration

| Parameter | Source | Description |
|-----------|--------|-------------|
| `SAML_IDP_METADATA_URL` | Environment variable | IdP metadata endpoint |
| `SAML_SP_ENTITY_ID` | Environment variable | Service provider entity ID |
| `SAML_SP_CERT` | File path | SP certificate for signing |
| `SAML_SP_KEY` | File path | SP private key (Restricted) |
| `SAML_ACS_URL` | Environment variable | Assertion Consumer Service URL |

#### 4.5.2 Authentication Flow

1. User clicks "Sign in with SAML SSO" on the login page
2. Frontend initiates via `GET /api/v1/auth/saml/login`
3. Backend generates SAML AuthnRequest and redirects to IdP
4. User authenticates with IdP
5. IdP posts SAML Response to `POST /api/v1/auth/saml/acs`
6. Backend validates SAML assertion (signature, conditions, audience)
7. Backend maps SAML attributes to Sentora user
8. Backend issues Sentora JWT tokens

#### 4.5.3 Attribute Mapping

| SAML Attribute | Sentora Field |
|----------------|------------------|
| `NameID` | External user ID |
| `email` / `mail` | User email |
| `displayName` / `cn` | Display name |
| `memberOf` / `groups` | Role mapping |

### 4.6 API Key Authentication (ADR-0022)

API keys provide non-interactive authentication for external integrations.

#### 4.6.1 Key Format

Keys use the prefix `sentora_sk_live_` followed by 48 hex characters (192-bit entropy).
The prefix enables detection by GitHub, GitGuardian, and truffleHog secret scanners.

#### 4.6.2 Key Storage

- Only the SHA-256 hash of the key is stored in the `api_keys` MongoDB collection
- The plaintext key is returned exactly once at creation time
- Keys cannot be retrieved after creation — if lost, create a new key and revoke the old one

#### 4.6.3 Key Scopes

Each key is granted a set of scopes that control which endpoints it can access:

| Scope Category | Scopes |
|----------------|--------|
| Read-only (9) | `agents:read`, `apps:read`, `compliance:read`, `enforcement:read`, `audit:read`, `sync:read`, `taxonomy:read`, `fingerprints:read`, `dashboard:read` |
| Write (3) | `sync:trigger`, `enforcement:write`, `tags:write` |
| Convenience | `read:all` (all read scopes), `write:all` (all scopes) |

Scope enforcement applies only to API key auth. JWT users are governed by RBAC.

#### 4.6.4 Key Management Security

- Key CRUD endpoints (`/api/v1/api-keys/`) require JWT user auth with `admin` or `super_admin` role
- API keys cannot create, modify, or revoke other API keys (prevents privilege escalation)
- Key rotation creates a new key with identical configuration; old key has a 5-minute grace period

#### 4.6.5 Request Headers

API keys are accepted via two headers:
- `Authorization: Bearer sentora_sk_live_...`
- `X-API-Key: sentora_sk_live_...`

#### 4.6.6 Per-Key Rate Limiting

Each API key has independent rate limits (default: 60/min, 1000/hr), separate from
the global per-IP rate limiting. Exceeding limits returns HTTP 429.

**Implementation:** `backend/domains/api_keys/`

---

## 5. Account Security

### 5.1 Account Lockout

| Parameter | Value |
|-----------|-------|
| Failed attempt threshold | 5 attempts |
| Lockout duration | 15 minutes |
| Lockout scope | Per account (not per IP) |
| Progressive lockout | After 3 consecutive lockouts, duration doubles |
| Admin unlock | Admins can manually unlock accounts |
| Lockout notification | Audit log entry + optional webhook |

### 5.2 Account Lifecycle (ADR-0021)

Accounts follow a defined lifecycle with validated state transitions:

| Status | Can Login | Reversible | Use Case |
|--------|-----------|-----------|----------|
| `invited` | No | → `active` | Pending password setup |
| `active` | Yes | → `suspended`, `deactivated` | Normal operation |
| `suspended` | No | → `active` | Temporary lock (policy violation) |
| `deactivated` | No | → `active` | Permanent disable (offboarding) |
| `deleted` | No | Terminal | Soft-delete (data retained for compliance) |

Suspending, deactivating, or deleting an account immediately revokes all sessions
and refresh tokens.

### 5.3 Session Management (ADR-0021)

Server-side session registry provides IdP-grade session control.

| Parameter | Value |
|-----------|-------|
| Session idle timeout | 30 days (configurable via `SESSION_INACTIVITY_TIMEOUT_DAYS`) |
| Absolute session lifetime | 30 days (configurable via `SESSION_MAX_LIFETIME_DAYS`) |
| Concurrent sessions | Allowed (no limit) |
| Session termination | Explicit logout revokes session + token family |
| Cross-device sessions | Each device maintains independent session |
| Device management | Users can list and revoke individual sessions |
| Admin session control | Admins can view and revoke any user's sessions |
| Password change | Revokes all sessions except the current device |
| Account disable | Revokes all sessions immediately |

Sessions are bound to refresh token families. Revoking a session also invalidates
the associated refresh token chain.

### 5.3 Rate Limiting

Rate limiting is applied per IP address using a sliding window algorithm.

| Endpoint Category | Rate Limit | Window |
|-------------------|-----------|--------|
| Authentication (`/auth/login`) | 10 requests | 1 minute |
| TOTP verification | 5 requests | 1 minute |
| User registration | 5 requests | 5 minutes |
| Token refresh | 30 requests | 1 minute |
| Password change | 5 requests | 5 minutes |
| OIDC/SAML SSO | 20 requests | 1 minute |
| Global API (per IP) | 100 requests | 1 minute |
| Global API (`/auth/login` strict) | 5 requests | 1 minute |
| API key (per key, configurable) | 60 req/min, 1000 req/hr | Sliding window |

Rate limit responses include headers:

```
X-RateLimit-Limit: <limit>
X-RateLimit-Remaining: <remaining>
X-RateLimit-Reset: <reset_timestamp>
```

Exceeding the rate limit returns HTTP 429 with a `Retry-After` header.

---

## 6. API Access Control

### 6.1 Authentication Middleware

All API routes pass through the authentication middleware stack defined in
`backend/middleware/auth.py`:

| Middleware | Function | Behavior |
|-----------|----------|----------|
| `get_current_user` | Extracts and validates JWT from `Authorization: Bearer <token>` header | Returns 401 if token invalid/expired |
| `require_role(role)` | Validates that the authenticated user has the required role or higher | Returns 403 if insufficient privileges |
| `get_auth_context` | Unified auth: detects API key (`sentora_sk_` prefix) or falls back to JWT | Returns `AuthContext` with auth_type, tenant, scopes |
| `require_scope(scope)` | Validates API key has required scope; skipped for JWT auth (governed by RBAC) | Returns 403 if scope missing |
| `require_user_auth()` | Rejects API key auth — JWT only | Used for key management endpoints |

### 6.2 Route Protection Categories

| Category | Auth Requirement | Example Routes |
|----------|-----------------|----------------|
| Public | None | `/health`, `/health/ready`, `/api/v1/deployment-info` |
| Authenticated (JWT or API key) | Valid JWT or API key | `/api/v1/dashboard/*`, `/api/v1/agents/*` |
| Role-restricted | JWT + specific role | `/api/v1/auth/users/*` (admin), `/api/v1/taxonomy/*` (admin for writes) |
| Scope-restricted | API key with required scope | `/api/v1/agents/*` requires `agents:read` scope for API keys |
| JWT-only (admin) | JWT required, API keys rejected | `/api/v1/api-keys/*` (management endpoints) |

### 6.3 CORS Policy

| Environment | Allowed Origins | Credentials |
|-------------|----------------|-------------|
| Development | `http://localhost:5003` (Vite dev server) | Allowed |
| Production | Configured domain only | Restricted |

Allowed methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`
Allowed headers: `Authorization`, `Content-Type`, `X-Request-ID`, `X-Tenant-ID`, `X-API-Key`

---

## 7. Infrastructure Access Control

### 7.1 MongoDB Access

| Control | Implementation |
|---------|---------------|
| Authentication | Username/password via connection string (`MONGODB_URL`) |
| Authorization | Application uses dedicated database user with minimal privileges |
| Network | Docker network isolation; no direct external access |
| Encryption | TLS for connections; encryption at rest (when configured) |

### 7.2 Container Security

| Control | Implementation |
|---------|---------------|
| Non-root execution | `apprunner` user (uid 1001) in `Dockerfile.backend` |
| Resource limits | 1 CPU, 1 GB RAM per container (`docker-compose.yml`) |
| Read-only filesystem | Application directories mounted read-only where possible |
| No privileged mode | Containers run without `--privileged` flag |

### 7.3 Environment Variable Security

| Control | Implementation |
|---------|---------------|
| Documentation | `.env.example` lists all variables with `[REQUIRED]` markers |
| Exclusion | `.gitignore` prevents `.env` files from being committed |
| Validation | Application validates required variables at startup; fails fast if missing |
| Rotation | JWT secrets and API tokens support rotation without downtime |

---

## 8. Access Review Process

### 8.1 Periodic Reviews

| Review Type | Frequency | Reviewer | Scope |
|-------------|-----------|----------|-------|
| User access review | Quarterly | Admin / Security team | All active accounts, role assignments |
| Service account review | Quarterly | Admin / Security team | API tokens, integration credentials |
| Admin privilege review | Monthly | Super admin | All admin and super_admin accounts |
| Dormant account review | Monthly | Automated + admin | Accounts inactive > 90 days |

### 8.2 Review Actions

For each account reviewed:

1. Verify the user still requires access
2. Verify the assigned role matches current job function
3. Verify 2FA is enabled (mandatory for admin+)
4. Check last login date (flag if > 90 days)
5. Review audit log for any anomalous access patterns
6. Document review outcome and any actions taken

### 8.3 Automated Controls

| Control | Trigger | Action |
|---------|---------|--------|
| Dormant account warning | 60 days inactive | Email notification to user and admin |
| Dormant account disable | 90 days inactive | Account disabled; requires admin reactivation |
| Password expiration | 90 days since last change | User prompted to change password at next login |
| Failed login alert | 3+ failed attempts | Audit log entry; admin notification if configured |

---

## 9. Access Control for SentinelOne Integration

| Aspect | Detail |
|--------|--------|
| Authentication | API token (`S1_API_TOKEN`) stored in environment variable |
| Authorization | Token should have minimum required S1 permissions (read-only for agents, apps, sites, groups) |
| Rate limiting | Token bucket algorithm prevents exceeding S1 API rate limits |
| Fail-fast | Sync refuses to start if token is missing or S1 URL is placeholder |
| Audit | All sync operations logged with start time, duration, record counts |

---

## 10. Audit Logging

All access control events are recorded in the audit log:

| Event | Logged Fields |
|-------|--------------|
| Login success | User ID, email, IP address, user agent, timestamp |
| Login failure | Attempted email, IP address, failure reason, timestamp |
| 2FA enrollment | User ID, timestamp |
| 2FA verification failure | User ID, IP address, timestamp |
| Token refresh | User ID, old token JTI, new token JTI, timestamp |
| Role change | Acting user, target user, old role, new role, timestamp |
| Account lockout | User ID, IP address, attempt count, lockout duration, timestamp |
| Account unlock | Acting admin, target user, timestamp |
| Password change | User ID, timestamp (password never logged) |
| Session termination | User ID, reason (logout/timeout/revocation), timestamp |

Audit logs are stored with hash-chain integrity (each entry includes hash of the
previous entry) and 90-day TTL via MongoDB TTL index.

---

## 11. Exception Process

Access control exceptions (e.g., temporary elevated privileges, emergency access)
must follow this process:

1. **Request:** Documented with business justification, scope, and duration
2. **Approval:** Requires approval from `super_admin` or designated security officer
3. **Implementation:** Time-bounded; automatic revocation at expiration
4. **Monitoring:** Enhanced audit logging during exception period
5. **Review:** Post-exception review of all actions taken during elevated access

All exceptions are recorded in the audit log with the approval chain.

---

## 12. Compliance Mapping

| Requirement | Framework | Control |
|-------------|-----------|---------|
| Logical access controls | SOC 2 CC6.1 | JWT auth + RBAC + MFA |
| Access credentials management | SOC 2 CC6.2 | bcrypt hashing, token rotation |
| Access restriction | SOC 2 CC6.3 | Role-based endpoint authorization |
| Privileged access management | ISO 27001 A.8.2 | super_admin/admin role separation |
| Secure authentication | ISO 27001 A.8.5 | Multi-factor, password complexity |
| Access control | ISO 27001 A.5.15 | This policy document |
| Identity management | ISO 27001 A.5.16 | User lifecycle management |

---

*This policy is reviewed semi-annually or when access control mechanisms change
significantly. All access control implementations reference this policy as the
authoritative source for requirements.*
