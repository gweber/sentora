# Environment Variable Reference

All Sentora configuration is supplied via environment variables. In local development these can be placed in a `.env` file at the repository root; the backend reads it automatically via `pydantic-settings`. In Docker deployments the `env_file` directive in `docker-compose.yml` loads the same file.

---

## Variable Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `S1_BASE_URL` | Yes | `https://example.sentinelone.net/web/api/v2.1` | Base URL of the SentinelOne Management API. Must include the full path up to and including the API version prefix (`/web/api/v2.1`). Do not include a trailing slash — see note below. |
| `S1_API_TOKEN` | Yes | _(empty)_ | SentinelOne API bearer token. Used in the `Authorization: ApiToken <token>` header on every S1 API call. Never logged, never returned in API responses. See the security note below. |
| `S1_RATE_LIMIT_PER_MINUTE` | No | `100` | Maximum number of S1 API requests per minute. Enforced by a token-bucket rate limiter inside the sync pipeline. Reduce this value if your S1 console enforces a lower limit on your API token's scope. Minimum: `1`. |
| `MONGO_URI` | No | `mongodb://localhost:27017` | MongoDB connection URI. In Docker Compose deployments this is automatically overridden to `mongodb://mongodb:27017` by the `environment` block in `docker-compose.yml`. For authenticated production deployments see the production recommendations below. |
| `MONGO_DB` | No | `sentora` | Name of the MongoDB database. All collections are created within this database. |
| `MONGO_DB_TEST` | No | `sentora_test` | Name of the MongoDB database used by the test suite (`conftest.py`). Must be different from `MONGO_DB` to prevent tests from touching production data. |
| `APP_PORT` | No | `5002` | TCP port the Uvicorn server listens on. Exposed by the Docker container. Must be in the range 1–65535. |
| `APP_ENV` | No | `development` | Runtime environment. Accepted values: `development`, `staging`, `production`. Controls debug mode and log verbosity. In `development`: Swagger UI (`/api/docs`) and ReDoc (`/api/redoc`) are enabled, and CORS is opened for `http://localhost:5003`. In `staging` and `production` these are disabled. |
| `LOG_LEVEL` | No | `INFO` | Python logging level. Accepted values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Loguru outputs structured JSON to stdout. Use `DEBUG` only in development — it produces significant volume in production. |
| `CLASSIFICATION_THRESHOLD` | No | `0.6` | Minimum normalized score (0.0–1.0) for a fingerprint match to produce a `correct` verdict. Agents whose best fingerprint score is below this threshold receive `unclassifiable`. Increasing this value makes classification stricter; decreasing it allows lower-confidence matches. |
| `AMBIGUITY_GAP` | No | `0.15` | Maximum gap between the top two fingerprint scores before a result is classified as `ambiguous` rather than `correct` or `misclassified`. If the best score is 0.80 and the second-best is 0.68, the gap is 0.12 which is below the default 0.15 threshold — the result is `ambiguous`. |
| `UNIVERSAL_APP_THRESHOLD` | No | `0.6` | Fraction of agents (0.0–1.0) an installed application must appear in before it is considered "universal" and excluded from fingerprint scoring by default. Applications present on more than 60% of all agents (browsers, runtimes, system components) would otherwise inflate scores uniformly. |
| `SUGGESTION_SCORE_THRESHOLD` | No | `0.5` | Minimum TF-IDF relevance score for a taxonomy entry to appear in fingerprint marker suggestions. Increasing this value raises the bar for suggestions, producing fewer but more precise results. |

---

