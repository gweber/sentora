# Docker Deployment Guide

Sentora ships with a `docker-compose.yml` that starts the full stack — backend, frontend build, and MongoDB — with a single command.

---

## Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Docker Engine | 24+ | Docker Desktop for Mac/Windows includes the Engine |
| Docker Compose | v2 (plugin) | Bundled with Docker Desktop; on Linux install via `docker compose` (no hyphen) |
| SentinelOne API token | — | Read-only scope on your S1 console is sufficient; see minimum required permissions in `docs/security/s1-token-handling.md` |
| Available ports | — | Port 5002 (backend), 27017 (MongoDB). Change `APP_PORT` in `.env` if either conflicts. |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/gweber/sentora.git
cd sentora

# 2. Copy the example environment file
cp .env.example .env

# 3. Edit .env — set S1_BASE_URL and S1_API_TOKEN at minimum
$EDITOR .env

# 4. Build the frontend and start all services
docker compose --profile build up -d
```

The `--profile build` flag includes the `frontend-build` service, which is a one-shot Node 22 container that runs `npm ci && npm run build` and writes the compiled assets to a shared Docker volume. The backend mounts this volume at `/app/frontend/dist` and serves the files via FastAPI's `StaticFiles`.

On subsequent restarts (when the frontend source has not changed) you can omit `--profile build`:

```bash
docker compose up -d
```

To rebuild the frontend after source changes:

```bash
docker compose --profile build run --rm frontend-build
docker compose restart backend
```

---

## Verifying the Deployment

### Check container health

```bash
docker compose ps
```

All three services should show `running (healthy)` (MongoDB uses a healthcheck; the backend `depends_on` MongoDB's healthy state).

Expected output:

```
NAME                    STATUS          PORTS
sentora-mongodb-1    running (healthy)   0.0.0.0:27017->27017/tcp
sentora-backend-1    running             0.0.0.0:5002->5002/tcp
```

### Check the backend API

```bash
curl -s http://localhost:5002/api/v1/sync/status | python3 -m json.tool
```

A healthy response is a JSON object with `current_run: null` and `last_completed_run: null` on a fresh install.

### Check the UI

Open `http://localhost:5002` in a browser. You should see the Sentora dashboard. In `APP_ENV=development` mode the Swagger UI is also available at `http://localhost:5002/api/docs`.

### Check MongoDB connectivity

```bash
docker compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

Expected output: `{ ok: 1 }`.

---

## Production Hardening

The default `docker-compose.yml` is designed for easy local deployment. Before running in a production or internet-facing environment, apply the following hardening steps.

### 1. Enable MongoDB Authentication

The default configuration starts MongoDB without authentication, which is acceptable on a private network but not on any internet-reachable host.

Create an admin user and an application user, then update `MONGO_URI`:

```bash
# Connect to the running MongoDB container
docker compose exec mongodb mongosh

# Inside mongosh:
use admin
db.createUser({ user: "adminUser", pwd: "STRONG_ADMIN_PASSWORD", roles: ["root"] })
use sentora
db.createUser({
  user: "sentora",
  pwd: "STRONG_APP_PASSWORD",
  roles: [{ role: "readWrite", db: "sentora" }]
})
exit
```

Update `.env`:

```dotenv
MONGO_URI=mongodb://sentora:STRONG_APP_PASSWORD@mongodb:27017/sentora?authSource=sentora
```

Add authentication configuration to the `mongodb` service in your override file (`docker-compose.override.yml`):

```yaml
services:
  mongodb:
    environment:
      MONGO_INITDB_ROOT_USERNAME: adminUser
      MONGO_INITDB_ROOT_PASSWORD: STRONG_ADMIN_PASSWORD
    command: ["--auth"]
