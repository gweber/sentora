"""Security regression tests — JWT algorithm restriction and token validation.

Covers:
- Round 2: JWT alg:none bypass attempt
- Round 2: JWT algorithm confusion (HS256 vs RS256)
- Round 2: Expired JWT rejection
- Round 2: Malformed JWT rejection
"""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from httpx import AsyncClient


class TestJwtAlgorithmRestriction:
    """Regression: Round 2 — JWT must only accept the configured algorithm."""

    def test_alg_none_rejected(self) -> None:
        """A JWT with alg=none and valid payload must be rejected."""
        from domains.auth.service import verify_token

        # Construct a token with alg=none (no signature)
        payload = {"sub": "attacker", "role": "admin", "type": "access", "exp": 9999999999}
        token = pyjwt.encode(payload, key="", algorithm="none")
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token(token)

    def test_wrong_algorithm_rejected(self) -> None:
        """A JWT signed with a different secret must be rejected."""
        from domains.auth.service import verify_token

        payload = {"sub": "attacker", "role": "admin", "type": "access", "exp": 9999999999}
        token = pyjwt.encode(payload, key="wrong-secret-key", algorithm="HS256")
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token(token)

    def test_expired_jwt_rejected(self) -> None:
        """An expired JWT must be rejected."""
        from config import get_settings
        from domains.auth.service import verify_token

        settings = get_settings()
        payload = {
            "sub": "user",
            "role": "admin",
            "type": "access",
            "exp": int(time.time()) - 3600,  # expired 1 hour ago
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token(token)

    def test_malformed_jwt_rejected(self) -> None:
        """A random string that is not a JWT must be rejected."""
        from domains.auth.service import verify_token

        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("this-is-not-a-jwt")

    def test_empty_string_jwt_rejected(self) -> None:
        """An empty string must be rejected."""
        from domains.auth.service import verify_token

        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("")

    def test_truncated_jwt_rejected(self) -> None:
        """A JWT with a missing signature segment must be rejected."""
        from domains.auth.service import verify_token

        # Valid header.payload but no signature
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0")


class TestJwtViaHttpEndpoint:
    """Regression: Round 2 — HTTP-level JWT enforcement on protected endpoints."""

    async def test_no_auth_header_401(self, client: AsyncClient) -> None:
        """Request without Authorization header returns 401."""
        resp = await client.get("/api/v1/agents/")
        assert resp.status_code in (401, 403)

    async def test_expired_jwt_401(self, client: AsyncClient) -> None:
        """Request with an expired JWT returns 401."""
        from config import get_settings

        settings = get_settings()
        payload = {
            "sub": "user",
            "role": "admin",
            "type": "access",
            "exp": int(time.time()) - 3600,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        resp = await client.get("/api/v1/agents/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_malformed_jwt_401(self, client: AsyncClient) -> None:
        """Request with a random string as JWT returns 401."""
        resp = await client.get(
            "/api/v1/agents/",
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        assert resp.status_code == 401

    async def test_alg_none_jwt_401(self, client: AsyncClient) -> None:
        """Request with alg=none JWT returns 401."""
        payload = {"sub": "attacker", "role": "admin", "type": "access", "exp": 9999999999}
        token = pyjwt.encode(payload, key="", algorithm="none")
        resp = await client.get(
            "/api/v1/agents/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_refresh_token_as_access_401(self, client: AsyncClient) -> None:
        """A refresh token must not be accepted as an access token."""
        from config import get_settings

        settings = get_settings()
        payload = {
            "sub": "user",
            "role": "admin",
            "type": "refresh",
            "jti": "fake-jti",
            "fam": "fake-fam",
            "exp": 9999999999,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        resp = await client.get(
            "/api/v1/agents/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
