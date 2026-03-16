"""Integration tests for auth refresh tokens, logout, and admin user management.

Covers the uncovered lines in auth/service.py and auth/router.py:
- Token refresh (rotation, reuse detection)
- Logout (single session, all sessions)
- GET /me endpoint
- Admin: list users, update role, disable/enable, delete
- Disabled user login rejection
- verify_token edge cases
"""

from __future__ import annotations

import pyotp
import pytest
from httpx import AsyncClient

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, username: str, password: str = "Password1234"
) -> dict:
    """Register a user, verify TOTP, and login. Returns the token response dict."""
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

    # Verify TOTP to activate 2FA
    verify = await client.post(
        "/api/v1/auth/totp/verify-setup",
        json={
            "username": username,
            "password": password,
            "code": pyotp.TOTP(secret).now(),
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


# ── Token Refresh ────────────────────────────────────────────────────────────


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh."""

    async def test_refresh_returns_new_token_pair(self, client: AsyncClient) -> None:
        """A valid refresh token yields a new access + refresh token pair."""
        tokens = await _register_and_login(client, "refreshuser1")
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["refresh_token"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["refresh_token"]
        # New tokens should differ from old ones
        assert data["refresh_token"] != tokens["refresh_token"]

    async def test_refresh_token_single_use(self, client: AsyncClient) -> None:
        """Using the same refresh token twice triggers reuse detection (401)."""
        tokens = await _register_and_login(client, "refreshuser2")
        old_refresh = tokens["refresh_token"]

        # First use — should succeed
        resp1 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_refresh,
            },
        )
        assert resp1.status_code == 200

        # Second use of the SAME old token — reuse detected
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_refresh,
            },
        )
        assert resp2.status_code == 401
        assert "reuse" in resp2.json()["detail"].lower()

    async def test_refresh_invalid_token_401(self, client: AsyncClient) -> None:
        """An invalid/garbage refresh token returns 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "not.a.valid.token",
            },
        )
        assert resp.status_code == 401

    async def test_refresh_with_access_token_401(self, client: AsyncClient) -> None:
        """Submitting an access token as a refresh token returns 401."""
        tokens = await _register_and_login(client, "refreshuser3")
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["access_token"],
            },
        )
        assert resp.status_code == 401


# ── Logout ──────────────────────────────────────────────────────────────────


class TestLogout:
    """Tests for POST /api/v1/auth/logout and /logout/all."""

    async def test_logout_revokes_session(self, client: AsyncClient) -> None:
        """After logout, the refresh token cannot be used."""
        tokens = await _register_and_login(client, "logoutuser1")

        resp = await client.post(
            "/api/v1/auth/logout",
            json={
                "refresh_token": tokens["refresh_token"],
            },
        )
        assert resp.status_code == 204

        # Refresh should fail
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["refresh_token"],
            },
        )
        assert resp2.status_code == 401

    async def test_logout_with_invalid_token_still_204(self, client: AsyncClient) -> None:
        """Logout with an invalid token is a no-op, still returns 204."""
        resp = await client.post(
            "/api/v1/auth/logout",
            json={
                "refresh_token": "garbage.token.here",
            },
        )
        assert resp.status_code == 204

    async def test_logout_all_revokes_all_sessions(self, client: AsyncClient) -> None:
        """POST /logout/all revokes all refresh tokens for the authenticated user."""
        tokens = await _register_and_login(client, "logoutall1")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        resp = await client.post("/api/v1/auth/logout/all", headers=headers)
        assert resp.status_code == 204

        # Refresh should fail
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["refresh_token"],
            },
        )
        assert resp2.status_code == 401

    async def test_logout_all_requires_auth(self, client: AsyncClient) -> None:
        """POST /logout/all without an auth token returns 401."""
        resp = await client.post("/api/v1/auth/logout/all")
        assert resp.status_code == 401


# ── GET /me ─────────────────────────────────────────────────────────────────


