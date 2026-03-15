# Quickstart Guide

Get Sentora running in under five minutes.

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Docker | 24.0 | `docker --version` |
| Docker Compose | v2 (plugin) | `docker compose version` |
| SentinelOne API token | — | See [S1 API Setup](./s1-api-setup.md) |
| Network access to S1 console | — | Outbound HTTPS on port 443 |

Sentora pulls data directly from your SentinelOne management console at sync time. The host running Docker must be able to reach your S1 instance URL.

---

## 1. Clone the Repository

```bash
git clone https://github.com/yourorg/sentora
cd sentora
```

---

## 2. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and set at minimum:

```dotenv
# Choose your deployment mode (default: onprem)
DEPLOYMENT_MODE=onprem

S1_BASE_URL=https://your-instance.sentinelone.net
S1_API_TOKEN=your_api_token_here

# Set a stable JWT secret for production
JWT_SECRET_KEY=your-secret-key-here
```

**Deployment modes:**
- `onprem` (default) — Single-tenant. The first registered user becomes `admin` with full access.
- `saas` — Multi-tenant with database-per-tenant isolation. Also set `MULTI_TENANCY_ENABLED=true`. The first registered user becomes `super_admin` (platform operator).

All other variables have working defaults for a local deployment. See `.env.example` for the full list with descriptions, or `docs/deployment/environment-variables.md` for detailed reference.

> **Security note:** Never commit `.env` to version control. The repository's `.gitignore` already excludes it.

---

## 3. Start the Stack

```bash
docker compose up -d
```

Docker Compose will pull images on the first run. This takes one to three minutes depending on your connection. Subsequent starts are nearly instant.

---

## 4. Verify Services Are Running

```bash
docker compose ps
```

Expected output — all three services should show `running` or `healthy`:

```
NAME                    IMAGE               STATUS
sentora-backend-1    sentora-backend  running (healthy)
sentora-frontend-1   sentora-frontend running
sentora-mongo-1      mongo:7             running (healthy)
```

Confirm the backend is responding:

```bash
curl -s http://localhost:5002/health | python3 -m json.tool
```

Expected response:

```json
{
  "status": "ok",
  "mongo": "connected"
}
```

---

## 5. Access the UI

Open your browser and navigate to:

```
http://localhost:5002
```

In production the backend serves both the API and the compiled frontend on port 5002. In development, the Vite dev server runs on port 5003.

You will be prompted to register the first user account. In on-prem mode, this user is automatically promoted to `admin`. In SaaS mode, the first user becomes `super_admin`.

The Dashboard loads automatically. On a fresh installation it will show zero agents and zero groups — that is expected until you run your first sync.

---

## 6. First Sync

1. Click **Sync Now** in the top navigation bar.
2. The sync panel opens showing two progress bars: **Agents** and **Applications**.
3. The Applications fetch is the slowest step in large environments (thousands of records per agent). Do not close the browser tab during the initial sync.
4. When both bars reach 100% and the status reads **Sync complete**, click **Close**.

Sync duration estimates:

| Environment Size | Estimated Duration |
|---|---|
| < 500 agents | 1–2 minutes |
| 500–2,000 agents | 3–8 minutes |
| 2,000–10,000 agents | 10–30 minutes |
| 10,000+ agents | See [Scaling Guide](./scaling.md) |

---

## 7. Verify Data Loaded

Return to the **Dashboard**. You should now see:

- **Total Agents** — the count of managed endpoints pulled from S1.
- **Groups** — the number of S1 site/group entries discovered.
- **Classification coverage** — initially low or zero; improves as you build fingerprints.

If agent or group counts appear but applications show zero, your S1 token may be missing the Applications scope. See [S1 API Setup](./s1-api-setup.md).

---

## 8. Tag Your Fleet (Optional)

Once you have fingerprints and classification results, you can use **Tag Rules** to label agents by role and push those labels back to SentinelOne as native S1 tags.

1. Click **Tag Rules** in the left sidebar.
2. Click **New Rule** and enter a tag name (e.g. `manufacturing`, `labs`, `servers`).
3. Drag taxonomy entries onto the rule to define which installed software indicates that role.
4. Click **Preview** to see which agents match the rule before committing.
5. Click **Apply to S1** to push the tag to all matching agents via the SentinelOne API.

> **Note:** Applying tags requires an Operator-role S1 token. See [S1 API Setup](./s1-api-setup.md) for role requirements.

---

## 9. Create Your First Enforcement Rule

Enforcement rules define software policies — what must be installed, what must be absent, and what's allowed.

