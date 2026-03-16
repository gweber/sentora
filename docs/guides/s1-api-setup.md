# SentinelOne API Token Setup

This guide walks through creating a SentinelOne service user and API token with the minimum permissions required for Sentora.

---

## Overview

Sentora uses the SentinelOne REST API (v2.1) primarily in read-only mode. The one exception is the **Tag Rules** feature: when you apply a tag rule, Sentora calls `POST /agents/actions/manage-tags` to add tags to matching agents in S1.

**Choosing a role:**
- **Viewer** — sufficient if you only use sync, fingerprinting, and classification. Tag Rules will work for preview but the apply step will fail.
- **Operator** (or higher) — required if you want to use Tag Rules and push tags back to S1. This is the recommended role for most deployments.

---

## Step 1: Navigate to Service Users

1. Log in to your SentinelOne management console as an Account Admin or higher.
2. In the left navigation, click **Settings**.
3. Select **Users**.
4. Click the **Service Users** tab.

> The exact navigation path varies slightly between SentinelOne versions (Singularity Platform, SentinelOne 22.x, etc.). If you do not see "Service Users", look under **Settings → Integrations → Service Users** or consult your S1 version documentation.

---

## Step 2: Create a New Service User

1. Click **Actions → Create New Service User**.
2. Fill in the form:
   - **Name:** `Sentora Read-Only` (or any descriptive name)
   - **Description:** `Service account for Sentora asset classification tool`
   - **Expiration:** Set an expiration date appropriate for your security policy (90 or 365 days is common). You will need to rotate the token before it expires — see [Token Rotation](#token-rotation) below.
3. Click **Next**.

---

## Step 3: Assign Scope and Role

This is the most important configuration step.

- **Scope:** Set to **Account** level (not Site or Group).

  Account scope is required because Sentora enumerates all groups across your account to build a complete picture of the environment. A Site-scoped token will return only agents within that site, causing incomplete sync results.

- **Role:** Set to **Operator** (recommended) or **Viewer** (read-only).

  Operator is recommended — it allows Sentora to apply Tag Rules and write tags back to agents. Viewer is sufficient if you do not intend to use the Tag Rules apply feature.

Click **Next** and then **Create**.

---

## Step 4: Copy the API Token

After the service user is created, the console displays the API token **exactly once**. Copy it immediately to a secure location (a password manager or secrets vault). You cannot retrieve it again — if lost, you must generate a new token.

---

## Step 5: Add the Token to Sentora

Open your `.env` file (copy from `.env.example` if you have not already):

```dotenv
S1_BASE_URL=https://your-instance.sentinelone.net
S1_API_TOKEN=your_copied_token_here
```

The base URL must match your console URL exactly — no trailing slash, and the scheme must be `https`.

---

## Step 6: Verify the Token

Test connectivity from the command line before starting Sentora:

```bash
curl -s \
  -H "Authorization: ApiToken YOUR_TOKEN" \
  "https://your-instance.sentinelone.net/web/api/v2.1/system/status"
```

A successful response looks like:

```json
{
  "data": {
    "health": "ok"
  }
}
```

If you receive a `401 Unauthorized`, the token is invalid or has expired. If you receive a connection error, check your `S1_BASE_URL` and network access.

---

## Required vs. Optional API Permissions

The following table lists every S1 API permission relevant to Sentora and whether it is required.

| Permission Area | Scope | Required | Notes |
|---|---|---|---|
| Agents: List | Account | **Yes** | Core data source for endpoint inventory |
| Agents: View | Account | **Yes** | Needed to read agent detail fields |
| Groups: List | Account | **Yes** | Used to build group/site structure |
| Groups: View | Account | **Yes** | Needed to read group attributes |
| Applications: List | Account | **Yes** | The primary fingerprint data source; data-heavy in large environments |
| Applications: View | Account | **Yes** | Needed to read application detail |
| Agents: Modify Tags | Account | **Yes (Tag Rules)** | Required to write tags back to agents via `manage-tags`. Not needed if you only use sync/classification. |
| System: Status | — | Recommended | Used for health checks and connectivity tests |
| Threats: List | — | No | Not used by Sentora |
| Policies: List | — | No | Not used by Sentora |
| Users: List | — | No | Not used by Sentora |
| Deep Visibility | — | No | Not used by Sentora |

The Viewer role at Account scope satisfies all required permissions by default.

---

## Token Rotation

API tokens expire on the date set at creation time. When a token expires, Sentora sync jobs will fail with a `401 Unauthorized` error.

**Recommended rotation procedure:**

1. At least one week before expiration, create a new service user and generate a fresh token (or, if your S1 version supports it, regenerate the token on the existing service user).
2. Copy the new token.
3. Update `.env`: replace the `S1_API_TOKEN` value.
4. Restart the backend container:
   ```bash
   docker compose restart backend
   ```
5. Run a test sync to confirm connectivity.
6. Invalidate or delete the old service user.

Set a calendar reminder for token renewal. In production environments, consider using a secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.) to automate rotation and delivery to the running container.

---

## Security Recommendations

- **Use a dedicated service account.** Do not reuse tokens that belong to human user accounts — these expire or are revoked when employees leave.
- **Apply least privilege.** Operator at Account scope is the recommended minimum for full functionality. If Tag Rules are not needed, Viewer is sufficient. Do not grant Admin or higher unless required.
- **Store tokens in secrets managers in production.** Pass the token to the container via an environment variable injected at runtime rather than committed to a `.env` file on disk.
- **Rotate on breach.** If you suspect a token has been exposed (e.g., accidentally committed to version control), invalidate it in the S1 console immediately and generate a new one.
- **Audit service user activity.** SentinelOne logs API usage by service user. Review these logs periodically to confirm that only expected read operations are occurring.
- **Do not share tokens across tools.** If multiple tools integrate with your S1 console, each should have its own service user with its own token. This limits the blast radius if one token is compromised.

---

## Troubleshooting

| Error | Likely Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Token is invalid, expired, or incorrectly copied | Verify token in S1 console, regenerate if needed |
| `403 Forbidden` | Token exists but lacks the required permission | Check service user role and scope |
| `connection refused` | `S1_BASE_URL` is wrong or network is blocked | Verify URL, test with `curl` from the Docker host |
| `0 agents returned` | Token is Site-scoped, missing account-level access | Recreate service user with Account scope |
| Sync hangs at Applications | Large environment hitting S1 rate limits | See [Scaling Guide](./scaling.md#s1-api-rate-limiting) |
