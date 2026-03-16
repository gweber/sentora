"""Security regression tests — audit logging for security-sensitive events.

Covers:
- Round 3: Audit log record created for login, failed login, registration
- Round 3: Audit log record created for TOTP setup and verification
- Round 3: Audit log record created for role change, user disable, user delete
- Round 3: Audit log record created for logout
- Round 3: Audit log TTL index exists (90 days)
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


# ── Audit Logging Tests ────────────────────────────────────────────────────


class TestAuditLogRegistration:
    """Regression: Round 3 — registration creates an audit log entry."""

    async def test_registration_audit_entry(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """POST /register creates an audit entry with action 'auth.registered'."""
        await _register_only(client, "audit_reg_user")
        entry = await test_db["audit_log"].find_one({"action": "auth.registered"})
        assert entry is not None, "No audit entry for auth.registered"
        assert entry["domain"] == "auth"
        assert "audit_reg_user" in entry.get("summary", "")


class TestAuditLogLogin:
    """Regression: Round 3 — login events are recorded in audit log."""

    async def test_successful_login_audit(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Successful login creates an audit entry with action 'auth.login'."""
        await _register_only(client, "audit_login_ok")
        await client.post(
            "/api/v1/auth/login",
            json={
                "username": "audit_login_ok",
                "password": "Password1234",
            },
        )
        entry = await test_db["audit_log"].find_one(
            {
                "action": "auth.login",
                "actor": "audit_login_ok",
            }
        )
        assert entry is not None, "No audit entry for successful login"
        assert entry["status"] == "success"

    async def test_failed_login_audit(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Failed login creates an audit entry with action 'auth.login_failed'."""
        await _register_only(client, "audit_login_fail")
        await client.post(
            "/api/v1/auth/login",
            json={
                "username": "audit_login_fail",
                "password": "WrongPassword1",
            },
        )
        entry = await test_db["audit_log"].find_one(
            {
                "action": "auth.login_failed",
            }
        )
        assert entry is not None, "No audit entry for failed login"
        assert entry["status"] == "failure"


class TestAuditLogTotp:
    """Regression: Round 3 — TOTP setup events are recorded."""

    async def test_totp_activated_audit(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """TOTP verification creates an audit entry with action 'auth.totp_activated'."""
        await _register_and_login(client, "audit_totp_user")
        entry = await test_db["audit_log"].find_one({"action": "auth.totp_activated"})
        assert entry is not None, "No audit entry for TOTP activation"
        assert "audit_totp_user" in entry.get("summary", "")


class TestAuditLogRoleChange:
    """Regression: Round 3 — role changes are recorded in audit log."""

    async def test_role_change_audit(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Changing a user's role creates an audit entry."""
        from domains.auth.service import get_password_hash

        await test_db["users"].insert_one(
            {
                "username": "audit_role_user",
                "email": "audit_role@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "viewer",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.patch(
            "/api/v1/auth/users/audit_role_user/role",
            json={"role": "analyst"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        entry = await test_db["audit_log"].find_one({"action": "auth.role_changed"})
        assert entry is not None, "No audit entry for role change"
        assert entry["details"]["new_role"] == "analyst"
        assert entry["details"]["target"] == "audit_role_user"


class TestAuditLogUserDisable:
    """Regression: Round 3 — user disable events are recorded."""

    async def test_user_disable_audit(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Disabling a user creates an audit entry."""
        from domains.auth.service import get_password_hash

        await test_db["users"].insert_one(
            {
                "username": "audit_disable_user",
                "email": "audit_disable@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "viewer",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.patch(
            "/api/v1/auth/users/audit_disable_user/disabled",
            json={"disabled": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        entry = await test_db["audit_log"].find_one({"action": "auth.user_disabled"})
        assert entry is not None, "No audit entry for user disable"


class TestAuditLogUserDelete:
    """Regression: Round 3 — user deletion events are recorded."""

    async def test_user_delete_audit(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Deleting a user creates an audit entry."""
        from domains.auth.service import get_password_hash

        await test_db["users"].insert_one(
            {
                "username": "audit_delete_user",
                "email": "audit_delete@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "viewer",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.delete(
            "/api/v1/auth/users/audit_delete_user",
            headers=admin_headers,
        )
        assert resp.status_code == 204
        entry = await test_db["audit_log"].find_one({"action": "auth.user_deleted"})
        assert entry is not None, "No audit entry for user delete"
        assert "audit_delete_user" in entry.get("summary", "")


class TestAuditLogLogout:
    """Regression: Round 3 — logout events are recorded."""

    async def test_logout_audit(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Logging out creates an audit entry."""
        tokens = await _register_and_login(client, "audit_logout_user")
        await client.post(
            "/api/v1/auth/logout",
            json={
                "refresh_token": tokens["refresh_token"],
            },
        )
        entry = await test_db["audit_log"].find_one({"action": "auth.logout"})
        assert entry is not None, "No audit entry for logout"


class TestAuditLogTtlIndex:
    """Regression: Round 3 — audit_log collection has a TTL index for auto-cleanup."""

    async def test_audit_log_ttl_index_exists(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """The audit_log collection must have a TTL index on created_at."""
        from db_indexes import ensure_all_indexes

        await ensure_all_indexes(test_db)
        indexes = await test_db["audit_log"].index_information()
        ttl_found = False
        for idx_info in indexes.values():
            if "expireAfterSeconds" in idx_info:
                ttl_found = True
                # 90 days in seconds
                expected_ttl = 90 * 24 * 60 * 60
                assert idx_info["expireAfterSeconds"] == expected_ttl, (
                    f"TTL index is {idx_info['expireAfterSeconds']}s, expected {expected_ttl}s"
                )
                break
        assert ttl_found, "No TTL index found on audit_log collection"
