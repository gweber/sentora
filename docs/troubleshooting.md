# Troubleshooting

Common issues and their solutions when running Sentora.

---

## MongoDB not available (503 on all endpoints)

**Symptoms:** Every API call returns HTTP 503, frontend shows "Failed to load" everywhere.

**Cause:** The backend cannot connect to MongoDB.

**Solutions:**
1. Verify MongoDB is running:
   ```bash
   mongosh --eval "db.runCommand({ping:1})"
   ```
2. Check the `MONGO_URI` environment variable (default: `mongodb://localhost:27017`).
3. If using Docker Compose, ensure the `mongo` service is healthy:
   ```bash
   docker compose ps
   docker compose logs mongo
   ```
4. Check network connectivity if MongoDB is on a remote host. Ensure the port (default 27017) is reachable.
5. If MongoDB requires authentication, verify that `MONGO_URI` includes credentials:
   ```
   MONGO_URI=mongodb://sentora_user:YOUR_PASSWORD@host:27017/sentora?authSource=admin
   ```

---

## Sync stuck in "running" state

**Symptoms:** The sync page shows "Sync in progress" indefinitely. Triggering a new sync returns HTTP 409 (conflict).

**Cause:** A previous sync crashed or the process was killed mid-sync, leaving the in-memory lock held.

**Solutions:**
1. **Restart the backend process.** The SyncManager re-initializes on startup, clearing the in-memory lock. Any incomplete sync checkpoint is preserved for resumption.
2. After restart, check if a checkpoint exists and resume:
   - The sync page will show a "Resume" option if a checkpoint is detected.
   - Or trigger a new full sync, which will overwrite the stale state.
3. If the problem persists after restart, manually clear the checkpoint:
   ```javascript
   // In mongosh
   use sentora
   db.sync_checkpoint.deleteOne({_id: "current"})
   db.sync_runs.updateMany({status: "running"}, {$set: {status: "failed"}})
   ```

---

## Classification not running

**Symptoms:** Triggering classification returns an error or does nothing. No classification results appear.

**Possible causes and fixes:**

1. **No fingerprints defined.** Classification requires at least one fingerprint to score agents against.
   - Navigate to Groups, select a group, and create a fingerprint with at least one marker.
   - Use "Generate Proposals" for automated marker suggestions.

2. **No agents synced.** Classification operates on agents stored in the `agents` collection.
   - Run a full sync first: go to the Sync page and click "Full Sync".

3. **No installed app data.** The `installed_app_names` field on agents must be populated.
   - If you upgraded from an earlier version, run the "Backfill app names" operation from the Sync page under Data Maintenance.

4. **Classification already running.** Only one classification can run at a time.
   - Wait for the current run to complete, or restart the backend to clear a stuck lock.

5. **Check the audit log.** Navigate to the Audit Log page and filter by domain "classification" for error details.

---

## S1 API rate limiting (429 responses)

**Symptoms:** Sync fails partway through or is very slow. Server logs show `429 Too Many Requests` from the SentinelOne API.

**Cause:** The S1 API enforces rate limits. The built-in token-bucket rate limiter should prevent this, but limits vary by S1 license tier.

**Solutions:**
1. **Reduce page sizes.** On the Sync page under "Fetch Limits", lower the Agents and Installed Apps page sizes (e.g. from 500 to 200). This reduces the rate of API calls.
2. **Use incremental sync.** After the initial full sync, use "Refresh" instead of "Full Sync". Incremental syncs fetch only changed data.
3. **Check S1 API limits.** Contact your SentinelOne administrator to understand your tenant's rate limits.
4. **Review server logs.** The S1 client logs rate-limit events:
   ```bash
   # Look for rate-limit warnings
   grep -i "rate" backend/logs/*.log
   ```
5. **Wait and retry.** S1 rate limits typically reset within 60 seconds. The sync can be resumed from its checkpoint after a failure.

---

## WebSocket not connecting

**Symptoms:** Sync progress does not update in real-time. The browser console shows WebSocket connection errors.

**Possible causes and fixes:**

1. **Proxy not configured for WebSocket upgrade.**
   - If using nginx, ensure WebSocket upgrade headers are set:
     ```nginx
     location /api/v1/sync/progress {
         proxy_pass http://backend:5002;
         proxy_http_version 1.1;
         proxy_set_header Upgrade $http_upgrade;
         proxy_set_header Connection "upgrade";
     }
     ```
   - The Docker Compose `Dockerfile.frontend` nginx config includes this by default.

2. **CORS blocking the connection.**
   - In development, the Vite dev server proxies `/api` to the backend (port 5002), including WebSocket. Ensure you access the app via `http://localhost:5003`, not directly on port 5002.
   - In production, both API and frontend are served from the same origin (port 5002), so CORS is not an issue.

