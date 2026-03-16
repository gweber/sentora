# ADR-0021: Enterprise Auth Hardening

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-03-15 |
| **Deciders** | Engineering |
| **Extends** | [ADR-0018: JWT Authentication with RBAC](0018-jwt-authentication-with-rbac.md) |

## Context

ADR-0018 established JWT-based authentication with RBAC, refresh token rotation,
TOTP 2FA, and enterprise SSO (OIDC/SAML). While this provided a solid foundation,
several gaps remained before the auth system could be considered IdP-grade:

- **No server-side session tracking.** Stateless JWT-only auth cannot immediately
  invalidate individual sessions. Revoking a user requires waiting for either the
  JWT to expire (15 min) or the revocation cache to refresh (~30s). There is no
  device management ("show me where I'm logged in").

- **Binary account status.** The `disabled: bool` field cannot distinguish between
  temporary suspension, permanent deactivation, pending invitations, and soft
  deletion — all of which have different business semantics.

- **No password history.** Users can reuse the same password on every change,
  defeating the purpose of password rotation policies.

- **Missing JWT claims.** Access tokens lack standard claims (`aud`, `iss`, `jti`)
  that IdPs use for token validation, scoping, and revocation lookup.

- **No account lockout.** While mentioned in ADR-0018's description, account lockout
  after consecutive failed login attempts was not implemented.

- **Incomplete audit trail.** Several auth events (TOTP verification failures,
  password changes, session revocations, new device detections) were not logged.

- **No breach checking.** Passwords were not validated against known breach databases.

## Decision

Extend the authentication system with IdP-grade features while maintaining the
stateless JWT architecture for performance.

### Server-Side Session Registry

Each login creates a `Session` document in MongoDB. The session ID (`sid`) is
embedded as a JWT claim in access tokens. An in-memory revocation cache (similar
to the user revocation cache) is checked on every authenticated request, enabling
immediate session invalidation without database calls.

**Key design choices:**
- Sessions are bound to refresh token families (1:1 mapping)
- Session revocation also revokes the associated refresh token family
- Password change revokes all sessions except the current one
- Account disable/suspend revokes all sessions immediately
- Sessions auto-expire via MongoDB TTL index after their absolute lifetime

**Endpoints added:**
- `GET /api/v1/auth/sessions` — user's active sessions (device list)
- `DELETE /api/v1/auth/sessions/{id}` — revoke a specific session
- `DELETE /api/v1/auth/sessions` — revoke all other sessions
- `GET /api/v1/auth/admin/sessions?username=X` — admin: user's sessions
- `DELETE /api/v1/auth/admin/sessions?username=X` — admin: revoke all

### Account Lifecycle

Replaced the binary `disabled: bool` with a `status` field using the `AccountStatus`
enum:

| Status | Can Login | Visible | Data Retained |
|---|---|---|---|
| `invited` | No (pending password setup) | Yes | Minimal |
| `active` | Yes | Yes | Full |
| `suspended` | No (temporary) | Yes | Full |
| `deactivated` | No (permanent) | Yes (greyed) | Full |
| `deleted` | No | No (soft-delete) | Retained for compliance |

State transitions are validated — e.g., `deleted` is terminal.
The `disabled` field is kept in sync for backward compatibility.

### Password Policy Engine

- **Password History:** Last N password hashes stored in the user document.
  New passwords are checked against history during changes.
- **Breach Checking:** Optional HaveIBeenPwned k-Anonymity API integration.
  Only the first 5 chars of the SHA-1 hash are sent — the password never
  leaves the server.
- **Configurable Policy:** All parameters (min length, complexity, history count,
  breach check) are environment-variable-configurable.
- **Change Password Endpoint:** `POST /api/v1/auth/change-password` validates
  current password, checks policy, and revokes other sessions on success.

### Token Hardening

