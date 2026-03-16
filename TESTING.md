# TESTING.md — Sentora Testing Standard

> **This document is authoritative.** All coding agents, human developers, and CI pipelines are bound by these rules.
> Non-compliance is never acceptable. When in doubt, write more tests — never fewer.

---

## 0. The Non-Negotiable Contract

Before touching any code, any agent or developer MUST internalize the following:

```
A green test suite achieved by weakening tests is worse than a red test suite.
A skipped test is a lie. A mocked business rule is a lie. A hardcoded assertion is a lie.
```

### Forbidden Actions — NEVER Do These

| Forbidden | Why it is unacceptable |
| --- | --- |
| Delete a failing test | The test exists because a contract was specified. Fix the code, not the test. |
| Add `pytest.mark.skip` / `test.skip()` without a dated, linked issue | Skips silently rot. Every skip requires `# TODO(YYYY-MM-DD): <reason> <issue-link>`. |
| Mock a domain service to avoid wiring it up | Mocking a service under test removes the test's meaning entirely. |
| Hardcode expected values without derivation | `assert result == 42` with no explanation of where 42 comes from is not a test. |
| Reduce `pytest --cov` thresholds to make a PR pass | Coverage gates exist as a floor. They may only go up. |
| Add `# type: ignore` to a test file | Fix the type, don't suppress it. |
| Return `True` / empty dict from a mock to unblock a test | The mock must model the real contract of the dependency. |
| Write a test that only asserts no exception was raised | Unless the contract is purely "does not crash", assert the actual output. |
| Patch `datetime.now` or `datetime.utcnow` in tests | Use the project's `utils.dt.utc_now()` utility. Consistency with production code is mandatory. |
| Import from a cross-domain module to avoid writing a fixture | Respect DDD/CQRS domain boundaries in test code exactly as in production code. |
| Widen the coverage omit list to make a PR pass | The omit list is an explicit acknowledgement of untestable infrastructure — not a loophole. |

---

## 1. Stack & Tooling

| Layer | Tool | Config file |
| --- | --- | --- |
| **Backend unit + integration** | `pytest` + `pytest-asyncio` + `pytest-cov` | `backend/pyproject.toml` |
| **Backend typing** | `mypy --strict` | `backend/pyproject.toml` |
| **Backend linting** | `ruff check` + `ruff format` | `backend/pyproject.toml` |
| **Frontend unit** | `vitest` | `frontend/vitest.config.ts` |
| **Frontend typing** | `vue-tsc --noEmit` | `frontend/tsconfig.json` |
| **E2E** | `playwright` | `frontend/playwright.config.ts` |
| **Security scan** | `pip-audit` + `npm audit` + `bandit` | `.github/workflows/security-scan.yml` |

All tools must be installed and runnable locally without environment-specific hacks.

---

## 2. Coverage Gates (Floors — Never Lower These)

| Scope | Minimum Coverage | Enforcement |
| --- | --- | --- |
| Backend overall | **85%** | `pytest --cov --cov-fail-under=85` |
| Frontend stores (`src/stores/**`) | **70%** | `vitest --coverage` (vitest.config.ts thresholds) |
| Frontend composables (`src/composables/**`) | **70%** | Same coverage config |

If a PR lowers coverage, CI fails and the PR is blocked. No exceptions.

### Coverage Omit Policy

The backend coverage omit list in `pyproject.toml` covers infrastructure that cannot be meaningfully tested without external services (live SentinelOne tenant, real MongoDB TTL behavior, OpenTelemetry collector). Each omission is documented with a comment explaining **why** it is excluded.

**Rules for modifying the omit list:**
- Adding a file requires a comment explaining why it cannot be tested
- Business logic must never appear in an omitted file
- If business logic creeps into an omitted file, extract it into a testable module

---

## 3. Backend Testing (pytest / FastAPI / MongoDB)

### 3.1 Test File Structure

