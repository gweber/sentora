# Contributing to Sentora

Thank you for your interest in contributing. This guide covers everything you need to get started: reporting bugs, suggesting features, setting up a development environment, writing code, and submitting pull requests.

---

## Code of Conduct

This project follows a standard Contributor Code of Conduct. By participating you agree to uphold it. Instances of unacceptable behavior may be reported to the project maintainers.

All contributors are expected to:

- Use welcoming and inclusive language.
- Respect differing viewpoints and experiences.
- Accept constructive criticism gracefully.
- Focus on what is best for the community and the project.

---

## Reporting Bugs

Use [GitHub Issues](https://github.com/gweber/sentora/issues) to report bugs.

Before opening a new issue:

1. Search existing open and closed issues to see if the bug has already been reported.
2. If you find an existing issue, add a comment with any additional context rather than opening a duplicate.

When filing a new bug report, include:

- **Sentora version** (commit SHA or Docker image tag).
- **Deployment method** (Docker Compose, local `start.sh`, etc.).
- **Operating system and browser** (for UI bugs).
- **Steps to reproduce** — the exact sequence of actions that triggers the bug, including any API calls with redacted sensitive values.
- **Expected behavior** — what should have happened.
- **Actual behavior** — what did happen, including any error messages or log output.
- **Logs** — relevant lines from `docker compose logs backend` with any sensitive values redacted.

Do not include `S1_API_TOKEN`, MongoDB credentials, or other secrets in issue reports.

**Security vulnerabilities** must not be reported via public GitHub issues. See `docs/security/` for the responsible disclosure process.

---

## Suggesting Features

Use [GitHub Issues](https://github.com/gweber/sentora/issues) with the `enhancement` label to suggest new features.

A good feature request answers:

- **What problem does this solve?** Describe the use case in terms of what you are trying to accomplish, not the specific implementation you have in mind.
- **Who is affected?** Is this specific to a particular deployment type (OT/ICS, IT asset management, etc.)?
- **What alternatives have you considered?** Are there workarounds? Why are they insufficient?
- **What does success look like?** How would you know the feature is working correctly?

For significant changes — new bounded contexts, changes to the data model, new external integrations — please discuss the approach in an issue before opening a pull request. This avoids duplicated effort and ensures the design fits the existing architecture.

---

## Development Setup

### Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.12 | `pyenv install 3.12` or system package manager |
| Node.js | 22 | `nvm install 22` or system package manager |
| npm | 10+ | Bundled with Node.js 22 |
| MongoDB | 7 | `docker run -d -p 27017:27017 mongo:7` |
| Git | 2.x | System package manager |

### Clone and install dependencies

```bash
# Clone
git clone https://github.com/gweber/sentora.git
cd sentora

# Backend dependencies
cd backend
pip install -e ".[dev]"
cd ..

# Frontend dependencies
cd frontend
npm install
cd ..
```

### Configure environment

```bash
cp .env.example .env
# Edit .env: set S1_BASE_URL and S1_API_TOKEN
# For local dev without a real S1 instance, leave S1_API_TOKEN empty
# and use the simulated sync manager (which runs a mock pipeline)
```

### Start the development servers

```bash
./start.sh
```

`start.sh` starts both servers in parallel:

- **Backend** (FastAPI + uvicorn with `--reload`) at `http://localhost:5002`
- **Frontend** (Vite dev server with HMR) at `http://localhost:5003`

The frontend dev server proxies API calls to the backend. Open `http://localhost:5003` in your browser.

The interactive API docs (Swagger UI) are available at `http://localhost:5002/api/docs` when `APP_ENV=development`.

### Run the test suite

```bash
# Backend
cd backend
pytest                          # All tests with coverage
pytest -m critical              # Critical path tests only
pytest -k test_taxonomy         # Tests matching a keyword

# Frontend
cd frontend
npm run test                    # Vitest unit tests
npm run test:coverage           # With coverage report
npm run lint                    # ESLint
vue-tsc --noEmit                # TypeScript type check
```

Coverage gates are enforced by CI:

- Backend overall: 85% minimum
- Frontend stores: 80% minimum
- Frontend components: 60% minimum

See `TESTING.md` for the full testing contract and `pyproject.toml` for pytest configuration.

---

## Making Changes

### Fork and branch

1. Fork the repository on GitHub.
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/sentora.git`
3. Add the upstream remote: `git remote add upstream https://github.com/gweber/sentora.git`
4. Create a feature branch from `main`:

```bash
git checkout main
git pull upstream main
git checkout -b <type>/<short-description>
```

### Branch naming convention

| Type | When to use | Example |
|---|---|---|
| `feature/` | New functionality | `feature/scheduled-sync` |
| `fix/` | Bug fix | `fix/ws-disconnect-cleanup` |
| `refactor/` | Code structure change with no behavior change | `refactor/classification-service` |
| `docs/` | Documentation only | `docs/adr-auth-design` |
| `chore/` | Tooling, dependencies, CI | `chore/upgrade-fastapi-0116` |
| `test/` | Tests only (no production code change) | `test/taxonomy-search-boundary` |

Use lowercase kebab-case after the prefix. Keep branch names under 50 characters.

### Commit messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `style`.

**Scope:** the bounded context or component affected: `sync`, `taxonomy`, `fingerprint`, `classification`, `frontend`, `docker`, `ci`.

**Examples:**

```
feat(sync): add rate-limit retry with exponential backoff

fix(classification): correct ambiguity gap comparison direction

docs(contributing): add ADR process section

test(taxonomy): add boundary condition tests for empty pattern list

chore(ci): add pip-audit step to backend quality job
```

The short summary must be in the imperative mood ("add", "fix", "correct") and must not end with a period. Keep it under 72 characters.

---

## Pull Request Process

### Before opening a PR

Run the full quality suite locally and ensure it passes:

```bash
# Backend
cd backend
ruff check .
mypy --strict . --ignore-missing-imports --exclude tests/
pytest --cov --cov-fail-under=85

# Frontend
cd frontend
npm run lint
vue-tsc --noEmit
npm run test:coverage
```

### PR checklist

When you open a pull request, work through the following checklist. Include it in your PR description:

```markdown
## Checklist

- [ ] New functionality has accompanying tests (happy path + at least one error case)
- [ ] All existing tests pass locally (`pytest`, `npm run test`)
- [ ] Backend coverage is ≥ 85% and was not lowered
- [ ] `ruff check .` passes with zero violations
- [ ] `mypy --strict .` passes with zero errors
- [ ] ESLint passes with zero warnings
- [ ] `vue-tsc --noEmit` passes with zero errors
- [ ] All new public functions, methods, and classes have docstrings (Google style)
- [ ] No `pytest.mark.skip` or `test.skip()` added without a dated issue link
- [ ] No `# type: ignore` added to test files
- [ ] If this changes a cross-cutting concern (auth, DB schema, API contract), an ADR has been written or updated
- [ ] The PR description explains *why* this change is needed, not just what it does
```

### Review process

1. Open the PR against `main` with a clear title following the commit message convention.
2. Fill in the PR template and checklist.
3. CI must pass all gates before a review is requested. Do not request review on a failing CI run unless you need guidance on the failure.
4. At least one maintainer review and approval is required before merge.
5. Address review comments by pushing additional commits; do not force-push a branch under review.
6. Maintainers will squash-merge or rebase-merge to keep the commit history clean.

---

## Code Style

### Python (backend)

The backend uses **ruff** for linting and formatting, and **mypy** for type checking. Both are configured in `backend/pyproject.toml`.

```bash
cd backend
ruff check .          # Lint
ruff format .         # Format
mypy --strict .       # Type check
```

Key rules enforced by ruff:

- `E`, `F` — pyflakes and pycodestyle errors
- `I` — isort import ordering
- `UP` — pyupgrade (prefer modern Python syntax)
- `B` — flake8-bugbear
- `SIM` — flake8-simplify
- `ANN` — type annotations required on all public functions

**Docstrings are mandatory** on all public functions, methods, and classes. Use Google style:

```python
def classify_agent(agent_id: str, fingerprints: list[Fingerprint]) -> ClassificationResult:
    """Score an agent against all fingerprints and return a classification verdict.

    Args:
        agent_id: String ObjectId of the agent to classify.
        fingerprints: List of all Fingerprint objects to score against.

    Returns:
        A ClassificationResult with a verdict and per-fingerprint scores.

    Raises:
        ClassificationNotFoundError: If no installed applications exist for the agent.
    """
```

### TypeScript / Vue (frontend)

The frontend uses **ESLint** with the Vue 3 + TypeScript ruleset and **vue-tsc** for type checking.

```bash
cd frontend
npm run lint          # ESLint
vue-tsc --noEmit      # Type check
```

**JSDoc is mandatory** on all exported composables, store actions, store getters, and utility functions.

Vue components must follow these conventions:

- Use `<script setup lang="ts">` — the Composition API with `setup` syntax.
- Define props with `defineProps<{}>()` using explicit TypeScript interfaces.
- Use Pinia stores for all shared state. Do not pass store instances as props.
- Tailwind CSS utility classes for styling. No scoped `<style>` blocks unless unavoidable.

---

## Testing Requirements

**All new logic must have tests.** A pull request that introduces untested code will not be approved.

### Backend

- Every new public function and class must have at least one unit or integration test.
- Every new API endpoint must have an integration test covering the success case and at least one error case (e.g. 404 Not Found, 409 Conflict).
- Tests use `pytest-asyncio` for async test functions and `mongomock-motor` for an in-memory MongoDB substitute.
- The `conftest.py` provides a `fresh_db` fixture that resets the test database before each test. Use it.
- Do not mock domain services to avoid writing fixtures. Use the in-memory store.

### Frontend

- Every new Pinia store action must have a unit test.
- API calls must be mocked at the HTTP boundary (vi.fn() on the fetch/axios layer), not by mocking store actions.
- Every new component should have at least a smoke test confirming it mounts without throwing.

See `TESTING.md` for the complete testing contract, coverage gates, and forbidden patterns.

---

## Architecture Decision Records (ADRs)

An ADR must be written when a decision:

- Introduces a new external dependency.
- Changes the data model in a way that affects multiple bounded contexts.
- Changes the deployment topology (new service, new port, new volume).
- Makes a technology choice where alternatives were seriously considered.
- Establishes a new cross-cutting convention (logging format, error shape, naming scheme).

ADRs live in `docs/adr/`. The filename convention is `NNNN-short-title.md` (zero-padded four-digit sequence number).

**ADR format:**

```markdown
# ADR-NNNN: <Title>

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-XXXX
**Date**: YYYY-MM-DD
**Deciders**: <names or roles>

## Context

<What is the situation that requires a decision? What forces are at play?>

## Decision

<What was decided?>

## Consequences

### Positive
- <benefit>

### Negative
- <drawback>

### Risks
- <risk>

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| ... | ... |
```

See `docs/adr/0001-use-mongodb-over-postgresql.md` for a complete example. Open a GitHub issue to discuss the proposed decision before writing the full ADR for significant architectural changes.
