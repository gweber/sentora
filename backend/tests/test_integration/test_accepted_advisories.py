"""Accepted advisories — documented skip-marked placeholders.

These tests exist solely to document known, accepted low-severity risks
in the test suite. Each corresponds to an advisory from audit rounds
that was accepted with compensating controls.

Round 3 accepted advisories (6 total).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="Accepted: no per-account lockout, compensated by rate limiting + mandatory TOTP"
)
def test_account_lockout_after_failed_attempts() -> None:
    """Would verify account locks after N failed logins.

    Not implemented — rate limiting (10 req/min on /login, 5 req/min
    global) and mandatory TOTP 2FA are the compensating controls.
    """
    pass


@pytest.mark.skip(reason="Accepted: registration reveals usernames/emails, rate-limited at 5/5min")
def test_registration_username_enumeration() -> None:
    """Would verify that registration does not reveal whether a username exists.

    Not implemented — the 409 response is by design for UX. Compensated
    by aggressive rate limiting (5 registrations per 5 minutes per IP).
    """
    pass


@pytest.mark.skip(reason="Accepted advisory: no password reset flow (not yet implemented)")
def test_password_reset_flow() -> None:
    """Would verify a password reset email flow exists.

    Not implemented — password reset is a planned feature. Current
    workaround: admin can delete+recreate accounts, or users can use SSO.
    """
    pass


@pytest.mark.skip(
    reason="Accepted advisory: TOTP secret stored as plaintext — standard for TOTP verification"
)
def test_totp_secret_encrypted_at_rest() -> None:
    """Would verify TOTP secrets are encrypted at rest in MongoDB.

    Not implemented — TOTP verification requires the raw base32 secret
    to compute the current code. This is standard practice (Google
    Authenticator, Authy, etc.). MongoDB encryption-at-rest is the
    compensating control.
    """
    pass


@pytest.mark.skip(
    reason="Accepted: in-memory rate limiter per-worker, upgrade to Redis when multi-worker"
)
def test_distributed_rate_limiting() -> None:
    """Would verify rate limits are shared across multiple workers.

    Not implemented — the current in-memory RateLimiter is per-process.
    Documented limitation: in multi-worker deployments, each worker
    maintains its own counters. Redis-backed rate limiting is planned.
    """
    pass


@pytest.mark.skip(reason="Accepted advisory: GitHub Actions use tag refs not SHA pins")
def test_github_actions_sha_pinned() -> None:
    """Would verify all GitHub Actions use SHA-pinned references.

    Not implemented — using tag refs (e.g., actions/checkout@v4) is the
    project's current practice. SHA pinning is recommended for supply-chain
    security but adds maintenance overhead for this project's threat model.
    """
    pass