## Deployment Mode

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEPLOYMENT_MODE` | No | `onprem` | Deployment mode. `onprem` for single-tenant on-premises installations; `saas` for multi-tenant SaaS deployments. See below for behavioral differences. |
| `MULTI_TENANCY_ENABLED` | No | `false` | Enable database-per-tenant isolation. Only relevant when `DEPLOYMENT_MODE=saas`. |
| `TENANT_ISOLATION` | No | `database` | Tenant isolation strategy. Currently only `database` is supported. |
| `MASTER_DB_NAME` | No | `sentora_master` | Name of the master database for the tenant registry and shared data (library entries, ingestion runs). |

### On-Prem vs SaaS Behavior

| Feature | On-Prem | SaaS |
|---|---|---|
| First registered user role | `admin` | `super_admin` |
| Top-level role | `admin` | `super_admin` |
| Library source management | `admin` | `super_admin` |
| Tenant management | Hidden (not available) | `super_admin` only |
| Tenant switcher (UI) | Hidden | Visible to `super_admin` |
| Multi-tenancy | Disabled (single database) | Database-per-tenant isolation |
| Platform guide (Getting Started) | Hidden | Visible to `super_admin` |

**On-Prem mode** is designed for organizations deploying a single instance on their own infrastructure. The `admin` role is the highest privilege level and has full access to all features including library source management.

**SaaS mode** introduces `super_admin` as a platform operator role that manages tenants, library sources, and cross-tenant configuration. Each tenant gets its own isolated database. Tenant administrators (`admin` role) manage their own users, fingerprints, and classifications.

---

## Authentication & Session Management

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | **Yes** (production) | _(auto-generated)_ | Secret key for JWT signing. Auto-generated in development; **must** be set in production. Generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm. Accepted: `HS256`, `HS384`, `HS512`. |
| `JWT_ACCESS_EXPIRE_MINUTES` | No | `15` | Access token lifetime in minutes. Shorter is more secure; longer reduces refresh frequency. |
| `JWT_REFRESH_EXPIRE_DAYS` | No | `7` | Refresh token lifetime in days. |
| `SESSION_MAX_LIFETIME_DAYS` | No | `30` | Maximum absolute session lifetime in days. Sessions expire after this period regardless of activity. |
| `SESSION_INACTIVITY_TIMEOUT_DAYS` | No | `30` | Session expires after this many days of inactivity. |
| `ACCOUNT_LOCKOUT_THRESHOLD` | No | `5` | Failed login attempts before account lockout. |
| `ACCOUNT_LOCKOUT_DURATION_MINUTES` | No | `15` | Account lockout duration in minutes. |
| `PASSWORD_MIN_LENGTH` | No | `12` | Minimum password length (NIST recommends ≥8). |
| `PASSWORD_REQUIRE_UPPERCASE` | No | `true` | Require at least one uppercase letter. |
| `PASSWORD_REQUIRE_LOWERCASE` | No | `true` | Require at least one lowercase letter. |
| `PASSWORD_REQUIRE_DIGIT` | No | `true` | Require at least one digit. |
| `PASSWORD_REQUIRE_SPECIAL` | No | `false` | Require at least one special character (NIST recommends **against** this). |
| `PASSWORD_HISTORY_COUNT` | No | `5` | Number of previous passwords to remember for reuse prevention. Set to `0` to disable. |
| `PASSWORD_MAX_AGE_DAYS` | No | `0` | Password expiry in days. `0` = no expiry (NIST-compliant). |
| `PASSWORD_CHECK_BREACHED` | No | `true` | Check new passwords against HaveIBeenPwned breach database via k-Anonymity API. The password never leaves the server. Set to `false` to disable external API calls. |
| `RATE_LIMIT_PER_MINUTE` | No | `100` | Global API rate limit per IP per minute. |
| `TRUSTED_PROXY_CIDRS` | No | _(empty)_ | Comma-separated CIDRs whose `X-Forwarded-For` header is trusted (e.g. `10.0.0.0/8,172.16.0.0/12`). |

---

## MongoDB High Availability

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGO_READ_PREFERENCE` | No | `primary` | Read preference: `primary`, `primaryPreferred`, `secondaryPreferred`, `secondary`, `nearest`. |
| `MONGO_WRITE_CONCERN_W` | No | `majority` | Write concern: `majority` or a number (e.g. `1`, `2`). |
| `MONGO_WRITE_CONCERN_J` | No | `true` | Write concern journal acknowledgement. |
| `MONGO_MAX_POOL_SIZE` | No | `100` | Maximum connection pool size (1–500). |
| `MONGO_MIN_POOL_SIZE` | No | `0` | Minimum connection pool size (0–100). |
| `MONGO_MAX_IDLE_TIME_MS` | No | `30000` | Max idle time for pooled connections in milliseconds. |

---

## OpenTelemetry Tracing

| Variable | Required | Default | Description |
|---|---|---|---|
| `OTEL_ENABLED` | No | `false` | Enable OpenTelemetry distributed tracing. |
| `OTEL_ENDPOINT` | No | `http://localhost:4317` | OTLP exporter endpoint (gRPC). |
| `OTEL_SERVICE_NAME` | No | `sentora` | Service name reported to the tracing backend. |

---

## Multi-Worker & Distributed Locking

| Variable | Required | Default | Description |
|---|---|---|---|
| `WORKERS` | No | `1` | Number of uvicorn workers (1–16). Use >1 only with `ENABLE_DISTRIBUTED_LOCKS=true`. |
| `ENABLE_DISTRIBUTED_LOCKS` | No | `true` | Use MongoDB distributed locks for multi-worker coordination (sync, classification, ingestion). |

---

## Backup & Restore

| Variable | Required | Default | Description |
|---|---|---|---|
| `BACKUP_ENABLED` | No | `false` | Enable scheduled backups. |
| `BACKUP_LOCAL_PATH` | No | `/backups` | Local directory for backup file storage. |
| `BACKUP_RETENTION_COUNT` | No | `7` | Number of backups to retain (1–365). |
| `BACKUP_SCHEDULE_CRON` | No | `0 2 * * *` | Cron schedule for automated backups. |

---

