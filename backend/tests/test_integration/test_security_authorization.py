"""Security regression tests — authorization, role escalation, and privilege guards.

Covers:
- Round 2: Role escalation prevention (viewer → admin, admin → super_admin)
- Round 2: Self-deletion guard
- Round 2: super_admin deletion protection
- Round 2: Audit log access control (viewer cannot read audit)
"""

from __future__ import annotations

import pyotp
from httpx import AsyncClient

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, username: str, password: str = "Password1234"
) -> dict:
    """Register a user, verify TOTP, return token response dict."""
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


async def _register_only(
    client: AsyncClient, username: str, password: str = "Password1234"
) -> dict:
    """Register a user without TOTP verification. Returns registration response."""
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


# ── Role Escalation ─────────────────────────────────────────────────────────


class TestRoleEscalation:
    """Regression: Round 2 — non-admin users cannot escalate their own role."""

    async def test_viewer_cannot_update_own_role_to_admin(
        self,
        client: AsyncClient,
        viewer_headers: dict,
    ) -> None:
        """A viewer attempting to change a user's role gets 403."""
        resp = await client.patch(
            "/api/v1/auth/users/testviewer/role",
            json={"role": "admin"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_analyst_cannot_update_role(
        self,
        client: AsyncClient,
        analyst_headers: dict,
    ) -> None:
        """An analyst attempting to change a user's role gets 403."""
        resp = await client.patch(
            "/api/v1/auth/users/someuser/role",
            json={"role": "admin"},
            headers=analyst_headers,
        )
        assert resp.status_code == 403

    async def test_admin_cannot_escalate_to_super_admin(
        self,
        client: AsyncClient,
        admin_headers: dict,
    ) -> None:
        """Regression: Round 2 — admin cannot set any user to super_admin."""
        await _register_only(client, "escalation_target")
        resp = await client.patch(
            "/api/v1/auth/users/escalation_target/role",
            json={"role": "super_admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 403, "Admin must not be able to escalate to super_admin"

    async def test_admin_cannot_self_escalate_to_super_admin(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: object,
    ) -> None:
        """Regression: Round 2 — admin cannot set own role to super_admin."""
        from domains.auth.service import get_password_hash

        # Seed the testadmin user so the endpoint can find them
        await test_db["users"].insert_one(  # type: ignore[index]
            {
                "username": "testadmin",
                "email": "testadmin@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "admin",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.patch(
            "/api/v1/auth/users/testadmin/role",
            json={"role": "super_admin"},
            headers=admin_headers,
        )
        # Both 400 and 403 indicate escalation was blocked
        assert resp.status_code in (400, 403), (
            f"Expected 400 or 403 for self-escalation, got {resp.status_code}"
        )
        assert resp.status_code != 200, "Self-escalation must not succeed"

    async def test_role_unchanged_after_failed_escalation(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: object,
    ) -> None:
        """After a blocked escalation attempt, the user's role remains unchanged."""
        from domains.auth.service import get_password_hash

        # Seed user directly as viewer to avoid first-user auto-admin
        await test_db["users"].insert_one(  # type: ignore[index]
            {
                "username": "role_check_user",
                "email": "role_check@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "viewer",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        # Attempt escalation (should fail)
        await client.patch(
            "/api/v1/auth/users/role_check_user/role",
            json={"role": "super_admin"},
            headers=admin_headers,
        )
        # Verify role is still viewer
        doc = await test_db["users"].find_one({"username": "role_check_user"})  # type: ignore[index]
        assert doc["role"] == "viewer"


# ── Self-Deletion Guard ────────────────────────────────────────────────────


class TestSelfDeletionGuard:
    """Regression: Round 2 — users cannot delete their own account."""

    async def test_admin_cannot_delete_self(
        self,
        client: AsyncClient,
    ) -> None:
        """An admin calling DELETE on their own username gets 400."""
        tokens = await _register_and_login(client, "selfdeleteadmin")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        resp = await client.delete(
            "/api/v1/auth/users/selfdeleteadmin",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "own account" in resp.json()["detail"].lower()


# ── Super Admin Protection ─────────────────────────────────────────────────


class TestSuperAdminProtection:
    """Regression: Round 2 — regular admin cannot delete super_admin users."""

    async def test_admin_cannot_delete_super_admin(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: object,
    ) -> None:
        """Admin attempting to delete a super_admin user gets 403."""
        # Create a super_admin user in the DB
        from domains.auth.service import get_password_hash

        await test_db["users"].insert_one(  # type: ignore[index]
            {
                "username": "protected_sa",
                "email": "sa@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "super_admin",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.delete(
            "/api/v1/auth/users/protected_sa",
            headers=admin_headers,
        )
        assert resp.status_code == 403
        assert "super_admin" in resp.json()["detail"].lower()

    async def test_super_admin_can_delete_super_admin(
        self,
        client: AsyncClient,
        super_admin_headers: dict,
        test_db: object,
    ) -> None:
        """super_admin can delete another super_admin."""
        from domains.auth.service import get_password_hash

        await test_db["users"].insert_one(  # type: ignore[index]
            {
                "username": "deletable_sa",
                "email": "deletable_sa@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "super_admin",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.delete(
            "/api/v1/auth/users/deletable_sa",
            headers=super_admin_headers,
        )
        assert resp.status_code == 204


# ── Audit Log Access Control ────────────────────────────────────────────────


class TestAuditLogAccessControl:
    """Regression: Round 3 — audit log requires analyst or admin role."""

    async def test_viewer_cannot_access_audit_log(
        self,
        client: AsyncClient,
        viewer_headers: dict,
    ) -> None:
        """A viewer attempting to read the audit log gets 403."""
        resp = await client.get("/api/v1/audit/", headers=viewer_headers)
        assert resp.status_code == 403

    async def test_analyst_can_access_audit_log(
        self,
        client: AsyncClient,
        analyst_headers: dict,
    ) -> None:
        """An analyst can access the audit log."""
        resp = await client.get("/api/v1/audit/", headers=analyst_headers)
        assert resp.status_code == 200

    async def test_admin_can_access_audit_log(
        self,
        client: AsyncClient,
        admin_headers: dict,
    ) -> None:
        """An admin can access the audit log."""
        resp = await client.get("/api/v1/audit/", headers=admin_headers)
        assert resp.status_code == 200