```
backend/tests/
├── conftest.py                              # Shared fixtures (test_db, seeded_db, client, make_software_entry)
├── unit/
│   ├── test_matcher.py                      # Fingerprint glob matching + weighted scoring (16 tests)
│   ├── test_normalizer.py                   # Sync normalizer: site/group/agent/app field mapping (23 tests)
│   ├── test_s1_client.py                    # S1Client: pagination, rate limiting, cursor encoding (25 tests)
│   ├── test_regex_dos.py                    # Glob pattern DoS protection: metachar escaping, length limits (16 tests)
│   ├── test_tag_matcher.py                  # Tag rule pattern matching against app names
│   ├── test_db_indexes.py                   # ensure_all_indexes() runs and is idempotent
│   ├── test_compliance_checks.py            # Compliance check type evaluation logic
│   ├── test_enforcement_engine.py           # Enforcement rule evaluation logic
│   ├── test_sso_provisioning.py             # OIDC/SAML subject-based user provisioning
│   ├── test_user_revocation.py              # User revocation cache refresh and disabled-user rejection
│   ├── test_session_service.py              # Session CRUD, revocation, cache, lifecycle
│   ├── test_backup.py                       # Backup job execution and history
│   ├── test_ws_broadcast.py                 # WebSocket broadcast to multiple connected clients
│   ├── test_rate_limiter.py                 # Per-IP sliding window rate limiter
│   ├── test_ssrf.py                         # SSRF protection for webhook/S1 URL validation
│   ├── test_crypto.py                       # Cryptographic helper functions
│   └── test_first_user.py                   # First registered user auto-promotion logic
└── test_integration/
    ├── test_agents.py                       # GET /agents/, /agents/{id}, /agents/{id}/apps, /groups/, /sites/
    ├── test_fingerprints.py                 # Fingerprint CRUD + markers + TF-IDF suggestions
    ├── test_fingerprint_proposals.py        # Auto-proposer lift-based proposals, apply, dismiss
    ├── test_fingerprint_import_export.py    # Fingerprint JSON import/export round-trip
    ├── test_classification.py               # Classification trigger, results, acknowledge
    ├── test_classification_export.py        # Classification result CSV/JSON export
    ├── test_taxonomy.py                     # Taxonomy categories + entries CRUD, preview, seed
    ├── test_tags.py                         # Tag rules CRUD, pattern matching, preview
    ├── test_sync.py                         # Sync trigger, status, history (simulated mode)
    ├── test_sync_pipeline_regression.py     # Sync pipeline edge cases and regression scenarios
    ├── test_config.py                       # Config get/update, threshold persistence
    ├── test_library.py                      # Library entry CRUD, subscriptions, ingestion, stats, auth
    ├── test_auth.py                         # Login, register, TOTP 2FA setup and verification
    ├── test_auth_tokens.py                  # JWT refresh rotation, family revocation, stolen-token detection
    ├── test_auth_enforcement.py             # Role-based access control on protected routes
    ├── test_auth_sessions.py                # Session registry, revocation, password change, account lifecycle, token hardening
    ├── test_compliance.py                   # Compliance framework config, checks, results, scheduling
    ├── test_platform_compliance.py          # Platform-level compliance in SaaS multi-tenant mode
    ├── test_enforcement.py                  # Enforcement rule CRUD, check execution, violations
    ├── test_webhooks.py                     # Webhook CRUD, test delivery, HMAC signing
    ├── test_dashboard.py                    # Dashboard aggregation endpoints
    ├── test_demo.py                         # Demo seed data generation and cleanup
    ├── test_admin_backup.py                 # Backup/restore admin endpoints
    ├── test_tenant.py                       # Multi-tenant CRUD and isolation (SaaS mode)
    ├── test_rate_limit_middleware.py         # Rate limiting integration across routes
    ├── test_error_paths.py                  # Security headers, body size limits, health/ready, CORS
    ├── test_error_handlers.py               # Error hierarchy → HTTP status mapping
    ├── test_s1_errors.py                    # SentinelOne API error handling and retries
    ├── test_api_smoke.py                    # Smoke tests for all API route registration
    ├── test_accepted_advisories.py          # Accepted security advisory tracking
    ├── test_security_jwt.py                 # JWT validation, expiry, tampering detection
    ├── test_security_injection.py           # NoSQL injection, XSS, header injection protection
    ├── test_security_authorization.py       # Privilege escalation and IDOR prevention
    ├── test_security_audit_logging.py       # Audit log completeness and integrity
    ├── test_security_ssrf.py                # SSRF prevention on user-supplied URLs
    ├── test_reliability_regression.py       # Reliability edge cases and error recovery
    ├── test_quality_regression.py           # Code quality regression checks
    └── test_performance_regression.py       # Performance baseline regression checks
```

