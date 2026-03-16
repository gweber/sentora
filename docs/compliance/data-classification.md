# Data Classification Policy

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Document ID**    | COMP-DC-001                                |
| **Status**         | Active                                     |
| **Version**        | 1.0                                        |
| **Owner**          | Security & Compliance Team                 |
| **Last Review Date** | 2026-03-15                               |
| **Next Review**    | 2026-09-13                                 |
| **Classification** | Internal                                   |

---

## 1. Purpose

This policy defines the data classification framework for the Sentora platform.
It categorizes all data types processed, stored, or transmitted by the system and
establishes handling requirements for each classification level. Proper data
classification ensures that information receives the appropriate level of protection
based on its sensitivity and business value.

---

## 2. Scope

This policy applies to all data within the Sentora system:

- Data at rest in MongoDB collections
- Data in transit between client and server, and between Sentora and SentinelOne API
- Data in processing within backend services
- Configuration and environment data
- Logs and audit trails
- Backup data

---

## 3. Classification Levels

### 3.1 Level Definitions

| Level | Label | Color Code | Description |
|-------|-------|------------|-------------|
| 1 | **Public** | Green | Information that can be freely disclosed without risk. No business impact if disclosed |
| 2 | **Internal** | Blue | Information for internal use. Low business impact if disclosed to unauthorized parties |
| 3 | **Confidential** | Orange | Sensitive information. Moderate to significant business impact if disclosed |
| 4 | **Restricted** | Red | Highly sensitive information. Severe business impact if disclosed or compromised |

### 3.2 Handling Requirements by Level

| Requirement | Public | Internal | Confidential | Restricted |
|------------|--------|----------|--------------|------------|
| **Encryption at rest** | Not required | Recommended | Required | Required |
| **Encryption in transit** | Recommended | Required | Required | Required |
| **Access control** | None | Authentication | Authentication + role-based | Authentication + role-based + MFA |
| **Audit logging** | Not required | Recommended | Required | Required |
| **Backup encryption** | Not required | Not required | Required | Required |
| **Retention policy** | Indefinite | Defined | Defined + review | Minimized + strict review |
| **Disposal method** | Standard delete | Standard delete | Secure delete | Cryptographic erasure |
| **Sharing restrictions** | None | Internal only | Need-to-know + approval | Named individuals + explicit approval |
| **Labeling** | Optional | Recommended | Required | Required |
| **Incident reporting** | Standard | Standard | Priority | Immediate |

---

## 4. Data Type Classification

### 4.1 Restricted Data (Level 4)

Restricted data would cause severe harm if disclosed. This includes authentication
secrets, cryptographic keys, and credentials that could grant unauthorized access.

| Data Type | Location | Format | Handling Notes |
|-----------|----------|--------|----------------|
| SentinelOne API tokens | Environment variable `S1_API_TOKEN` | String | Never stored in code or logs. Loaded from environment only. Fail-fast if missing |
| JWT signing secret | Environment variable `JWT_SECRET_KEY` | String | Auto-generated with warning if not configured. Must be unique per deployment |
| User passwords (hashed) | MongoDB `users` collection | bcrypt 5.x hash | Never stored in plaintext. Never returned in API responses. Never logged |
| TOTP secrets | MongoDB `users` collection | Encrypted string | Used for 2FA enrollment. Must be encrypted at rest. Never exposed after enrollment |
| SAML SP private keys | Configuration file or environment | PEM-encoded key | Used for SAML assertion signing/decryption. File permissions restricted (0600) |
| SAML SP certificates | Configuration file | PEM-encoded cert | Associated with private keys. Handle as restricted due to pairing |
| OIDC client secrets | Environment variable | String | Used for OIDC token exchange. Never stored in code or logs |
| Database connection credentials | Environment variable `MONGODB_URL` | Connection string | May contain username/password. Never logged |
| Backup encryption keys | Environment variable or key management | String | Required for encrypted backup restoration |

**Technical Controls:**
- Environment variables only; never committed to version control
- `.gitignore` excludes `.env` files
- `.env.example` documents required variables without values
- Structured logging explicitly excludes these fields
- bcrypt work factor prevents rainbow table attacks

### 4.2 Confidential Data (Level 3)

Confidential data could cause significant harm if disclosed, particularly PII and
network information that could aid reconnaissance.