3. **Backend not running.**
   - The WebSocket endpoint is at `/api/v1/sync/progress`. Verify the backend is responding:
     ```bash
     curl http://localhost:5002/api/v1/health
     ```

4. **Browser reconnection.**
   - The frontend WebSocket composable (`useWebSocket.ts`) implements exponential backoff reconnection. Check the browser console for reconnection attempts.

---

## High memory usage during sync

**Symptoms:** The backend process memory grows significantly during a full sync, potentially causing OOM kills.

**Cause:** Large fleets can have millions of installed app records. Processing them in memory-intensive batches contributes to peak memory usage.

**Solutions:**
1. **Reduce S1 API page sizes.** On the Sync page, under "Fetch Limits", lower page sizes for Agents and Installed Apps (e.g. 200 instead of 500). Smaller pages reduce peak memory per batch.
2. **Use per-phase sync.** Instead of a full sync, sync data types individually (Sites, Groups, Agents, Apps, Tags) to spread memory usage across separate operations.
3. **Increase container memory limits.** If running in Docker, increase the memory limit:
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             memory: 2G
   ```
4. **Monitor with `/api/v1/health`.** The health endpoint returns basic process info. Watch memory usage over time.

---

## Frontend not loading (blank page)

**Symptoms:** Navigating to the application URL shows a blank white page or a "Cannot GET /" error.

**Possible causes and fixes:**

1. **Frontend not built.**
   - In production mode, the backend serves the compiled frontend from `frontend/dist/`.
   - Build the frontend:
     ```bash
     cd frontend && npm install && npm run build
     ```
   - Verify `frontend/dist/index.html` exists.

2. **SPA fallback not configured.**
   - The backend must serve `index.html` for all non-API routes (SPA routing).
   - This is handled automatically by `main.py`'s static file mount with fallback.
   - If using a reverse proxy, ensure it falls back to `/index.html` for 404s on non-API paths.

3. **Wrong port or URL.**
   - Development: access via `http://localhost:5003` (Vite dev server).
   - Production: access via `http://localhost:5002` (backend serves everything).
   - Docker: access via the exposed port in `docker-compose.yml`.

4. **JavaScript errors.**
   - Open the browser developer console (F12) and check for JavaScript errors.
   - Common issue: mismatched API base URL. The frontend expects `/api/v1/` to be available at the same origin.

5. **Node modules not installed.**
   - If running the dev server:
     ```bash
     cd frontend && npm install && npm run dev
     ```

---

## Taxonomy seed data not loading

**Symptoms:** Categories and entries are empty after first startup.

**Cause:** The seed runs only if the `taxonomy_categories` collection is empty. If a partial seed occurred, it may not re-run.

**Solutions:**
1. Clear taxonomy collections and restart:
   ```javascript
   use sentora
   db.taxonomy_categories.drop()
   db.taxonomy_entries.drop()
   ```
2. Restart the backend -- the seed will run automatically.

---

## API key authentication failing

**Symptoms:** Requests with an API key return 401 Unauthorized or 403 Forbidden.

**Possible causes and fixes:**

1. **Invalid key format.** API keys must start with `sentora_sk_live_`. Ensure the full key is being sent, not just the prefix.

2. **Key revoked or expired.** Check the key status in the API Keys management page. Revoked keys are immediately rejected. Expired keys (past `expires_at`) return 401.

3. **Missing scope.** A 403 response with message "API key missing required scope" means the key doesn't have the scope for the requested endpoint. Edit the key to add the required scope.

4. **Rate limit exceeded.** HTTP 429 with "API key rate limit exceeded" means per-key limits are hit. Each key has independent per-minute and per-hour limits. Wait for the window to reset or increase the limits.

5. **Wrong header.** API keys are accepted via:
   - `Authorization: Bearer sentora_sk_live_...`
   - `X-API-Key: sentora_sk_live_...`

6. **Management endpoints require JWT.** Creating, listing, updating, rotating, and revoking API keys requires JWT user auth with `admin` role. API keys cannot manage other API keys.

7. **Key was rotated.** After rotation, the old key remains valid for 5 minutes (grace period). After that, only the new key works.

---

## Tests failing with database errors

**Symptoms:** `pytest` fails with MongoDB connection errors or collection conflicts.

**Solutions:**
1. Ensure MongoDB is running locally on the default port (27017).
2. The test suite uses a separate database (`sentora_test`) that is dropped before and after each test.
3. If tests hang, a previous test run may have left stale background tasks. Kill any lingering `uvicorn` or `pytest` processes and retry.
4. Run tests with verbose output for debugging:
   ```bash
   cd backend && pytest -v --tb=long
   ```