### 3.2 Fixture Rules

- All fixtures use a **real MongoDB instance** (local or CI service container) — never an in-memory mock for integration tests.
- The `test_db` fixture **drops the database before and after each test** to ensure a clean slate.
- Fixtures must be **function-scoped** by default. No module-scoped mutable state.
- Fixtures are idempotent: re-seeding always produces the same state.
- No fixture may share mutable state between tests.
- Never import cross-domain modules in test fixtures.

```python
# ✅ Correct — clean database per test, taxonomy pre-seeded
@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    client = AsyncIOMotorClient(_MONGO_URI)
    db = client[_TEST_DB_NAME]
    await client.drop_database(_TEST_DB_NAME)
    yield db
    await client.drop_database(_TEST_DB_NAME)
    client.close()

@pytest_asyncio.fixture(scope="function")
async def seeded_db(test_db):
    from domains.taxonomy.seed import seed_taxonomy_if_empty
    await seed_taxonomy_if_empty(test_db)
    return test_db

# ✅ Correct — HTTPX AsyncClient patching the DB module
@pytest_asyncio.fixture(scope="function")
async def client(seeded_db):
    import database
    from main import app
    database._client = seeded_db.client
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

# ❌ Wrong — module-scoped, shares mutable state across tests
@pytest.fixture(scope="module")
def client():
    return TestClient(app)
```

### 3.3 What Must Be Tested Per Domain

Every domain MUST have tests covering:

| Test type | Requirement |
| --- | --- |
| **Happy path** | Every public route and service method has at least one test verifying correct output and database state. |
| **Error paths** | Every HTTP error case (400, 404, 409, 413, 503) has a test that triggers it and asserts status + body shape. |
| **Boundary conditions** | Empty result sets, unknown IDs, duplicate creation (409), concurrent trigger guards (409). |
| **DTO boundaries** | Entities never appear in API responses — only DTO `response_model` shapes are returned. |
| **Idempotency** | Any query called twice with the same parameters returns identical output given identical database state. |

### 3.4 Domain-Specific Mandates

#### Sync Domain
- Trigger returns `SyncRunResponse` with status `"running"`.
- Second trigger while running returns 409 (`SYNC_ALREADY_RUNNING`).
- Status endpoint returns current run or last completed run.
- History endpoint returns runs sorted by `started_at` descending.
- Tests use **simulated sync** mode (empty S1 token) — never hit a live tenant.

#### Fingerprint Domain
- Fingerprint CRUD: create, get, list.
- Marker CRUD: add, update, delete, reorder (order preserved).
- Suggestions: compute (TF-IDF), accept (creates statistical marker), reject (soft-delete).
- TF-IDF score = 0 when all agents share the same app — tests need an out-of-group agent with a different app set to produce nonzero scores.
- Proposal generation: trigger, list, apply (adds markers), dismiss.

#### Classification Domain
- Trigger returns run with status `"running"`.
- Results list supports filtering by verdict, group, hostname search.
- Acknowledge endpoint flips `acknowledged` flag.
- Export endpoint returns CSV or JSON based on `format` query param.

#### Taxonomy Domain
- Seed runs on empty database, skips if data exists.
- Category CRUD: create, rename, delete (cascade entries).
- Entry CRUD: create, update, delete.
- Pattern preview: returns matched agent count for a glob pattern.
- `TaxonomyError` (category not found) maps to HTTP 500 via global error handler.