```

### 2. Put a Reverse Proxy in Front of the Backend

Do not expose port 5002 directly to the internet. Use nginx or Caddy as a TLS-terminating reverse proxy:

**Caddy example (`Caddyfile`):**

```
sentora.example.com {
    reverse_proxy backend:5002
}
```

**nginx example (minimal):**

```nginx
server {
    listen 443 ssl;
    server_name sentora.example.com;

    ssl_certificate     /etc/ssl/certs/sentora.crt;
    ssl_certificate_key /etc/ssl/private/sentora.key;

    location / {
        proxy_pass         http://backend:5002;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }
}
```

The `Upgrade` / `Connection` headers are required to proxy the sync progress WebSocket.

### 3. Set APP_ENV to production

```dotenv
APP_ENV=production
LOG_LEVEL=INFO
```

This disables Swagger UI and ReDoc, removes the development CORS exception for `localhost:5003`, and sets appropriate log verbosity.

### 4. Apply Resource Limits

Add resource limits to the `docker-compose.override.yml` to prevent a runaway sync from consuming all available memory:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
  mongodb:
    deploy:
      resources:
        limits:
          memory: 1G
```

### 5. Regular MongoDB Backups

The MongoDB data volume (`mongo_data`) must be backed up regularly. Use `mongodump` for consistent backups:

```bash
# Run a backup — outputs to ./backups/YYYY-MM-DD/
docker compose exec mongodb mongodump \
  --uri="mongodb://sentora:APP_PASSWORD@localhost:27017/sentora?authSource=sentora" \
  --out /tmp/backup

docker cp sentora-mongodb-1:/tmp/backup ./backups/$(date +%F)
```

Schedule this as a cron job on the host. Consider shipping backup archives to object storage (S3, GCS, etc.) and retaining at least 30 days of history.

---

## Upgrading

```bash
# 1. Pull the latest images / source
git pull origin main

# 2. Rebuild the frontend
docker compose --profile build run --rm frontend-build

# 3. Rebuild and restart the backend
docker compose build backend
docker compose up -d backend

# 4. Verify the backend is healthy
docker compose ps
curl -s http://localhost:5002/api/v1/sync/status
```

There are no database migrations to run — MongoDB's schema-flexible documents accommodate new fields without structural changes. If a release's changelog notes a breaking schema change, follow the specific migration instructions in that release's notes.

---

## Troubleshooting

### Backend fails to start: "MongoDB not reachable"

**Symptom:** Backend logs show `MongoDB not reachable at mongodb://mongodb:27017 — starting in degraded mode`.

**Cause:** The backend started before MongoDB was ready, or the `depends_on` healthcheck is failing.

**Fix:**
```bash
docker compose ps   # Check MongoDB status
docker compose logs mongodb --tail=50
# If MongoDB is still initializing, wait 30 seconds and check again
docker compose restart backend
```

### Frontend shows a blank page or 404 on refresh

**Symptom:** The UI loads on `/` but navigating directly to `/classification/results` returns a 404 or blank page.

**Cause:** The `frontend-build` profile was not run, so `frontend/dist/` is empty or missing.

**Fix:**
```bash
docker compose --profile build run --rm frontend-build
docker compose restart backend
```

### POST /api/v1/sync/trigger returns 502

**Symptom:** Triggering a sync returns `{"error_code": "S1_API_ERROR", "message": "..."}`.

**Cause:** The backend cannot reach the SentinelOne API. This is usually a wrong `S1_BASE_URL`, an invalid `S1_API_TOKEN`, or a network/firewall issue.

**Fix:**
```bash
# Test S1 connectivity from inside the backend container
docker compose exec backend curl -s \
  -H "Authorization: ApiToken YOUR_TOKEN" \
  "https://your-console.sentinelone.net/web/api/v2.1/system/status"
```

Verify `S1_BASE_URL` does not have a trailing slash and that the token has the required API scopes.

### MongoDB volume shows stale data after a reset

**Symptom:** After running `docker compose down` and `docker compose up -d`, old data persists.

**Cause:** `docker compose down` does not remove named volumes by default. The `mongo_data` volume persists across restarts.

**Fix:**
```bash
# WARNING: This deletes all Sentora data permanently
docker compose down -v
docker compose --profile build up -d
```

### Classification results are empty after a sync

**Symptom:** Sync completes successfully but `GET /api/v1/classification/results` returns an empty list.

**Cause:** Classification is not run automatically after a sync. It is a separate, explicit operation.

**Fix:** After a successful sync, navigate to the Classification page in the UI and click "Run Classification", or call `POST /api/v1/classification/run` directly. Note that classification also requires at least one fingerprint to exist; if no fingerprints have been defined yet, all agents will receive the `unclassifiable` verdict.