| Data Type | Location | Format | Handling Notes |
|-----------|----------|--------|----------------|
| User email addresses | MongoDB `users` collection | String | PII — used for authentication. Access restricted to admin role |
| User display names | MongoDB `users` collection | String | PII — visible to admins only |
| Agent hostnames | MongoDB `agents` collection | String | Network topology information. Could aid reconnaissance if disclosed |
| Agent IP addresses | MongoDB `agents` collection | String/Array | Network topology information. Classified as confidential network data |
| Agent MAC addresses | MongoDB `agents` collection | String | Hardware identifiers. Network topology data |
| Agent OS details | MongoDB `agents` collection | String | Version information could reveal patch levels and vulnerabilities |
| SentinelOne site/group hierarchy | MongoDB `sites`/`groups` collections | Documents | Organizational structure information |
| OIDC client IDs | Configuration | String | While not secret, reveal integration details. Pair with restricted client secrets |
| SAML IdP metadata | Configuration | XML | Contains endpoints and certificates of identity provider |
| Session tokens (JWT access/refresh) | In transit / client storage | JWT string | Short-lived but grant access. 15-min access tokens, 7-day refresh tokens |

**Technical Controls:**
- RBAC restricts access (admin for user data, analyst+ for agent data)
- Audit logging on all access to confidential data
- TLS required for all data in transit (HSTS enforcement)
- CORS policy restricts cross-origin access
- Session idle timeout (30 minutes) limits exposure window

### 4.3 Internal Data (Level 2)

Internal data is intended for use within the Sentora system. Disclosure would have
limited business impact but could reveal operational details.

| Data Type | Location | Format | Handling Notes |
|-----------|----------|--------|----------------|
| Agent inventory metadata | MongoDB `agents` collection | Documents | Device counts, OS distributions. Non-identifying aggregate data |
| Installed applications list | MongoDB `applications` collection | Documents | Software inventory per agent. Useful for asset management |
| Software fingerprints | MongoDB `fingerprints` collection | Documents | TF-IDF matching results with confidence scores |
| Fingerprint proposals | MongoDB `fingerprint_proposals` collection | Documents | Pending matches awaiting analyst review |
| Classification results | MongoDB `classifications` collection | Documents | Software categorization outcomes |
| Classification rules | MongoDB `classification_rules` collection | Documents | Rule definitions for automated classification |
| Tag rules and assignments | MongoDB `tags` collection | Documents | Tag rule engine definitions and match results |
| Audit logs | MongoDB `audit_logs` collection | Documents | Security event records. Hash-chain integrity. 90-day TTL |
| Sync state and checkpoints | MongoDB `sync_state` collection | Documents | Sync progress, cursor positions, last-run timestamps |
| Dashboard aggregations | Computed / cached | Documents | Fleet statistics, fingerprinting coverage metrics |
| Runtime configuration | MongoDB `config` collection | Documents | Application settings (non-secret) |
| Prometheus metrics | `/metrics` endpoint | Text | Request counts, durations, in-progress gauges |
| Application logs | Stdout / log aggregator | JSON | Structured logs with correlation IDs. May contain internal paths |
| WebSocket messages | In transit | JSON | Sync progress updates. Rate-limited to 10 msg/s |

**Technical Controls:**
- Authentication required for all API access
- Role-based access control (viewer+ for read, analyst+ for write)
- Structured logging format for centralized analysis
- Metrics endpoint may be restricted by network policy in production

### 4.4 Public Data (Level 1)

Public data can be freely shared without business impact. This includes reference data,
documentation, and openly available API metadata.

| Data Type | Location | Format | Handling Notes |
|-----------|----------|--------|----------------|
| Taxonomy categories | MongoDB `taxonomy` collection | Documents | Software category definitions (e.g., "Browser", "IDE", "Security") |
| Taxonomy vendors | MongoDB `taxonomy` collection | Documents | Known vendor names (e.g., "Microsoft", "Google", "Mozilla") |
| Software library entries | MongoDB `software_library` collection | Documents | Reference library of known software names and metadata |
| API documentation (OpenAPI) | `/api/spec.json`, `/api/spec.yaml` | JSON/YAML | Auto-generated API schema. Publicly accessible |
| Health check responses | `/health`, `/health/ready` | JSON | Liveness and readiness status. No sensitive data |
| License text | `LICENSE`, `COMMERCIAL_LICENSE.md` | Markdown | Open source and commercial license terms |
| Code of Conduct | `CODE_OF_CONDUCT.md` | Markdown | Contributor behavioral expectations |
| Security policy (disclosure process) | `SECURITY.md` | Markdown | How to report vulnerabilities (process, not vulnerabilities) |
| README and documentation | `README.md`, `docs/` | Markdown | System documentation and guides |
| ADR summaries | `docs/adr/` | Markdown | Architecture decision records (public context) |
| Error message templates | API responses | JSON | Standardized error codes and messages |