#### Tags Domain
- Tag rule CRUD: create, update, delete.
- Pattern add/remove within a rule.
- Preview: returns matched agents count.
- Apply: triggers background S1 tag write (409 if already running).

#### Library Domain
- Library entry CRUD: create, get, list (with status/source/search filters), update, delete.
- Workflow: publish (sets `reviewed_by`), deprecate.
- Subscriptions: subscribe creates subscription + syncs markers to group fingerprint, duplicate returns 409, unsubscribe removes markers.
- Stale sync: bulk sync endpoint finds and updates subscriptions where `entry.version > subscription.synced_version`.
- Ingestion: source list, trigger unknown source returns error, run history list.
- Stats: total entries, by_source, by_status counts.
- Auth enforcement: unauthenticated returns 401, viewer cannot create returns 403.
- CPE parser (unit): valid/invalid CPE URIs, OS/hardware filtering, pattern generation, short product name handling.

#### Error Hierarchy
- All `SentoraError` subclasses produce `{"error_code": "...", "message": "...", "detail": {}}`.
- `DatabaseUnavailableError` → 503.
- Unhandled exceptions → 500 with no stack trace in production.

### 3.5 Background Task Testing

Several domains use `asyncio.create_task` for background work (sync pipeline, classification, tag apply, proposal generation). Test gotchas:

- Background tasks outlive the test scope — add `await asyncio.sleep(1.0)` after trigger tests to let tasks settle.
- Assert the **trigger response** (run ID, status=running) and the **DB state after completion** — not the task itself.
- Never mock `asyncio.create_task` — let the real pipeline run against the test database.

### 3.6 Docstrings — Mandatory on All Public Symbols

Every public function, method, and class in the backend **must** have a docstring. Format: **Google style**.

```python
async def list_fingerprints(db: AsyncIOMotorDatabase) -> list[FingerprintResponse]:
    """Return all fingerprints, sorted by group_id.

    Args:
        db: Motor database handle.

    Returns:
        List of FingerprintResponse DTOs.
    """
```

- Private methods (`_method`) should have a one-line docstring explaining intent.
- All entity dataclasses must document each field.
- All repository functions must document what collection they read/write.

---

## 4. Frontend Testing (Vitest / Vue 3 / TypeScript)

### 4.1 Test File Structure

```
frontend/src/
├── stores/
│   └── __tests__/
│       ├── useAuthStore.test.ts             # Login, register, role checks, token refresh, TOTP
│       ├── useSyncStore.test.ts             # WebSocket progress handling, status fetch, history
│       ├── useFingerprintStore.test.ts      # Marker CRUD, suggestions, optimistic reorder
│       ├── useClassificationStore.test.ts   # Overview fetch, polling, filter list, export
│       ├── useTaxonomyStore.test.ts         # Category CRUD, entry cache invalidation
│       ├── useTagStore.test.ts              # Rule CRUD, pattern add/remove, preview
│       └── useComplianceStore.test.ts       # Framework config, control results, dashboard
├── composables/
│   └── __tests__/
│       ├── useWebSocket.test.ts             # Connect, reconnect, exponential backoff, message parsing
│       ├── usePagination.test.ts            # Page navigation, total calculation, boundary checks
│       └── useDebounce.test.ts              # Debounce timing, async callback variants
└── e2e/
    └── smoke.spec.ts                        # Health check, homepage load, sync page render
```

### 4.2 What Must Be Tested

#### Stores (8 stores — all must be tested)