1. Click **Enforcement** in the left sidebar.
2. Click **Create Rule**.
3. Fill in:
   - **Name:** `EDR Required`
   - **Taxonomy Category:** select `Required / EDR` from the dropdown (this category should contain entries with patterns like `SentinelOne*`)
   - **Type:** Required
   - **Severity:** Critical
   - **Scope:** leave empty (all agents)
4. Click **Create Rule**.
5. Click **Run All Checks** to evaluate the rule immediately.
6. The summary cards update: any agent without SentinelOne shows as a violation.

For more rule types and examples, see [Enforcement Rules](../ENFORCEMENT.md).

---

## 10. Activate a Compliance Framework

Compliance monitoring checks your fleet against framework-specific controls (SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz).

1. Click **Compliance** in the left sidebar, then **Settings**.
2. Toggle **BSI IT-Grundschutz** (or your preferred framework) to enabled.
3. Click the framework card to review its 16 controls.
4. Click **Back to Dashboard**, then **Run All Checks**.
5. The dashboard shows per-framework scores and the control status table fills in.

All violations — from both enforcement rules and compliance controls — appear in the unified **All Violations** feed at the bottom of the Compliance Dashboard. Filter by source or severity.

For configuration details, see [Compliance Monitoring](../COMPLIANCE.md).

---

## Troubleshooting

### MongoDB not starting

**Symptom:** `docker compose ps` shows `mongo` in `Exiting` state or restart loop.

**Cause:** Most commonly a data directory permission issue or a port conflict.

**Fix:**
```bash
# Check logs
docker compose logs mongo

# If the data directory is the cause, remove it and let Docker recreate it
docker compose down -v
docker compose up -d
```

> Warning: `docker compose down -v` removes all stored data. Only use this on a fresh installation.

---

### S1 connection refused / timeout

**Symptom:** Sync fails immediately with "connection refused" or the progress bar freezes at 0%.

**Cause:** The `S1_BASE_URL` is unreachable from the Docker host, or the value in `.env` is incorrect.

**Fix:**
```bash
# Test connectivity from outside Docker
curl -I https://your-instance.sentinelone.net/web/api/v2.1/system/status

# Test from inside the backend container
docker compose exec backend curl -s \
  -H "Authorization: ApiToken $S1_API_TOKEN" \
  "https://your-instance.sentinelone.net/web/api/v2.1/system/status"
```

Ensure the URL does not have a trailing slash and matches the format `https://hostname.sentinelone.net` exactly.

---

### No agents appear after sync completes

**Symptom:** Sync shows 100% for Agents but the Dashboard count remains zero.

**Cause:** The API token may have Site-scope visibility only, missing agents at the Account level, or the token lacks the Agents: List permission.

**Fix:** Review your token's scope in the S1 console. The token needs Account-level scope to enumerate all groups. See [S1 API Setup](./s1-api-setup.md#required-permissions).

---

### Port conflict — address already in use

**Symptom:** `docker compose up` fails with `bind: address already in use` for port 5002, 27017, or 5003.

**Fix:**
```bash
# Identify what is using the port (example for 5002)
lsof -i :5002

# Option A: Stop the conflicting process
kill <PID>

# Option B: Change the Sentora port in .env
APP_PORT=3001
BACKEND_PORT=5010
```

Then restart: `docker compose up -d`.

---

### Frontend not loading (blank page or 502)

**Symptom:** `http://localhost:5002` shows a blank page, a 502 error, or an endless spinner.

**Cause A:** The frontend container is still building its initial Vite production bundle (takes 20–40 seconds on first boot).

**Fix A:** Wait 60 seconds, then hard-refresh the browser (`Ctrl+Shift+R`).

**Cause B:** The backend is not healthy so the frontend's API calls fail.

**Fix B:**
```bash
docker compose logs backend --tail 50
```

Look for Python import errors or `mongo: connection refused` messages. Resolve those first, then restart:

```bash
docker compose restart backend
```

---

## Development Setup

Use this workflow when you want to iterate on backend or frontend code without rebuilding Docker images.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Make sure MongoDB is running. You can start only the database container:

```bash
docker compose up -d mongo
```

Then start the development servers from the project root:

```bash
./start.sh
```

`start.sh` launches:
- **uvicorn** on `http://localhost:5002` (backend, with hot-reload)
- **Vite dev server** on `http://localhost:5003` (frontend, with HMR)

Interactive API documentation is available at `http://localhost:5002/api/docs` in development mode.

### Running Tests Locally

```bash
# Backend
cd backend
pytest --cov --cov-report=term-missing

# Frontend
cd frontend
npm run test
```

See [TESTING.md](../../TESTING.md) for full testing guidance.