**Technical Controls:**
- No authentication required for public endpoints
- Health check endpoints intentionally expose minimal information
- API documentation does not include example credentials or tokens

---

## 5. Data Flow Classification

### 5.1 External Data Flows

| Flow | Direction | Data Classification | Transport Security |
|------|-----------|-------------------|-------------------|
| SentinelOne API -> Sentora | Inbound | Confidential (agent data) | TLS 1.2+ required |
| Browser -> Sentora API | Inbound | Mixed (per endpoint) | HSTS enforced |
| Sentora API -> Browser | Outbound | Mixed (per endpoint) | HSTS enforced |
| OIDC Provider <-> Sentora | Bidirectional | Restricted (tokens), Confidential (claims) | TLS 1.2+ required |
| SAML IdP <-> Sentora | Bidirectional | Restricted (assertions), Confidential (attributes) | TLS 1.2+ required |
| Webhook notifications | Outbound | Internal (event summaries) | TLS recommended |

### 5.2 Internal Data Flows

| Flow | Direction | Data Classification | Transport Security |
|------|-----------|-------------------|-------------------|
| Backend -> MongoDB | Bidirectional | Up to Restricted | Network isolation; auth required |
| Frontend -> Backend API | Bidirectional | Up to Confidential | Loopback or Docker network |
| WebSocket (sync progress) | Backend -> Frontend | Internal | Same as API transport |
| Prometheus scrape | Monitoring -> Backend | Internal | Network policy restricted |

---

## 6. Data Retention

| Data Type | Classification | Retention Period | Disposal Method | Authority |
|-----------|---------------|-----------------|-----------------|-----------|
| Audit logs | Internal | 90 days | TTL auto-delete | MongoDB TTL index |
| JWT access tokens | Confidential | 15 minutes | Self-expiring | Token `exp` claim |
| JWT refresh tokens | Confidential | 7 days | Self-expiring + revocation | Token `exp` claim |
| Sync checkpoints | Internal | Until next sync | Overwritten | Sync manager |
| User accounts | Confidential | Until admin deletion | Secure delete | Admin action |
| Agent data | Confidential | Until sync refresh | Overwritten | Sync cycle |
| Fingerprints | Internal | Indefinite | Standard delete | Admin action |
| Classifications | Internal | Indefinite | Standard delete | Admin action |
| Taxonomy data | Public | Indefinite | Standard delete | Admin action |
| Application logs | Internal | Per log aggregator policy | Rotation | Infrastructure |
| Backup data | Same as source | Per backup retention policy | Secure delete | Backup schedule |

---

## 7. Handling Violations

| Severity | Example | Response |
|----------|---------|----------|
| Critical | Restricted data exposed in logs or API response | Immediate incident response. Rotate affected credentials. Notify affected parties within 24 hours |
| High | Confidential data accessed by unauthorized role | Investigate access path. Revoke unauthorized access. Review RBAC configuration |
| Medium | Internal data shared externally without approval | Review sharing controls. Update access policies. Retrain involved personnel |
| Low | Public data handling inconsistency | Document and correct in next review cycle |

---

## 8. Responsibilities

| Role | Responsibility |
|------|---------------|
| **Security Team** | Maintain this policy. Conduct annual data classification reviews. Investigate violations |
| **Developers** | Apply classification when introducing new data types. Implement required technical controls. Review DTOs to prevent data leakage |
| **Administrators** | Configure access controls per classification requirements. Manage user lifecycle. Monitor audit logs |
| **Analysts** | Handle classified data per policy. Report suspected violations. Follow need-to-know principle |

---

## 9. Review and Updates

This policy must be reviewed:

- Semi-annually (scheduled)
- When new data types are introduced
- When data flows change significantly
- After any data handling incident
- When regulatory requirements change

All reviews must be documented with date, reviewer, and any changes made.

---

*This document is classified as Internal and subject to the handling requirements
defined in Section 3.2 for that classification level.*
