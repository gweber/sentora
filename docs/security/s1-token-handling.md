# SentinelOne API Token Handling

The SentinelOne API token is the most sensitive credential in Sentora. This document describes precisely how the token enters the system, how it is stored, how it is used, and what to do if it is compromised.

---

## How the Token Enters the System

The token is supplied exclusively via the `S1_API_TOKEN` environment variable. There is no UI input, no database field, and no API endpoint for setting or updating the token at runtime.

At startup, `pydantic-settings` reads `S1_API_TOKEN` from the process environment (or a `.env` file in the repository root, if present). The value is stored as an attribute on the `Settings` Pydantic model:

```python
s1_api_token: str = Field(default="")
```

The `Settings` instance is cached by `@lru_cache` and shared across the process lifetime. No copy of the token string is made outside of the `Settings` instance and the HTTP client that uses it (see below).

**Accepted input paths:**

| Path | Supported | Notes |
|---|---|---|
| `S1_API_TOKEN` environment variable | Yes | Primary method for all deployments |
| `.env` file at repository root | Yes | Loaded automatically by `pydantic-settings` in development. Must not be committed to version control. |
| Docker Compose `env_file` directive | Yes | `docker-compose.yml` uses `env_file: .env` |
| Docker Compose `environment` block | Yes | Can override the `.env` value per-service |
| API request body | No | No endpoint accepts a token |
| Database | No | The token is never written to MongoDB |
| Frontend | No | The frontend never handles or stores the token |

---

## How the Token is Stored

The token is held **in memory only**, as a string attribute on the `Settings` singleton. It is never:

- Written to MongoDB or any other database
- Written to disk (log files, temp files, crash dumps)
- Cached in Redis or any external store
- Included in any API response body
- Serialized into any file

The `Settings.model_dump()` method, if ever called (e.g. for health check endpoints or debug output), must not expose the token. To prevent accidental serialization, the field can be marked with Pydantic's `exclude` or overridden in a `__repr__` method. Any endpoint that returns configuration state must explicitly exclude `s1_api_token` from its response.

---

## How the Token is Used

The token is used exclusively to authenticate outbound HTTP requests to the SentinelOne Management API. It is placed in the `Authorization` header as a bearer token in S1's custom scheme:

```
Authorization: ApiToken <token_value>
```

The HTTP client (built on `httpx`) constructs this header immediately before each request. The header value is not stored separately from the `Settings` instance.

**Scopes accessed by Sentora:**

Sentora calls three SentinelOne API endpoints during a sync. The token must have read-only access to:

| S1 API Endpoint | Purpose | Minimum Permission |
|---|---|---|
| `GET /web/api/v2.1/groups` | Fetch agent group list | View Groups |
| `GET /web/api/v2.1/agents` | Fetch agent inventory (paginated) | View Endpoints |
| `GET /web/api/v2.1/agents/applications` | Fetch installed application list per agent | View Endpoints, View Applications |

Sentora **never** calls any S1 write endpoint. A read-only API token is sufficient and strongly recommended to limit blast radius if the token is compromised.

In the SentinelOne Management Console, create a service user with the **Viewer** role scoped to the relevant sites. Do not use an admin or full-access token.

---

## How the Token is Excluded from Logs

The request logging middleware (`middleware/request_logging.py`) logs:

- HTTP method
- Request path
- Response status code
- Response time in milliseconds
- Correlation ID (`X-Request-ID`)

It does **not** log:

- Request headers (including `Authorization`)
- Request bodies
- Response bodies

The S1 API client does not log the `Authorization` header. The `loguru` logger is configured for structured JSON output to stdout; no logger call anywhere in the application includes the token string.

**Verification:** Search the codebase for any reference to `s1_api_token` and confirm that none of those references pass the value to a logger:

```bash
grep -rn "s1_api_token" backend/
```

As of the current release, the only references are in `config.py` (field definition) and the S1 HTTP client (header construction). Neither passes the value to a logger.

---

## Required S1 API Permissions

To follow the principle of least privilege, create a dedicated service user in SentinelOne with the following minimum permissions:

| Permission | Scope | Reason |
|---|---|---|
| View Endpoints | Sites in scope | Required to list agents |
| View Applications | Sites in scope | Required to list installed applications per agent |
| View Groups | Account or sites in scope | Required to list agent groups |

**Steps to create the token in SentinelOne:**

1. Log in to your SentinelOne Management Console.
2. Navigate to **Settings → Users** and create a new Service User.
3. Assign the **Viewer** role, scoped to the relevant sites (not account-wide unless your fleet spans multiple sites and you want to sync all of them).
4. Generate an API token for the service user.
5. Copy the token and set it as `S1_API_TOKEN` in your `.env` file or secrets manager.
6. Test the connection with `curl`:
   ```bash
   curl -s -H "Authorization: ApiToken YOUR_TOKEN" \
     "https://your-console.sentinelone.net/web/api/v2.1/system/status"
   ```

---

## Token Rotation Procedure

Rotate the token proactively (e.g. quarterly or whenever team membership changes) or immediately if compromise is suspected.

### Planned Rotation

1. In the SentinelOne Management Console, generate a new API token for the Sentora service user (or create a new service user and token).
2. Update `S1_API_TOKEN` in your secrets manager or `.env` file with the new token value.
3. Restart the Sentora backend to reload the `Settings` singleton:
   ```bash
   docker compose restart backend
   ```
4. Verify connectivity by triggering a sync: `POST /api/v1/sync/trigger` and confirming the sync progresses past the groups phase.
5. Revoke the old token in the SentinelOne Management Console.

**Zero-downtime rotation** is not currently possible because the token is loaded once at startup. A backend restart is required. The restart takes under 10 seconds and does not affect stored classification results or fingerprints.

### Emergency Rotation (Suspected Compromise)

1. **Immediately revoke the compromised token** in the SentinelOne Management Console. Do not wait.
2. Generate a replacement token (see planned rotation steps 1–3 above).
3. Review SentinelOne audit logs for any API calls made using the compromised token from unexpected IP addresses.
4. Review Sentora's backend logs for any unusual sync activity or API errors during the window when the token may have been in attacker hands.
5. If the token was found in a committed `.env` file, rotate the credential, remove the file from git history using `git filter-repo`, and notify affected parties.

---

## What Happens if the Token is Compromised

If an attacker obtains the `S1_API_TOKEN`, they can:

- **Call SentinelOne read endpoints** as the service user: list agents, applications, groups, and other inventory data that the token has permission to read.
- **They cannot** modify Sentora data directly (they would need access to the Sentora API separately).
- **They cannot** call SentinelOne write endpoints if the token was scoped to a read-only Viewer role.

The scope of damage is bounded by the permissions assigned to the service user. This is the primary reason to use a read-only, site-scoped Viewer token rather than an admin token.

Revoke the compromised token in the SentinelOne Management Console as the first and most urgent action.
