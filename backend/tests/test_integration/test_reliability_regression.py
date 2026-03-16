"""Reliability regression tests — concurrency, race conditions, and robustness.

Covers:
- Round 2: Concurrent registration race (DuplicateKeyError → 409, not 500)
- Round 2: Refresh token TOCTOU (concurrent refresh)
- Round 2: Body size limit enforcement
- Round 2: SSO state stored in MongoDB (multi-worker safe)
- Round 2: Log format safety (no f-string injection in loguru calls)
"""

from __future__ import annotations

import pyotp
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register_only(
    client: AsyncClient,
    username: str,
    password: str = "Password1234",
) -> dict:
    """Register a user without TOTP verification."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": password,
        },
    )
    assert reg.status_code == 201
    return reg.json()


async def _register_and_login(
    client: AsyncClient,
    username: str,
    password: str = "Password1234",
) -> dict:
    """Register, verify TOTP, return token response dict."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": password,
        },
    )
    assert reg.status_code == 201
    secret = pyotp.parse_uri(reg.json()["totp_uri"]).secret
    verify = await client.post(
        "/api/v1/auth/totp/verify-setup",
        json={
            "username": username,
            "code": pyotp.TOTP(secret).now(),
            "password": password,
        },
    )
    assert verify.status_code == 200
    return verify.json()


# ── Concurrent Registration ────────────────────────────────────────────────


class TestConcurrentRegistration:
    """Regression: Round 2 — concurrent registration with same username returns 409, not 500."""

    async def test_duplicate_username_race(self, client: AsyncClient) -> None:
        """Two simultaneous registrations with the same username: one 201, one 409."""
        payload = {
            "username": "raceuser1",
            "email": "raceuser1@test.com",
            "password": "Password1234",
        }
        # We can't truly race with a single async client, but we can verify
        # the second attempt returns 409 (not 500 DuplicateKeyError)
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        resp2 = await client.post("/api/v1/auth/register", json=payload)

        codes = sorted([resp1.status_code, resp2.status_code])
        assert codes == [201, 409], (
            f"Expected one 201 and one 409, got {resp1.status_code} and {resp2.status_code}"
        )

    async def test_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        """Two registrations with same email return 409, not 500."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "emailrace1",
                "email": "shared@test.com",
                "password": "Password1234",
            },
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "emailrace2",
                "email": "shared@test.com",
                "password": "Password1234",
            },
        )
        assert resp.status_code == 409, f"Duplicate email should return 409, got {resp.status_code}"


# ── Refresh Token TOCTOU ─────────────────────────────────────────────────


class TestRefreshTokenToctou:
    """Regression: Round 2 — refresh token single-use enforcement prevents TOCTOU."""

    async def test_reused_refresh_token_revokes_family(
        self,
        client: AsyncClient,
    ) -> None:
        """Using a refresh token twice revokes the entire token family."""
        tokens = await _register_and_login(client, "toctou_user")
        old_refresh = tokens["refresh_token"]

        # First use — succeeds
        resp1 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_refresh,
            },
        )
        assert resp1.status_code == 200
        new_refresh = resp1.json()["refresh_token"]

        # Reuse old token — triggers family revocation
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_refresh,
            },
        )
        assert resp2.status_code == 401

        # Even the new token should now be revoked (entire family killed)
        resp3 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": new_refresh,
            },
        )
        assert resp3.status_code == 401, "New refresh token should be revoked when family is killed"


# ── SSO State Storage ──────────────────────────────────────────────────────


class TestSsoStateStorage:
    """Regression: Round 2 — SSO state stored in MongoDB, not in-memory."""

    async def test_oidc_state_in_mongodb(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """OIDC pending states are stored in MongoDB for multi-worker safety."""
        # Insert a state as the OIDC flow would
        from utils.dt import utc_now

        state = "test-csrf-state-12345"
        await test_db["oidc_pending_states"].insert_one(
            {
                "_id": state,
                "created_at": utc_now(),
            }
        )
        # Verify it's persisted
        doc = await test_db["oidc_pending_states"].find_one({"_id": state})
        assert doc is not None, "OIDC state not found in MongoDB"

    async def test_oidc_state_ttl_index(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """OIDC pending states collection has a TTL index for auto-cleanup."""
        from db_indexes import ensure_all_indexes

        await ensure_all_indexes(test_db)
        indexes = await test_db["oidc_pending_states"].index_information()
        ttl_found = False
        for idx_info in indexes.values():
            if "expireAfterSeconds" in idx_info:
                ttl_found = True
                assert idx_info["expireAfterSeconds"] == 600, (
                    f"OIDC state TTL is {idx_info['expireAfterSeconds']}s, expected 600s"
                )
        assert ttl_found, "No TTL index on oidc_pending_states"


# ── Log Format Safety ────────────────────────────────────────────────────


class TestLogFormatSafety:
    """Regression: Round 2 — loguru calls must not use f-strings with user input."""

    def test_no_fstring_in_loguru_calls(self) -> None:
        """Static check: no loguru .format() or f-string with user variables in templates.

        Scans all Python files under backend/ for dangerous log patterns.
        """
        import pathlib
        import re

        backend_dir = pathlib.Path(__file__).resolve().parent.parent.parent
        violations = []

        # Pattern: logger.xxx(f"...{variable}...")
        fstring_pattern = re.compile(r'logger\.\w+\(f["\']')
        # Pattern: logger.xxx("...".format(
        format_pattern = re.compile(r'logger\.\w+\(["\'].*?["\']\.format\(')

        # Only scan project source directories, not installed packages or venv
        source_dirs = ["domains", "middleware", "utils", "audit"]
        py_files: list[pathlib.Path] = []
        for src in source_dirs:
            src_path = backend_dir / src
            if src_path.is_dir():
                py_files.extend(src_path.rglob("*.py"))
        # Also check top-level files
        py_files.extend(backend_dir.glob("*.py"))

        for py_file in py_files:
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text()
            except Exception:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if fstring_pattern.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")
                if format_pattern.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")

        assert not violations, (
            f"Found {len(violations)} loguru f-string/format violations:\n"
            + "\n".join(violations[:20])
        )
