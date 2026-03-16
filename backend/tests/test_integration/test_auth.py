"""Integration tests for the auth domain.

Tests cover registration, login, TOTP 2FA, JWT token creation/verification,
and password hashing.
"""

from __future__ import annotations

from httpx import AsyncClient


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    async def test_register_creates_user_with_totp(self, client: AsyncClient) -> None:
        """A new user can be registered and returns 201 with TOTP setup data."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "Securepassword123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        # Response is TotpSetupResponse with nested user
        assert data["user"]["username"] == "testuser"
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["disabled"] is False
        assert data["user"]["totp_enabled"] is False
        # TOTP setup data present
        assert "totp_uri" in data
        assert data["totp_uri"].startswith("otpauth://totp/")
        assert "qr_code_svg" in data
        assert "<svg" in data["qr_code_svg"].lower()

    async def test_first_user_is_admin(self, client: AsyncClient) -> None:
        """The very first registered user is auto-promoted to admin."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "firstuser",
                "email": "first@example.com",
                "password": "Securepassword123",
            },
        )
        assert response.status_code == 201
        assert response.json()["user"]["role"] == "admin"

    async def test_second_user_is_viewer(self, client: AsyncClient) -> None:
        """Subsequent users default to viewer role."""
        # First user (admin)
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "firstadmin",
                "email": "first@example.com",
                "password": "Securepassword123",
            },
        )
        # Second user (viewer)
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "seconduser",
                "email": "second@example.com",
                "password": "Securepassword123",
            },
        )
        assert response.status_code == 201
        assert response.json()["user"]["role"] == "viewer"

    async def test_register_duplicate_username_409(self, client: AsyncClient) -> None:
        """Registering with an existing username returns 409."""
        payload = {
            "username": "dupeuser",
            "email": "dupe@example.com",
            "password": "Password12345",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409
        assert "already taken" in response.json()["detail"]

    async def test_second_user_always_gets_viewer(self, client: AsyncClient) -> None:
        """Non-first users are always assigned the viewer role."""
        # Create first user to consume the auto-admin slot
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "seedadmin",
                "email": "seed@example.com",
                "password": "Password12345",
            },
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "vieweruser",
                "email": "viewer@example.com",
                "password": "Viewerpass123",
            },
        )
        assert response.status_code == 201
        # Role field was removed from RegisterRequest — server enforces viewer
        assert response.json()["user"]["role"] == "viewer"


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(self, client: AsyncClient) -> None:
        """Login with correct credentials returns a JWT token.

        Note: TOTP is not yet enabled (user hasn't verified setup), so login works directly.
        """
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "Correctpassword1",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "loginuser",
                "password": "Correctpassword1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["requires_totp"] is False

    async def test_login_wrong_password_401(self, client: AsyncClient) -> None:
        """Login with wrong password returns 401."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "wrongpwuser",
                "email": "wrongpw@example.com",
                "password": "Correctpassword1",
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "wrongpwuser",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user_401(self, client: AsyncClient) -> None:
        """Login with a nonexistent username returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "doesnotexist",
                "password": "anything",
            },
        )
        assert response.status_code == 401