class TestMe:
    """Tests for GET /api/v1/auth/me."""

    async def test_me_returns_user_profile(self, client: AsyncClient) -> None:
        """GET /me with a valid access token returns the user's profile."""
        tokens = await _register_and_login(client, "meuser1")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser1"
        assert data["email"] == "meuser1@test.com"
        assert data["totp_enabled"] is True  # we verified TOTP

    async def test_me_without_auth_401(self, client: AsyncClient) -> None:
        """GET /me without an auth token returns 401."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ── Disabled user ───────────────────────────────────────────────────────────


class TestDisabledUser:
    """Login should be rejected for disabled accounts."""

    async def test_disabled_user_cannot_login(self, client: AsyncClient, test_db: object) -> None:
        """A disabled user gets 403 on login."""
        await _register_only(client, "disableduser", "Password1234")
        # Manually disable in DB
        await test_db["users"].update_one(  # type: ignore[index]
            {"username": "disableduser"},
            {"$set": {"disabled": True}},
        )
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "disableduser",
                "password": "Password1234",
            },
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()


class TestLoginReturnsRefreshToken:
    """Login (without TOTP) returns both access and refresh tokens."""

    async def test_login_returns_refresh_token(self, client: AsyncClient) -> None:
        """Login without TOTP enabled returns both tokens."""
        await _register_only(client, "loginrefuser")
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "loginrefuser",
                "password": "Password1234",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["refresh_token"]


# ── Admin user management ───────────────────────────────────────────────────


class TestAdminUserManagement:
    """Tests for admin-only user management endpoints."""

    async def test_list_users(self, client: AsyncClient, admin_headers: dict) -> None:
        """GET /users returns a list of all users."""
        await _register_only(client, "listuser1")
        resp = await client.get("/api/v1/auth/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert isinstance(data["users"], list)
        usernames = [u["username"] for u in data["users"]]
        assert "listuser1" in usernames

    async def test_list_users_requires_admin(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """GET /users with non-admin role returns 403."""
        resp = await client.get("/api/v1/auth/users", headers=analyst_headers)
        assert resp.status_code == 403

    async def test_update_user_role(
        self, client: AsyncClient, admin_headers: dict, test_db: object
    ) -> None:
        """PATCH /users/:username/role changes the user's role."""
        from domains.auth.service import get_password_hash

        # Seed user directly as viewer to avoid first-user auto-admin issues
        await test_db["users"].insert_one(  # type: ignore[index]
            {
                "username": "roleuser1",
                "email": "roleuser1@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "viewer",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.patch(
            "/api/v1/auth/users/roleuser1/role",
            json={"role": "analyst"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "analyst"

    async def test_update_role_nonexistent_user_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """PATCH /users/:username/role for a non-existent user returns 404."""
        resp = await client.patch(
            "/api/v1/auth/users/nosuchuser/role",
            json={"role": "analyst"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    async def test_disable_user(self, client: AsyncClient, super_admin_headers: dict) -> None:
        """PATCH /users/:username/disabled disables a user account."""
        # First registration gets super_admin via auto-promotion; register
        # a throwaway so the target user is a normal viewer.
        await _register_only(client, "firstuser_disable")
        await _register_only(client, "disableuser1")
        resp = await client.patch(
            "/api/v1/auth/users/disableuser1/disabled",
            json={"disabled": True},
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is True

    async def test_enable_user(self, client: AsyncClient, super_admin_headers: dict) -> None:
        """PATCH /users/:username/disabled can re-enable a user."""
        await _register_only(client, "firstuser_enable")
        await _register_only(client, "enableuser1")
        # Disable first
        await client.patch(
            "/api/v1/auth/users/enableuser1/disabled",
            json={"disabled": True},
            headers=super_admin_headers,
        )
        # Re-enable
        resp = await client.patch(
            "/api/v1/auth/users/enableuser1/disabled",
            json={"disabled": False},
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is False

    async def test_disable_nonexistent_user_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """PATCH /users/:username/disabled for a non-existent user returns 404."""
        resp = await client.patch(
            "/api/v1/auth/users/nosuchuser/disabled",
            json={"disabled": True},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    async def test_delete_user(
        self, client: AsyncClient, admin_headers: dict, test_db: object
    ) -> None:
        """DELETE /users/:username deletes the user."""
        from domains.auth.service import get_password_hash

        # Seed user directly as viewer to avoid first-user auto-admin issues
        await test_db["users"].insert_one(  # type: ignore[index]
            {
                "username": "deleteuser1",
                "email": "deleteuser1@test.com",
                "hashed_password": get_password_hash("Password1234"),
                "role": "viewer",
                "disabled": False,
                "totp_enabled": False,
            }
        )
        resp = await client.delete("/api/v1/auth/users/deleteuser1", headers=admin_headers)
        assert resp.status_code == 204

        # Verify user is soft-deleted (status=deleted, disabled=True)
        resp2 = await client.get("/api/v1/auth/users", headers=admin_headers)
        deleted = [u for u in resp2.json()["users"] if u["username"] == "deleteuser1"]
        assert len(deleted) == 1
        assert deleted[0]["status"] == "deleted"
        assert deleted[0]["disabled"] is True

    async def test_delete_nonexistent_user_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """DELETE /users/:username for a non-existent user returns 404."""
        resp = await client.delete("/api/v1/auth/users/nosuchuser", headers=admin_headers)
        assert resp.status_code == 404


# ── verify_token edge cases ─────────────────────────────────────────────────


class TestVerifyTokenEdgeCases:
    """Unit tests for verify_token edge cases."""

    def test_refresh_token_rejected_as_access(self) -> None:
        """verify_token must reject tokens with type='refresh'."""
        import jwt as pyjwt

        from config import get_settings
        from domains.auth.service import verify_token

        settings = get_settings()
        token = pyjwt.encode(
            {
                "sub": "user",
                "role": "viewer",
                "type": "refresh",
                "aud": "sentora-api",
                "iss": "sentora",
                "exp": 9999999999,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="access token"):
            verify_token(token)

    def test_token_missing_sub_rejected(self) -> None:
        """verify_token must reject tokens missing the 'sub' claim."""
        import jwt as pyjwt

        from config import get_settings
        from domains.auth.service import verify_token

        settings = get_settings()
        token = pyjwt.encode(
            {
                "role": "viewer",
                "type": "access",
                "aud": "sentora-api",
                "iss": "sentora",
                "exp": 9999999999,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="missing required"):
            verify_token(token)

    def test_token_missing_role_rejected(self) -> None:
        """verify_token must reject tokens missing the 'role' claim."""
        import jwt as pyjwt

        from config import get_settings
        from domains.auth.service import verify_token

        settings = get_settings()
        token = pyjwt.encode(
            {
                "sub": "user",
                "type": "access",
                "aud": "sentora-api",
                "iss": "sentora",
                "exp": 9999999999,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(ValueError, match="missing required"):
            verify_token(token)
