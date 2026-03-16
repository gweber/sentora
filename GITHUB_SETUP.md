# GitHub Repository Setup Checklist

Recommended settings for the `gweber/sentora` repository after the initial push.

---

## Repository Settings

- [ ] **Description**: "Software fingerprint-based asset classification for SentinelOne EDR environments."
- [ ] **Topics/Tags**: `sentinelone`, `asset-management`, `software-inventory`, `classification`, `fastapi`, `vue`, `mongodb`, `security`, `compliance`, `edr`
- [ ] **Website**: Set to the repo's GitHub Pages URL or leave blank
- [ ] **Social preview image**: Upload a branded card (1280x640 recommended) — or flag as TODO

---

## Branch Protection — `main`

Go to **Settings > Branches > Add branch protection rule** for `main`:

- [x] Require a pull request before merging
  - [x] Require at least **1** approval
  - [x] Dismiss stale pull request approvals when new commits are pushed
- [x] Require status checks to pass before merging
  - Required checks: `backend-lint`, `backend-test`, `frontend-typecheck`, `frontend-test`, `docker-build`
- [x] Require branches to be up to date before merging
- [x] Do not allow force pushes
- [x] Do not allow deletions

---

## Dependabot

Create `.github/dependabot.yml` (already included in the repo if following the full setup):

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /backend
    schedule:
      interval: weekly
    open-pull-requests-limit: 10
    labels:
      - dependencies
      - python

  - package-ecosystem: npm
    directory: /frontend
    schedule:
      interval: weekly
    open-pull-requests-limit: 10
    labels:
      - dependencies
      - javascript

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    labels:
      - dependencies
      - ci
```

---

## GitHub Issues

- [x] Enable Issues
- [x] Issue templates are already configured in `.github/ISSUE_TEMPLATE/`:
  - `bug_report.yml` — structured bug reports with component dropdown
  - `feature_request.yml` — feature requests with use case context
  - `security_vulnerability.yml` — redirects to SECURITY.md

---

## GitHub Actions

- [x] CI workflow (`.github/workflows/ci.yml`) — runs on push to `main` and on PRs
- [x] Security scan workflow (`.github/workflows/security-scan.yml`) — weekly + on push to `main`

---

## Secrets (if using CI with real S1 integration tests)

If you want CI to run integration tests against a real SentinelOne instance (not required — CI uses placeholder tokens by default):

- `S1_BASE_URL` — your S1 management console URL
- `S1_API_TOKEN` — a read-only scoped API token

These should be added as **repository secrets** under **Settings > Secrets and variables > Actions**.

---

## Additional Recommendations

- [ ] Enable **Discussions** if you want a community Q&A forum
- [ ] Enable **GitHub Pages** for hosting the `docs/` directory (optional)
- [ ] Set up **CODEOWNERS** — already configured in `.github/CODEOWNERS`
- [ ] Pin important issues (getting started, known limitations) after the first release