## Fingerprint Library Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LIBRARY_INGESTION_ENABLED` | No | `false` | Enable background ingestion of library entries from public sources (NIST CPE, MITRE ATT&CK, Chocolatey, Homebrew). When `true`, the ingestion scheduler runs at the configured interval. |
| `LIBRARY_INGESTION_INTERVAL_HOURS` | No | `24` | Hours between automatic ingestion runs. Range: 1–168 (1 hour to 1 week). Only takes effect when `LIBRARY_INGESTION_ENABLED=true`. |
| `LIBRARY_INGESTION_SOURCES` | No | _(empty)_ | Comma-separated list of source adapter names to run during automatic ingestion. Available adapters: `nist_cpe`, `mitre`, `chocolatey`, `homebrew`. If empty and ingestion is enabled, no sources are ingested automatically — use the admin UI to trigger manually. |

### Library Ingestion Notes

- **NIST CPE** adapter calls the NVD API v2. Rate limiting is enforced: 6-second delays without an API key, 0.6 seconds with one. For heavy usage, obtain an NVD API key from https://nvd.nist.gov/developers/request-an-api-key.
- **MITRE ATT&CK** adapter downloads the STIX 2.1 bundle (~15 MB) from the MITRE CTI GitHub repository. No API key required.
- **Chocolatey** and **Homebrew** adapters use their public JSON/OData APIs. No API keys required.
- Ingestion runs are tracked in the `library_ingestion_runs` collection and visible in the Library Sources admin view.
- Manual ingestion can always be triggered via `POST /api/v1/library/sources/{source}/ingest` regardless of the `LIBRARY_INGESTION_ENABLED` setting.

---

## Notes

### S1_BASE_URL Trailing Slash

The `S1_BASE_URL` value is validated at startup by a `field_validator` that strips any trailing slash:

```python
@field_validator("s1_base_url")
@classmethod
def strip_trailing_slash(cls, v: str) -> str:
    return v.rstrip("/")
```

Both of these are equivalent and produce the same effective URL:

```
S1_BASE_URL=https://my-console.sentinelone.net/web/api/v2.1
S1_BASE_URL=https://my-console.sentinelone.net/web/api/v2.1/
```

### S1_API_TOKEN Security

The `S1_API_TOKEN` value is treated as a secret throughout the application:

- It is **never** logged. The request logging middleware logs paths and headers but explicitly excludes `Authorization` header values. The S1 API client constructs the header in memory and does not pass it through any logging utility.
- It is **never** returned in any API response, including error responses.
- It is held **in memory only** for the lifetime of the process. It is never written to disk, to MongoDB, or to any cache.
- See `docs/security/s1-token-handling.md` for the full handling policy and rotation procedure.

### MONGO_URI Production Recommendations

The default `mongodb://localhost:27017` is suitable for local development only. For staging and production deployments:

1. **Enable authentication.** Create a dedicated MongoDB user with read/write permissions on the `MONGO_DB` database only:
   ```
   MONGO_URI=mongodb://sentora:STRONG_PASSWORD@mongodb:27017/sentora?authSource=admin
   ```

2. **Enable TLS.** If the MongoDB instance is not on the same private network as the backend:
   ```
   MONGO_URI=mongodb://sentora:STRONG_PASSWORD@mongodb:27017/sentora?tls=true&authSource=admin
   ```

3. **Use a replica set for write acknowledgment guarantees:**
   ```
   MONGO_URI=mongodb://sentora:PASSWORD@mongo1:27017,mongo2:27017/sentora?replicaSet=rs0&authSource=admin
   ```

4. **Do not commit the `.env` file** containing `MONGO_URI` with credentials to version control. Use a secrets manager (Vault, AWS Secrets Manager, etc.) to inject the value at deploy time.

---

## Example .env Files

### On-Prem (default)

```dotenv
# Deployment mode — single-tenant on-premises
DEPLOYMENT_MODE=onprem

# SentinelOne connection
S1_BASE_URL=https://your-console.sentinelone.net
S1_API_TOKEN=your_api_token_here

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB=sentora

# Application
APP_PORT=5002
APP_ENV=production
LOG_LEVEL=INFO

# JWT — set a stable secret for production
JWT_SECRET_KEY=your-secret-key-here
```

### SaaS (multi-tenant)

```dotenv
# Deployment mode — multi-tenant SaaS
DEPLOYMENT_MODE=saas

# Multi-tenancy
MULTI_TENANCY_ENABLED=true
MASTER_DB_NAME=sentora_master

# SentinelOne connection
S1_BASE_URL=https://your-console.sentinelone.net
S1_API_TOKEN=your_api_token_here

# MongoDB (replica set recommended for SaaS)
MONGO_URI=mongodb://mongo1:27017,mongo2:27017,mongo3:27017/sentora?replicaSet=rs0
MONGO_DB=sentora

# Application
APP_PORT=5002
APP_ENV=production
LOG_LEVEL=INFO

# JWT — set a stable secret for production
JWT_SECRET_KEY=your-secret-key-here
```