class TestTotpSetup:
    """Tests for TOTP 2FA setup and verification."""

    async def test_verify_setup_activates_totp(self, client: AsyncClient) -> None:
        """Verifying a valid TOTP code activates 2FA and returns a JWT."""
        import pyotp

        # Register
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "totpuser",
                "email": "totp@example.com",
                "password": "Securepassword123",
            },
        )
        totp_uri = reg_resp.json()["totp_uri"]
        # Extract secret from URI
        secret = pyotp.parse_uri(totp_uri).secret

        # Verify setup with a valid code
        totp = pyotp.TOTP(secret)
        code = totp.now()
        verify_resp = await client.post(
            "/api/v1/auth/totp/verify-setup",
            json={
                "username": "totpuser",
                "code": code,
                "password": "Securepassword123",
            },
        )
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 50

    async def test_login_requires_totp_after_setup(self, client: AsyncClient) -> None:
        """After TOTP is enabled, login without code returns requires_totp=true."""
        import pyotp

        # Register + verify setup
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "totp2user",
                "email": "totp2@example.com",
                "password": "Securepassword123",
            },
        )
        secret = pyotp.parse_uri(reg_resp.json()["totp_uri"]).secret
        await client.post(
            "/api/v1/auth/totp/verify-setup",
            json={
                "username": "totp2user",
                "code": pyotp.TOTP(secret).now(),
                "password": "Securepassword123",
            },
        )

        # Login without TOTP code
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "totp2user",
                "password": "Securepassword123",
            },
        )
        assert login_resp.status_code == 401
        data = login_resp.json()
        assert data["detail"]["requires_totp"] is True

    async def test_login_with_totp_code_succeeds(self, client: AsyncClient) -> None:
        """Login with a valid TOTP code after setup returns a JWT."""
        import pyotp

        # Register + verify setup
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "totp3user",
                "email": "totp3@example.com",
                "password": "Securepassword123",
            },
        )
        secret = pyotp.parse_uri(reg_resp.json()["totp_uri"]).secret
        await client.post(
            "/api/v1/auth/totp/verify-setup",
            json={
                "username": "totp3user",
                "code": pyotp.TOTP(secret).now(),
                "password": "Securepassword123",
            },
        )

        # Login with TOTP code
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "totp3user",
                "password": "Securepassword123",
                "totp_code": pyotp.TOTP(secret).now(),
            },
        )
        assert login_resp.status_code == 200
        data = login_resp.json()
        assert data["requires_totp"] is False
        assert len(data["access_token"]) > 50

    async def test_login_with_wrong_totp_code_401(self, client: AsyncClient) -> None:
        """Login with an invalid TOTP code returns 401."""
        import pyotp

        # Register + verify setup
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "totp4user",
                "email": "totp4@example.com",
                "password": "Securepassword123",
            },
        )
        secret = pyotp.parse_uri(reg_resp.json()["totp_uri"]).secret
        await client.post(
            "/api/v1/auth/totp/verify-setup",
            json={
                "username": "totp4user",
                "code": pyotp.TOTP(secret).now(),
                "password": "Securepassword123",
            },
        )

        # Login with wrong TOTP code
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "totp4user",
                "password": "Securepassword123",
                "totp_code": "000000",
            },
        )
        assert login_resp.status_code == 401

    async def test_verify_setup_invalid_code_401(self, client: AsyncClient) -> None:
        """Verifying an invalid TOTP code returns 401."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "badcode",
                "email": "badcode@example.com",
                "password": "Securepassword123",
            },
        )
        response = await client.post(
            "/api/v1/auth/totp/verify-setup",
            json={
                "username": "badcode",
                "code": "000000",
                "password": "Securepassword123",
            },
        )
        assert response.status_code == 401


class TestPasswordHashing:
    """Unit tests for password hashing functions."""

    def test_hash_and_verify(self) -> None:
        """Hashing a password and verifying it succeeds."""
        from domains.auth.service import get_password_hash, verify_password

        hashed = get_password_hash("mypassword")
        assert verify_password("mypassword", hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_is_not_plaintext(self) -> None:
        """Hash output is never the plaintext input."""
        from domains.auth.service import get_password_hash

        hashed = get_password_hash("mypassword")
        assert hashed != "mypassword"
        assert "$2b$" in hashed  # bcrypt prefix


class TestTokenCreation:
    """Unit tests for JWT token creation."""

    def test_create_access_token(self) -> None:
        """create_access_token returns a JWT string."""
        from domains.auth.service import create_access_token

        token = create_access_token({"sub": "testuser", "role": "viewer"})
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

    def test_token_contains_claims(self) -> None:
        """Token can be decoded and contains the expected claims."""
        from domains.auth.service import create_access_token, verify_token

        token = create_access_token({"sub": "testuser", "role": "admin"})
        payload = verify_token(token)
        assert payload is not None
        assert payload.sub == "testuser"
        assert payload.role == "admin"

    def test_verify_invalid_token_raises(self) -> None:
        """verify_token raises ValueError for an invalid JWT."""
        import pytest

        from domains.auth.service import verify_token

        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("not.a.valid.jwt.token")
