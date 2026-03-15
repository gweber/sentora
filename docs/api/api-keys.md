# API Keys

Tenant-scoped API keys for external integrations (SIEM, dashboards, automation).

## Authentication with API Keys

API keys can be passed in two ways:

```
Authorization: Bearer sentora_sk_live_...
```

or:

```
X-API-Key: sentora_sk_live_...
```

## Key Format

```
sentora_sk_live_{48 hex chars}
│       │    │    └── 192-bit random hex
│       │    └── Environment
│       └── Secret Key
└── Prefix (grep-able by secret scanners)
```

## Scopes

| Scope | Description |
|-------|-------------|
| `agents:read` | List and view agents |
| `apps:read` | List and view installed applications |
| `compliance:read` | View compliance results and violations |
| `enforcement:read` | View enforcement rules and violations |
| `audit:read` | View audit log entries |
| `sync:read` | View sync status and history |
| `taxonomy:read` | View taxonomy categories |
| `fingerprints:read` | View fingerprints |
| `dashboard:read` | View dashboard metrics |
| `sync:trigger` | Trigger a manual sync |
| `enforcement:write` | Create and modify enforcement rules |
| `tags:write` | Create and assign tags |
| `read:all` | All read-only scopes |
| `write:all` | All write scopes (implies read:all) |

## Endpoints

### Key Management (JWT user-auth only, admin+)

#### Create Key

```
POST /api/v1/api-keys/
```

**Request:**
```json
{
  "name": "Splunk Integration",
  "description": "Read-only access for SIEM ingestion",
  "scopes": ["read:all"],
  "rate_limit_per_minute": 60,
  "rate_limit_per_hour": 1000,
  "expires_at": "2027-01-01T00:00:00Z"
}
```

**Response (201):**
```json
{
  "key": {
    "id": "...",
    "name": "Splunk Integration",
    "key_prefix": "sentora_sk_live_a8f3",
    "scopes": ["read:all"],
    ...
  },
  "full_key": "sentora_sk_live_a8f3b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7"
}
```

> **Warning:** The `full_key` is shown **once**. Copy it immediately.

#### List Keys

```
GET /api/v1/api-keys/
```

Returns all keys for the tenant. Never includes the full key or hash.

#### Get Key

```
GET /api/v1/api-keys/{id}
```

#### Update Key

```
PUT /api/v1/api-keys/{id}
```

Updates name, description, scopes, rate limits. Does **not** change the key itself.

#### Revoke Key

```
DELETE /api/v1/api-keys/{id}
```

Immediate revocation. All subsequent requests with this key return 401.

#### Rotate Key

```
POST /api/v1/api-keys/{id}/rotate
```

Creates a new key with the same scopes and limits. The old key remains valid for
5 minutes (grace period) to enable zero-downtime rotation.

### Self-Info (API key auth)

#### Current Key

```
GET /api/v1/api-keys/current
```

Returns info about the currently authenticated API key. Only accessible via API key auth.

## Rate Limiting

Each API key has independent rate limits:
- `rate_limit_per_minute` (default: 60)
- `rate_limit_per_hour` (default: 1000)

Rate limit exceeded returns HTTP 429 with `Retry-After: 60` header.

## Security

- Keys are stored as SHA-256 hashes — the plaintext is never persisted
- Key management endpoints require JWT user auth with admin role
- API keys cannot create, modify, or revoke other API keys
- Keys are tenant-isolated — a key can only access its own tenant's data
- The `sentora_sk_live_` prefix enables detection by GitHub, GitGuardian, and truffleHog
