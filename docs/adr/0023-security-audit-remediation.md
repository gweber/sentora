# ADR-0023: Security Audit Remediation (March 2026)

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-03-16 |
| **Deciders** | Engineering |
| **Extends** | [ADR-0018: JWT Authentication with RBAC](0018-jwt-authentication-with-rbac.md), [ADR-0021: Enterprise Auth Hardening](0021-enterprise-auth-hardening.md) |

## Context

A comprehensive codebase audit identified 50 findings across security, correctness,
performance, and infrastructure. The findings ranged from critical tenant isolation
bypasses and weak key derivation to moderate correctness issues in distributed locking
and compliance scoring. Two rounds of remediation were performed to address all findings
systematically.

### Scope

- **Round 1:** 25 findings covering critical/high security issues, correctness bugs,
  and infrastructure hardening.
- **Round 2:** 25 findings covering remaining security gaps, CQRS compliance,
  CI/CD reliability, and edge-case correctness issues.

## Decision

The following key architectural changes were made to remediate the audit findings:

1. **HKDF-SHA256 for field encryption key derivation.** Replaced unsalted SHA-256
   with HKDF-SHA256 and introduced a dedicated `FIELD_ENCRYPTION_KEY` environment
   variable, separating field encryption from JWT signing.

2. **PKCE added to OIDC authorization flow.** The OIDC login now generates a
   code verifier and includes `code_challenge` / `code_challenge_method` parameters
   per RFC 7636, preventing authorization code interception.

3. **Tenant isolation via JWT `tenant_id` claim.** Tenant context is now derived
   from the authenticated JWT token rather than a client-supplied header, closing
   the tenant isolation bypass.

4. **Atomic account lockout via `find_one_and_update`.** Login lockout increments
   and threshold checks are performed in a single atomic MongoDB operation,
   preventing concurrent bypass of the lockout mechanism.

5. **Compliance violation capping at 10,000.** All compliance checks cap their
   violation count at `MAX_VIOLATIONS = 10_000` to prevent unbounded memory
   growth, with the count computed before the cap is applied.

6. **DNS rebinding protection via `resolve_and_validate`.** Webhook delivery and
   SSRF validation now resolve hostnames and validate the resulting IP address
   before connecting, blocking DNS rebinding and TOCTOU attacks.

7. **`defusedxml` for XML parsing.** The Chocolatey adapter replaced
   `xml.etree.ElementTree` with `defusedxml` to prevent XML External Entity (XXE)
   and billion-laughs attacks.

8. **Non-root nginx container.** The frontend nginx container now runs as a
   non-root user on port 8080, reducing the blast radius of a container escape.

9. **MongoDB authentication in Docker Compose.** All MongoDB containers in
   `docker-compose.yml` now require authentication by default, with `MONGO_URI`
   including `authSource=admin`.

10. **Auth router CQRS refactoring.** All direct database operations were extracted
    from the auth router into the service layer, bringing the auth domain into
    compliance with the project's CQRS architecture.

## Consequences

### Positive

- **Security hardened.** All 50 audit findings addressed — critical tenant isolation,
  key derivation, and SSRF issues eliminated.
- **CQRS compliance.** The auth router now follows the same service-layer pattern
  as other domains, improving testability and separation of concerns.
- **Defence in depth.** Multiple layers (PKCE, DNS validation, atomic operations,
  non-root containers) reduce the impact of any single control failing.
- **CI/CD reliability.** E2E pipeline uses health polling, correct Node version,
  and `--legacy-peer-deps`, reducing false-negative test failures.

### Negative

- **`FIELD_ENCRYPTION_KEY` must be set for production.** Existing deployments
  need to generate and configure a new secret. A fallback to `JWT_SECRET_KEY`
  is provided for development but logs a warning.
- **Migration required for encrypted fields.** Data encrypted with the old
  unsalted SHA-256 derivation must be re-encrypted with the new HKDF key.

### Risks

- **Key rotation coordination.** Deploying the new `FIELD_ENCRYPTION_KEY` requires
  a coordinated rollout — the new key must be available before any service
  attempts to decrypt data encrypted with it.
- **Behavioural change in lockout.** The atomic lockout may surface latent issues
  in environments with high-frequency brute-force attempts due to stricter
  enforcement of the threshold.

## Alternatives Considered

1. **Incremental patching without architectural changes.** Rejected — several
   findings (tenant isolation, CQRS violations) required structural refactoring
   that could not be addressed by point fixes alone.

2. **Encrypting tenant ID in headers instead of JWT claims.** Rejected — this
   would still rely on client-supplied data. Deriving tenant context from the
   JWT is the only approach that ties tenant identity to the authentication proof.

3. **Application-level DNS caching instead of `resolve_and_validate`.** Rejected —
   caching DNS results introduces stale-record risks and does not prevent
   rebinding attacks where the attacker controls the authoritative DNS server.
