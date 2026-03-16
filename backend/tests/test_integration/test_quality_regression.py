"""Code quality regression tests — dead code, state management, error handling.

Covers:
- Round 2: OIDC error responses don't leak internal details
- Round 2: Error handlers return structured JSON, not stack traces
- Round 2: Password not exposed in user list response
"""

from __future__ import annotations

from httpx import AsyncClient

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


# ── Credential Safety ──────────────────────────────────────────────────────


class TestCredentialSafety:
    """Regression: Round 2 — sensitive data never appears in API responses."""

    async def test_user_list_excludes_password_hash(
        self,
        client: AsyncClient,
        admin_headers: dict,
    ) -> None:
        """GET /users must not return hashed_password or totp_secret fields."""
        await _register_only(client, "safe_user")
        resp = await client.get("/api/v1/auth/users", headers=admin_headers)
        assert resp.status_code == 200
        for user in resp.json()["users"]:
            assert "hashed_password" not in user, "Password hash leaked in user list"
            assert "totp_secret" not in user, "TOTP secret leaked in user list"
            assert "password" not in user, "Plain password leaked in user list"

    async def test_me_endpoint_excludes_password(
        self,
        client: AsyncClient,
    ) -> None:
        """GET /me must not return password or totp_secret."""
        import pyotp

        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "safe_me_user",
                "email": "safe_me@test.com",
                "password": "Password1234",
            },
        )
        secret = pyotp.parse_uri(reg.json()["totp_uri"]).secret
        verify = await client.post(
            "/api/v1/auth/totp/verify-setup",
            json={
                "username": "safe_me_user",
                "code": pyotp.TOTP(secret).now(),
                "password": "Password1234",
            },
        )
        headers = {"Authorization": f"Bearer {verify.json()['access_token']}"}

        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "hashed_password" not in data
        assert "totp_secret" not in data
        assert "password" not in data


# ── Error Handler Safety ───────────────────────────────────────────────────


class TestErrorHandlerSafety:
    """Regression: Round 2 — error responses don't leak internals."""

    async def test_404_returns_structured_json(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """A 404 on a nonexistent resource returns structured JSON, not HTML or stack trace."""
        resp = await client.get("/api/v1/agents/nonexistent-id-12345", headers=admin_headers)
        assert resp.status_code == 404
        data = resp.json()
        # Should NOT contain stack traces or file paths
        response_text = str(data)
        assert "Traceback" not in response_text
        assert ".py" not in response_text or "file" not in response_text.lower()

    async def test_unhandled_validation_error_structured(self, client: AsyncClient) -> None:
        """A Pydantic validation error returns structured 422, not 500."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": 12345,  # wrong type
                "password": "anything",
            },
        )
        # Should be 422 (validation), not 500
        assert resp.status_code == 422


# ── OIDC Error Leak Prevention ─────────────────────────────────────────────


class TestOidcErrorLeakPrevention:
    """Regression: Round 2 — OIDC errors don't expose internal details."""

    async def test_oidc_callback_error_no_secrets(self, client: AsyncClient) -> None:
        """OIDC callback with error param returns generic message, not secrets."""
        resp = await client.get(
            "/api/v1/auth/oidc/callback",
            params={
                "code": "fake-code",
                "state": "fake-state",
                "error": "access_denied",
                "error_description": "User denied access",
            },
        )
        # May be 404 (OIDC not enabled) or 401 (error handled)
        assert resp.status_code in (401, 404)
        body = resp.text
        # Should NOT contain internal paths, secrets, or dependency versions
        assert "client_secret" not in body.lower()
        assert "jwt_secret" not in body.lower()
        assert "traceback" not in body.lower()


# ── First-User Auto-Admin Safety ──────────────────────────────────────────


class TestFirstUserAutoAdmin:
    """Regression: Round 2 — first user is admin, subsequent users are viewer."""

    async def test_first_user_gets_admin(self, client: AsyncClient) -> None:
        """The first registered user is auto-promoted to admin."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "first_admin",
                "email": "first@test.com",
                "password": "Password1234",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["user"]["role"] == "admin"

    async def test_register_request_does_not_accept_role_field(
        self,
        client: AsyncClient,
    ) -> None:
        """Regression: Round 2 — register request cannot specify a role.

        The RegisterRequest DTO does not have a role field, so even if an
        attacker sends a role in the JSON body, it is silently ignored.
        """
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "role_inject_user",
                "email": "role_inject@test.com",
                "password": "Password1234",
                "role": "super_admin",  # should be ignored
            },
        )
        assert resp.status_code == 201
        # First user gets admin via server logic, never via client input
        # The key test: the role field in the request was ignored
        assert resp.json()["user"]["role"] == "admin"  # auto-admin for first user
