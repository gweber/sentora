# Security Audit Remediation Report — March 2026

## Overview

This document details the security remediation work performed in March 2026 as a
follow-up to the initial audit (see [audit-2026-03.md](audit-2026-03.md) and
[ADR-0024](../adr/0024-security-audit-remediation-2026-03.md)).

## Findings Summary by Severity

| Severity | Count | Status |
|---|---|---|
| Critical | 3 | All fixed |
| High | 5 | All fixed |
| Medium | 2 | All fixed |
| **Total** | **10** | **All fixed** |

## Critical and High Findings

| # | Severity | Finding | Fix | Affected Component |
|---|---|---|---|---|
| 1 | Critical | DNS rebinding bypasses SSRF validation in webhook delivery | Pin resolved IP for duration of HTTP request; eliminate TOCTOU window | `webhooks/delivery.py`, `utils/ssrf.py` |
| 2 | Critical | Tenant isolation bypass at data layer — queries accept client-supplied tenant ID | Inject `tenant_id` from JWT claim into all repository queries; add middleware guard | Tenant middleware, all repository modules |
| 3 | Critical | Privilege escalation via self-role-elevation in role assignment | Block role assignment above caller's own role; reject header-based `super_admin` overrides | `auth/service.py`, RBAC middleware |
| 4 | High | Audit hash chain race condition under concurrent workers | Acquire MongoDB-backed distributed lock before reading previous hash and writing new entry | `audit/service.py`, `utils/distributed_lock.py` |
| 5 | High | OIDC/SAML state documents accumulate indefinitely | Add TTL index (`expires_at`, 10 min) on state collections | `auth/oidc.py`, `auth/saml.py`, MongoDB indexes |
| 6 | High | JWT tokens accepted with missing or mismatched `aud`/`iss` claims | Strictly validate `aud` and `iss` against configured values; reject non-conforming tokens | `auth/jwt.py` |
| 7 | High | TOTP secrets stored in plaintext in user documents | Encrypt TOTP secrets at rest using HKDF-SHA256 derived field encryption key | `auth/totp.py`, `crypto.py` |
| 8 | High | Backup recovery codes stored in plaintext | Hash backup codes with bcrypt; mark used codes as consumed with timestamp | `auth/backup_codes.py` |
| 9 | Medium | Rate limiter bypassable via path variation (`//`, trailing `/`, percent encoding) | Normalize paths before rate limit bucket assignment | `middleware/rate_limiter.py` |
| 10 | Medium | API key checkpoint responses leak raw key material after creation | Return plaintext key only on initial creation; strip from all subsequent responses | `auth/api_keys.py` |

## Verification Steps

### DNS Rebinding SSRF Fix
1. Configure a webhook pointing to an attacker-controlled domain that resolves to a public IP on first lookup and `127.0.0.1` on second lookup.
2. Trigger webhook delivery.
3. Verify the request is sent to the originally resolved public IP, not `127.0.0.1`.
4. Verify that if the original resolution returns an internal IP, delivery is blocked with a 400 error.

### Tenant Isolation
1. Authenticate as a user in tenant A.
2. Attempt to query resources belonging to tenant B by manipulating request parameters.
3. Verify 403 Forbidden is returned.
4. Verify audit log records the cross-tenant access attempt.

### Privilege Escalation Guards
1. Authenticate as an `analyst` user.
2. Attempt to assign `admin` role to self or another user.
3. Verify 403 Forbidden is returned.
4. Authenticate as `admin` in SaaS mode; attempt platform-level operations.
5. Verify `super_admin` is required and the request is rejected.

### Audit Chain Distributed Lock
1. Deploy two or more backend workers.
2. Trigger concurrent operations that produce audit entries (e.g., bulk user creation).
3. Verify the audit hash chain is linear (each entry's `prev_hash` matches the preceding entry's hash).
4. Verify no fork or gap exists in the chain.

### TTL Indexes for OIDC/SAML State
1. Initiate an OIDC login but do not complete the callback.
2. Verify the state document is created with an `expires_at` field.
3. Wait 10+ minutes (plus MongoDB TTL monitor interval).
4. Verify the state document has been automatically deleted.

### JWT Verification Hardening
1. Generate a valid JWT with an incorrect `aud` claim.
2. Send an authenticated request using this token.
3. Verify 401 Unauthorized is returned with an appropriate error message.
4. Repeat with a missing `iss` claim; verify rejection.

### TOTP Secret Encryption
1. Enable TOTP for a user account.
2. Inspect the user document in MongoDB directly.
3. Verify the `totp_secret` field contains an encrypted value (not the raw base32 secret).
4. Verify TOTP verification still succeeds with the correct code.

### Backup Credential Protection
1. Generate backup codes for a user.
2. Inspect the user document in MongoDB.
3. Verify codes are stored as bcrypt hashes, not plaintext.
4. Verify a backup code can be used for recovery exactly once.
5. Verify used codes are marked as consumed (not deleted).

### Rate Limit Path Normalization
1. Send requests to `/api/v1/login` until the rate limit is reached.
2. Attempt to bypass by sending requests to `/api//v1/login` or `/api/v1/login/`.
3. Verify the rate limit still applies (429 Too Many Requests).

### API Key Credential Stripping
1. Create a new API key; verify the plaintext key is returned in the response.
2. Retrieve the key via GET endpoint; verify only the prefix and metadata are returned.
3. Rotate the key; verify the new plaintext is returned once, then stripped on subsequent GETs.
