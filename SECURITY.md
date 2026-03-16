# Security Policy

## Reporting a Vulnerability

**Please do not file public GitHub issues for security vulnerabilities.**

If you discover a security vulnerability in Sentora, please report it by email to:

**GitHub Security Advisories** — [Report a vulnerability](../../security/advisories/new)

Alternatively, email: **webersheim@gmail.com** with subject line `[SECURITY] Sentora`.

### What to Include

Please include as much of the following as possible so we can reproduce and assess the issue quickly:

- A description of the vulnerability and its potential impact.
- Steps to reproduce, including any relevant configuration, payloads, or request/response examples.
- The version or commit SHA you tested against.
- Whether you believe a proof-of-concept exploit is feasible.

### Our Commitments

| Milestone | Timeline |
|---|---|
| Acknowledgement of receipt | Within 48 hours of your report |
| Initial assessment (severity, affected versions) | Within 7 calendar days |
| Status update | Every 7 days thereafter until resolved |
| Patch or mitigation | Target within 90 days for Critical/High; 180 days for Medium/Low |
| Public disclosure | Coordinated with you after a patch is available |

We follow a coordinated disclosure model. We will not take legal action against researchers who report vulnerabilities in good faith and follow this policy.

---

## Supported Versions

| Version | Supported |
|---|---|
| Unreleased (`main` branch) | Yes — active development |
| 1.3.x | Yes — current release |
| < 1.3.0 | Not supported |

We encourage all users to run the latest release or the `main` branch.

---

## Sensitive Data Classification

The following categories of data are processed or stored by Sentora. Understanding their sensitivity helps prioritise vulnerability reports.

| Data Category | Sensitivity | Location | Notes |
|---|---|---|---|
| **SentinelOne API token** | Critical | `.env` file / environment variable only | Never stored in MongoDB. Never logged. Must not appear in any HTTP response body or log output. |
| **Agent inventory data** (hostnames, IP addresses, OS versions, usernames) | Internal | MongoDB `agents` collection | Not intended for public exposure. Breach could reveal network topology. |
| **Application names and versions** | Internal | MongoDB `applications` and `classification_results` collections | Reveals installed software, which is operationally sensitive in security contexts. |
| **Classification verdicts and fingerprint definitions** | Low | MongoDB `fingerprints`, `classification_results` collections | Reveals detection logic. Potentially useful to an attacker seeking to evade classification, but not directly exploitable. |
| **Taxonomy structure** | Low | MongoDB `taxonomy_nodes` collection | Organisational metadata only. |

---

## Security Design

### SentinelOne API Token Handling

The S1 API token is the most sensitive credential in the system. The following controls are in place:

- The token is loaded exclusively from the `S1_API_TOKEN` environment variable at startup. It is never written to any persistent store.
- The token is never serialised into any API response, log message, or database document.
- The backend uses the token only to make outbound HTTPS requests to the SentinelOne Management API. The token is sent in the `Authorization` header of those requests, not in query strings or request bodies.
- Loguru is configured to redact the token value if it appears in log output (belt-and-suspenders guard against accidental inclusion in exception traces).

### Network Model

```
Internet (SentinelOne API)
        |
        | HTTPS (outbound only, initiated by backend)
        |
[Backend — port 5002] <──── [Frontend — port 5003]
        |
[MongoDB — port 27017, internal only]
```

- MongoDB is bound to the internal Docker network only. It is not exposed to the host network or the internet.
- The SentinelOne API is contacted outbound over HTTPS. No inbound connections from SentinelOne are required.
- The frontend communicates with the backend over HTTP on the Docker network (or localhost in dev). TLS termination in production should be handled by a reverse proxy (nginx, Caddy, etc.) placed in front of both services.

### Input Validation

- All API request bodies are validated by Pydantic v2 models with strict types. Requests that do not conform to the schema are rejected with HTTP 422 before reaching service or repository code.
- MongoDB queries use Motor's parameter binding. Raw user-supplied strings are never interpolated into query documents.
- Regex patterns supplied in fingerprint marker definitions are compiled with `re.compile()` and any `re.error` is caught and returned as a 400 Bad Request, preventing regex injection or catastrophic backtracking from reaching the classification engine.
- File paths are not accepted as user input anywhere in the application.

### Authentication & Authorisation

Sentora includes built-in authentication and role-based access control:

- **JWT access tokens** (15 min default) with **refresh token rotation** (7 days).
- **Three roles**: `admin`, `analyst`, `viewer` — enforced via RBAC middleware.
- **Optional TOTP 2FA** per user.
- **Family-based token revocation** detects stolen refresh tokens and invalidates the entire token family.
- **API keys for external integrations** — tenant-scoped, SHA-256-hashed (plaintext never stored), with granular scopes and per-key rate limiting. Key format (`sentora_sk_live_`) is detectable by GitHub, GitGuardian, and truffleHog secret scanners. Management restricted to JWT admin users — API keys cannot create/modify/revoke other keys.

All existing API routes use `OptionalAuth` by default, meaning they remain accessible without a token unless explicitly protected. To enforce authentication on all routes, configure role requirements per endpoint.

**Recommended production hardening:**

1. **Set `JWT_SECRET_KEY`** in your `.env` — if left empty, a random key is generated on each startup (tokens will not survive restarts).
2. **Deploy behind a reverse proxy** (nginx, Caddy) with TLS termination.
3. **Do not expose port 5002 directly to the internet** without TLS.

---

### Library Ingestion Security

The fingerprint library ingests data from external public APIs (NVD, MITRE, Chocolatey, Homebrew). The following controls are in place:

- **Input validation**: All ingested data passes through Pydantic models before storage. Patterns, names, and descriptions are validated for type and length.
- **Pattern sanitization**: Glob patterns generated from CPE URIs and package names are constructed programmatically — user-supplied regex metacharacters are not passed through. Patterns use only `*` and `?` wildcards.
- **Source provenance**: Every library entry records its `source` (adapter name) and `upstream_id` (external identifier). Community-contributed entries are tagged as `source="community"` for separate review.
- **Access control**: Only `admin` role users can trigger ingestion, manage sources, or publish/deprecate library entries. `analyst` users can create entries and manage subscriptions. `viewer` users have read-only access.
- **No outbound credential exposure**: Ingestion adapters use public APIs only. No Sentora credentials are sent to external services.
- **Rate limiting**: The NIST CPE adapter enforces NVD-compliant rate limiting (6s without API key, 0.6s with key) to prevent IP bans.
- **Subscription isolation**: Library markers are copied into group fingerprints at subscribe time. Modifying or deleting a library entry does not retroactively alter existing group fingerprints — only explicit re-sync propagates changes.

---

## Known Limitations

- **In-memory rate limiting.** The inbound API rate limiter (100 req/min per IP, configurable via `RATE_LIMIT_PER_MINUTE`) uses in-memory sliding windows. In a multi-worker deployment, each worker tracks limits independently. For shared rate limiting across workers, a Redis-backed implementation is recommended. Path normalization is applied before bucket assignment to prevent bypass via path variation.
- **OIDC token validation.** ID tokens are validated against the provider's JWKS with a 1-hour cache. A key rotation at the IdP during this window could cause transient validation failures.
- **Audit chain distributed lock.** Under high-throughput audit scenarios, the MongoDB-backed distributed lock may become a bottleneck. Monitor lock wait times in production; batching audit entries is a future optimization.
- **TOTP secret migration.** Deployments upgrading from versions prior to this remediation must run the TOTP secret encryption migration during a maintenance window. A migration script is provided.