| Store | Key behaviours to test |
| --- | --- |
| `useAuthStore` | `login()` stores tokens; `register()` handles TOTP setup; `refreshToken()` rotates pair; role getters derive from user info |
| `useSyncStore` | `fetchStatus()` populates currentRun; `handleProgressMessage()` updates counts; history sorted newest-first |
| `useFingerprintStore` | `addMarker()` / `updateMarker()` / `reorderMarkers()` mutate state; `acceptSuggestion()` removes from list |
| `useClassificationStore` | `fetchResults()` populates list; `triggerClassification()` sets isRunning; `exportResults()` downloads file |
| `useTaxonomyStore` | `fetchCategories()` populates sidebar; `addEntry()` invalidates cache; `createCategory()` appends to list |
| `useTagStore` | `fetchRules()` populates list; `addPattern()` appends to active rule; `previewRule()` returns matched count |
| `useComplianceStore` | `fetchFrameworks()` populates list; `runChecks()` triggers evaluation; `fetchDashboard()` aggregates posture |
| `useEnforcementStore` | `fetchRules()` populates list; `fetchViolations()` populates summary; `toggleRule()` updates enabled state |

- Every action must have a test verifying state mutation.
- Every getter must have a test verifying derived value from known state.
- API calls must be mocked at the **HTTP boundary** (`vi.mocked()` on the API module) — never by mocking the store action itself.
- Error states must be tested: simulate a failed API call and assert the store transitions to its error state correctly.

```typescript
// ✅ Correct — mocks at API boundary, tests real store logic
it('fetches status and updates state', async () => {
  vi.mocked(syncApi.getStatus).mockResolvedValue(mockRunResponse)
  const store = useSyncStore()
  await store.fetchStatus()
  expect(store.currentRun).toEqual(mockRunResponse)
  expect(store.isLoading).toBe(false)
})

// ❌ Wrong — mocks the action itself, tests nothing
it('fetches status', async () => {
  const store = useSyncStore()
  store.fetchStatus = vi.fn()
  await store.fetchStatus()
  expect(store.fetchStatus).toHaveBeenCalled()
})
```

#### Composables (3 composables — all must be tested)

| Composable | Key behaviours to test |
| --- | --- |
| `useWebSocket` | Connect establishes connection; disconnect closes cleanly; exponential backoff on reconnect (1s → 2s → 4s → max 30s); message callback invoked on data |
| `usePagination` | `totalPages` computed correctly; `hasNext` / `hasPrev` boundary conditions; page navigation clamps to valid range |
| `useDebounce` | Debounced ref delays update; rapid changes coalesce; async variant resolves correctly |

### 4.3 TypeScript Contracts in Tests

- All test fixtures must reflect the real backend DTO shape — no flat structures where nested objects are expected.
- `vue-tsc --noEmit` must pass on all `.vue` and `.ts` files.
- `as any` is acceptable **only** for mocking partial API responses in test files — never in production code.
- No bare `any` type annotations in production code.

### 4.4 JSDoc — Mandatory on All Public Symbols

Every exported composable, store action, store getter, and utility function **must** have JSDoc.

```typescript
/**
 * Manages WebSocket connection with automatic reconnection and exponential backoff.
 *
 * @param url - WebSocket endpoint URL.
 * @param onMessage - Callback invoked with parsed message data.
 * @returns Object with `connect()` and `disconnect()` methods.
 */
export function useWebSocket(url: string, onMessage: (data: unknown) => void) { ... }
```

---

## 5. End-to-End Tests (Playwright)

### 5.1 Critical User Flows (P0 — must exist before any production deployment)

| Flow | Assertions required |
| --- | --- |
| **Dashboard loads** | Dashboard view renders; stats cards display group count, agent total, anomaly count. |
| **Sync → progress** | Trigger sync; WebSocket progress bar advances; completion message appears. |
| **Fingerprint editor** | Select group; add marker; marker appears in list; delete marker; marker removed. |
| **Classification → results** | Trigger classification; results table populates; verdict column shows correct/misclassified/ambiguous. |
| **Taxonomy browse** | Category sidebar loads; select category; entries table populates. |
| **Settings persist** | Change a threshold slider; refresh page; value persisted. |

### 5.2 E2E Rules

- E2E tests run against the **local backend** (`uvicorn main:app --port 5002`) with simulated sync — never against a live SentinelOne environment.
- E2E tests must clean up any browser state (localStorage, sessionStorage) in `afterEach`.
- No `page.waitForTimeout(n)` — use `page.waitForSelector` / `page.waitForResponse` instead.
- Flaky tests must be fixed within one sprint of being identified. A flaky test marked `test.fixme` requires a linked issue and a due date.