- **`aud` claim:** Set to `sentora-api`, validated on decode
- **`iss` claim:** Set to `sentora`, validated on decode
- **`jti` claim:** Unique per token, enables revocation lookup
- **`sid` claim:** Session ID for server-side session validation
- **Backward compatibility:** Tokens without `aud`/`iss` are accepted with
  a fallback decode path (no validation of these claims) to prevent lockout
  during rollout.

### Account Lockout

After `ACCOUNT_LOCKOUT_THRESHOLD` (default: 5) consecutive failed login attempts,
the account is locked for `ACCOUNT_LOCKOUT_DURATION_MINUTES` (default: 15 minutes).
Failed attempt counter resets on successful login.

### Login Anomaly Detection

- **New Device Detection:** User-Agent strings are tracked per user. First login
  from an unknown User-Agent triggers an audit event.
- **Audit-Event-Based:** All anomalies are logged as audit events, not hard
  blocks. This prevents false-positive lockouts for MSPs with many technicians
  on the same IP or using VPNs.

### Comprehensive Auth Audit Trail

All auth events are now logged with structured details (IP, User-Agent, session ID):

| Event | Action | Details |
|---|---|---|
| Login success | `auth.login` | IP, User-Agent |
| Login failure | `auth.login_failed` | IP, username |
| TOTP failure | `auth.totp_verify_failed` | IP, username |
| Token refresh failure | `auth.token_refresh_failed` | IP |
| Password changed | `auth.password_changed` | username |
| Password change failed | `auth.password_change_failed` | username |
| New device detected | `auth.new_device_detected` | IP, User-Agent |
| Session revoked | `auth.session_revoked` | session_id |
| All sessions revoked | `auth.sessions_revoked_all` | count |
| Admin revoked sessions | `auth.admin_sessions_revoked` | target, count |
| Account status changed | `auth.user_{status}` | old/new status, reason |
| Logout all | `auth.logout_all` | username |

## Consequences

### Positive

- **Immediate session invalidation.** Revoked sessions are rejected on the next
  API call (within ~30s cache refresh), not at JWT expiry.
- **Device management.** Users can see and manage their active sessions, matching
  the UX of Google Account, GitHub, and enterprise IdPs.
- **Compliance alignment.** Password history, breach checking, and account lifecycle
  states satisfy NIST SP 800-63B, SOC 2 CC6.2, and ISO 27001 A.8.3/A.8.5.
- **Defense in depth.** Multiple layers of protection: JWT expiry + session
  revocation + user revocation + account lockout + rate limiting.

### Negative

- **Session cache memory.** The in-memory revoked-session cache grows with the
  number of recently revoked sessions (bounded to 24h window). For typical
  deployments this is negligible (<1 KB).
- **Database writes on login.** Each login now creates a session document
  (~500 bytes). With few admin users and 150k agents (not interactive users),
  this is minimal overhead.
- **Password breach check latency.** The HaveIBeenPwned API call adds ~200ms
  to registration and password change. This is acceptable for infrequent
  operations and can be disabled via configuration.

### Risks

- **HaveIBeenPwned API availability.** If the API is unreachable, the breach
  check fails open (non-blocking). This is intentional — availability of the
  login flow takes priority over breach checking.
- **Session cache staleness.** A 30-second window exists where a just-revoked
  session can still be used. This matches the existing user revocation cache
  behavior and is acceptable for the threat model.

## Alternatives Considered

1. **Redis-backed session store.** Rejected — adds an infrastructure dependency
   that conflicts with Sentora's single-binary deployment simplicity. MongoDB
   with in-memory caching achieves the same performance profile.

2. **JWT blacklist (token-level revocation).** Rejected — would require storing
   every issued token ID. Session-level revocation is coarser but sufficient
   and far more storage-efficient.

3. **Argon2 instead of bcrypt.** Considered for future migration. Bcrypt remains
   the current choice for compatibility with existing password hashes. Argon2
   would be reconsidered if GPU-accelerated attacks become a concern.
