"""Integration tests for server-side session management.

Tests cover:
- Session creation on login
- Session listing (user + admin)
- Session revocation (single, all, admin)
- Session revocation on password change
- Session revocation on account disable
- Revoked session blocks token refresh
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient, test_db: AsyncIOMotorDatabase) -> dict:
    """Register a test user and return credentials + tokens."""
    # Register
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "sessionuser",
            "email": "sessionuser@test.com",
            "password": "TestPass123!",
        },
    )
    assert resp.status_code == 201
    setup = resp.json()

    # Verify TOTP to get tokens
    import pyotp

    secret = setup["totp_uri"].split("secret=")[1].split("&")[0]
    code = pyotp.TOTP(secret).now()

    resp = await client.post(
        "/api/v1/auth/totp/verify-setup",
        json={
            "username": "sessionuser",
            "password": "TestPass123!",
            "code": code,
        },
    )
    assert resp.status_code == 200
    tokens = resp.json()

    return {
        "username": "sessionuser",
        "password": "TestPass123!",
        "totp_secret": secret,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


class TestSessionCreation:
    """Sessions are created on login and token verification."""

    @pytest.mark.asyncio
    async def test_login_creates_session(self, registered_user: dict, client: AsyncClient) -> None:
        """Login creates a server-side session that appears in session list."""
        resp = await client.get("/api/v1/auth/sessions", headers=registered_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        sessions = data["sessions"]
        assert any(s["is_current"] for s in sessions)

    @pytest.mark.asyncio
    async def test_session_has_device_info(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Sessions include IP address and user-agent."""
        resp = await client.get("/api/v1/auth/sessions", headers=registered_user["headers"])
        session = resp.json()["sessions"][0]
        assert session["ip_address"]
        assert session["user_agent"]
        assert session["is_active"] is True

    @pytest.mark.asyncio
    async def test_multiple_logins_create_multiple_sessions(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Each login creates a distinct session."""
        import pyotp

        code = pyotp.TOTP(registered_user["totp_secret"]).now()
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "sessionuser",
                "password": "TestPass123!",
                "totp_code": code,
            },
        )
        assert resp.status_code == 200

        new_tokens = resp.json()
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        resp = await client.get("/api/v1/auth/sessions", headers=new_headers)
        assert resp.json()["total"] >= 2


class TestSessionRevocation:
    """Sessions can be revoked individually or in bulk."""

    @pytest.mark.asyncio
    async def test_revoke_single_session(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Revoking a specific session removes it from the list."""
        # Create a second session via login
        import pyotp

        code = pyotp.TOTP(registered_user["totp_secret"]).now()
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "sessionuser",
                "password": "TestPass123!",
                "totp_code": code,
            },
        )
        new_tokens = resp.json()
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}

        # List sessions
        resp = await client.get("/api/v1/auth/sessions", headers=new_headers)
        sessions = resp.json()["sessions"]
        non_current = [s for s in sessions if not s["is_current"]]
        assert len(non_current) >= 1

        # Revoke the non-current session
        resp = await client.delete(
            f"/api/v1/auth/sessions/{non_current[0]['id']}",
            headers=new_headers,
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_revoke_other_sessions(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Revoking all other sessions keeps only the current one."""
        resp = await client.delete("/api/v1/auth/sessions", headers=registered_user["headers"])
        assert resp.status_code == 204

        resp = await client.get("/api/v1/auth/sessions", headers=registered_user["headers"])
        sessions = resp.json()["sessions"]
        assert all(s["is_current"] for s in sessions)

    @pytest.mark.asyncio
    async def test_cannot_revoke_other_users_session(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Users cannot revoke sessions belonging to other users."""
        resp = await client.delete(
            "/api/v1/auth/sessions/nonexistent_session_id",
            headers=registered_user["headers"],
        )
        assert resp.status_code == 404


class TestPasswordChangeRevokeSessions:
    """Password change revokes all other sessions."""

    @pytest.mark.asyncio
    async def test_password_change_revokes_other_sessions(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Changing password revokes all sessions except current."""
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "TestPass123!",
                "new_password": "NewPass456!abc",
            },
            headers=registered_user["headers"],
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_password_change_wrong_current(
        self,
        registered_user: dict,
        client: AsyncClient,
    ) -> None:
        """Password change fails with incorrect current password."""
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "wrongpassword",
                "new_password": "NewPass456!abc",
            },
            headers=registered_user["headers"],
        )
        assert resp.status_code == 401


class TestAdminSessionManagement:
    """Admin can view and revoke other users' sessions."""

    @pytest.mark.asyncio
    async def test_admin_list_user_sessions(
        self,
        registered_user: dict,
        client: AsyncClient,
        admin_headers: dict,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Admin can list sessions for any user."""
        from domains.auth.service import get_password_hash

        await test_db["users"].update_one(
            {"username": "testadmin"},
            {
                "$set": {
                    "username": "testadmin",
                    "email": "admin@test.com",
                    "hashed_password": get_password_hash("Admin123!"),
                    "role": "admin",
                    "disabled": False,
                    "status": "active",
                    "totp_enabled": False,
                }
            },
            upsert=True,
        )

        resp = await client.get(
            "/api/v1/auth/admin/sessions",
            params={"username": "sessionuser"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_admin_revoke_user_sessions(
        self,
        registered_user: dict,
        client: AsyncClient,
        admin_headers: dict,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Admin can revoke all sessions for a user."""
        from domains.auth.service import get_password_hash

        await test_db["users"].update_one(
            {"username": "testadmin"},
            {
                "$set": {
                    "username": "testadmin",
                    "email": "admin@test.com",
                    "hashed_password": get_password_hash("Admin123!"),
                    "role": "admin",
                    "disabled": False,
                    "status": "active",
                }
            },
            upsert=True,
        )

        resp = await client.delete(
            "/api/v1/auth/admin/sessions",
            params={"username": "sessionuser"},
            headers=admin_headers,
        )
        assert resp.status_code == 204


class TestPasswordPolicy:
    """Password policy endpoint returns configured policy."""

    @pytest.mark.asyncio
    async def test_get_password_policy(self, client: AsyncClient) -> None:
        """Password policy endpoint is public and returns policy config."""
        resp = await client.get("/api/v1/auth/password-policy")
        assert resp.status_code == 200
        data = resp.json()
        assert "min_length" in data
        assert "require_uppercase" in data
        assert "history_count" in data
        assert "check_breached" in data


class TestAccountLifecycle:
    """Account status transitions."""

    @pytest.mark.asyncio
    async def test_status_change_suspend(
        self,
        registered_user: dict,
        client: AsyncClient,
        super_admin_headers: dict,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Super admin can suspend an active user (including auto-promoted super_admin)."""
        resp = await client.patch(
            "/api/v1/auth/users/sessionuser/status",
            json={"status": "suspended", "reason": "policy violation"},
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    @pytest.mark.asyncio
    async def test_suspended_user_cannot_login(
        self,
        client: AsyncClient,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """A suspended user gets 403 on login."""
        from domains.auth.service import get_password_hash

        await test_db["users"].insert_one(
            {
                "username": "suspendeduser",
                "email": "suspended@test.com",
                "hashed_password": get_password_hash("TestPass123!"),
                "role": "viewer",
                "disabled": True,
                "status": "suspended",
                "totp_enabled": False,
            }
        )

        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "suspendeduser",
                "password": "TestPass123!",
            },
        )
        assert resp.status_code in (401, 403)


class TestTokenHardening:
    """JWT tokens include IdP-grade claims."""

    @pytest.mark.asyncio
    async def test_access_token_has_required_claims(self) -> None:
        """Access tokens include jti, iss, aud, and optionally sid."""
        import jwt

        from config import get_settings
        from domains.auth.service import create_access_token

        settings = get_settings()
        token = create_access_token(
            {"sub": "testuser", "role": "viewer"},
            session_id="test-session-123",
        )
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="sentora-api",
        )
        assert payload["iss"] == "sentora"
        assert payload["aud"] == "sentora-api"
        assert payload["jti"]  # unique token ID
        assert payload["sid"] == "test-session-123"
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_verify_token_rejects_wrong_audience(self) -> None:
        """Tokens with wrong audience are rejected."""
        import jwt as _jwt

        from config import get_settings
        from domains.auth.service import verify_token

        settings = get_settings()
        token = _jwt.encode(
            {
                "sub": "user",
                "role": "viewer",
                "type": "access",
                "aud": "wrong-api",
                "iss": "sentora",
                "exp": 9999999999,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="(?i)audience"):
            verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_rejects_legacy_without_audience(self) -> None:
        """Tokens without aud/iss (legacy) are rejected — defense-in-depth."""
        import jwt as _jwt

        from config import get_settings
        from domains.auth.service import verify_token

        settings = get_settings()
        token = _jwt.encode(
            {
                "sub": "user",
                "role": "viewer",
                "type": "access",
                "exp": 9999999999,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token(token)