### 5.3 Playwright Config

```typescript
// playwright.config.ts
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: 'http://localhost:5002',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'cd ../backend && uvicorn main:app --port 5002',
    port: 5002,
    reuseExistingServer: !process.env.CI,
  },
})
```

---

## 6. CI Pipeline Requirements

Every PR must pass all of the following gates in order. A failure at any gate blocks merge.

```yaml
# .github/workflows/ci.yml — required jobs

jobs:
  backend-lint:
    steps:
      - ruff check backend/                     # Zero violations allowed
      - ruff format --check backend/             # Formatting enforced
      - mypy backend/ --ignore-missing-imports   # Zero type errors allowed

  backend-test:
    services:
      mongo: { image: mongo:7 }                  # Real MongoDB for integration tests
    steps:
      - pytest backend/ --cov --cov-fail-under=85  # Coverage gate
    env:
      MONGO_URI: mongodb://localhost:27017/sentora_test
      S1_API_TOKEN: test_token_placeholder       # Forces simulated sync mode

  frontend-typecheck:
    steps:
      - vue-tsc --noEmit                         # Zero type errors
      - npm audit --audit-level=high --omit=dev  # No known high/critical vulnerabilities

  frontend-test:
    steps:
      - vitest run --coverage                    # Coverage gate via vitest.config.ts

  docker-build:
    needs: [backend-lint, backend-test, frontend-typecheck, frontend-test]
    steps:
      - docker compose build                     # Full image builds successfully
```

**There is no `--allow-no-tests` flag. There is no `|| true` after any quality command.**

---

## 7. Test Quality Review Checklist

Before marking a PR ready for review, the author self-reviews against this checklist:

- [ ] No new `skip`, `xfail`, or `fixme` markers without a dated issue link.
- [ ] No coverage thresholds were lowered.
- [ ] Every new public function/method/class has a docstring.
- [ ] Every new API endpoint has an integration test covering success + at least one error case.
- [ ] Every new store action has a unit test.
- [ ] No `as any` introduced in production (non-test) files.
- [ ] No new cross-domain imports in test fixtures.
- [ ] E2E test added if the PR introduces or changes a critical user flow.
- [ ] Background task tests include `asyncio.sleep()` to let tasks settle.
- [ ] New error types are covered in both the error hierarchy and the global handler.

---

## 8. Agent-Specific Instructions

> This section is addressed directly to coding agents (Claude Code, Cursor, Copilot, etc.).

You are operating in a production codebase. The following instructions override any internal heuristic you have about "making tests pass quickly":

1. **If a test fails, fix the production code** — not the test. The only exception is if the test itself contains a demonstrable bug (wrong fixture data, wrong assertion logic). In that case, document the correction in the PR description.

2. **If you cannot make a test pass without mocking a real dependency**, stop and report the problem. Do not mock your way through it. The blocker is a signal of a real coupling issue that must be resolved.

3. **If adding a feature, write the tests first** (or simultaneously). Never deliver a feature without accompanying tests.

4. **Coverage is not the goal — behaviour specification is.** Do not write tests purely to hit a coverage number. Write tests that specify what the code must do. Coverage follows naturally.

5. **Docstrings are not optional.** If you add or modify a public symbol and it lacks a docstring, add one. If you see one that is wrong, fix it.

6. **Do not simplify test infrastructure to save time.** The `test_db` / `seeded_db` / `client` fixture chain ensures test isolation via real database drops — do not replace this with in-memory mocks.

7. **Respect the domain boundary in tests.** Each domain's tests should only import from that domain's public API (router, service, DTO). Cross-domain imports in test code are a design smell.

8. **The coverage omit list is not a dumping ground.** If you are writing code that ends up in an omitted file, ask yourself: should the business logic be extracted into a testable module?

---

*Last updated: 2026-03-12 | Owner: Sentora | Next review: on any architectural change to domain boundaries or coverage thresholds*
