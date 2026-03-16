"""Unit tests for auth security fixes (AUDIT-024/025/026).

Covers:
- JWT access token verification with built-in aud/iss checks (AUDIT-024)
- Refresh token issuer verification (AUDIT-026)
- TOTP secret encryption at rest (AUDIT-025)
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest


def _mock_settings(**overrides):  # noqa: ANN003, ANN202
    """Return a mock settings object with sensible test defaults."""
    defaults = {
        "jwt_secret_key": "test-secret-key-for-unit-tests",
        "jwt_algorithm": "HS256",
        "jwt_access_expire_minutes": 15,
        "jwt_refresh_expire_days": 7,
        "field_encryption_key": "test-encryption-key-for-unit-tests",
    }
    defaults.update(overrides)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


# ── AUDIT-024: JWT aud/iss verification ──────────────────────────────────────


class TestVerifyTokenAudIss:
    """verify_token must reject tokens with wrong/missing audience or issuer."""

    def test_valid_token_accepted(self) -> None:
        """A properly minted access token passes verification."""
        settings = _mock_settings()
        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import create_access_token, verify_token

            token = create_access_token({"sub": "alice", "role": "viewer"})
            payload = verify_token(token)
            assert payload.sub == "alice"
            assert payload.role == "viewer"

    def test_wrong_audience_rejected(self) -> None:
        """Token with wrong audience is rejected by PyJWT's built-in check."""
        settings = _mock_settings()
        # Manually craft a token with a wrong audience
        claims = {
            "sub": "alice",
            "role": "viewer",
            "type": "access",
            "aud": "wrong-audience",
            "iss": "sentora",
            "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + timedelta(minutes=15),
        }
        token = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")

        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import verify_token

            with pytest.raises(ValueError, match="Invalid token"):
                verify_token(token)

    def test_wrong_issuer_rejected(self) -> None:
        """Token with wrong issuer is rejected by PyJWT's built-in check."""
        settings = _mock_settings()
        claims = {
            "sub": "alice",
            "role": "viewer",
            "type": "access",
            "aud": "sentora-api",
            "iss": "evil-issuer",
            "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + timedelta(minutes=15),
        }
        token = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")

        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import verify_token

            with pytest.raises(ValueError, match="Invalid token|Invalid or missing token issuer"):
                verify_token(token)

    def test_missing_audience_rejected(self) -> None:
        """Token without audience claim is rejected."""
        settings = _mock_settings()
        claims = {
            "sub": "alice",
            "role": "viewer",
            "type": "access",
            "iss": "sentora",
            "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + timedelta(minutes=15),
        }
        token = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")

        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import verify_token

            with pytest.raises(ValueError, match="Invalid.*audience|Invalid token"):
                verify_token(token)

    def test_list_audience_accepted(self) -> None:
        """PyJWT's built-in aud check handles list audiences correctly."""
        settings = _mock_settings()
        claims = {
            "sub": "alice",
            "role": "viewer",
            "type": "access",
            "jti": "test-jti",
            "aud": ["sentora-api", "other-service"],
            "iss": "sentora",
            "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + timedelta(minutes=15),
        }
        token = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")

        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import verify_token

            payload = verify_token(token)
            assert payload.sub == "alice"


# ── AUDIT-026: Refresh token issuer verification ────────────────────────────


class TestRefreshTokenIssuer:
    """Refresh tokens must include iss claim and verify it on decode."""

    @pytest.mark.asyncio
    async def test_refresh_token_includes_iss(self) -> None:
        """create_refresh_token embeds an 'iss' claim."""
        from unittest.mock import AsyncMock

        settings = _mock_settings()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))

        with (
            patch("domains.auth.service.get_settings", return_value=settings),
            patch("config.get_settings", return_value=settings),
        ):
            from domains.auth.service import create_refresh_token

            token_str, _fam = await create_refresh_token(mock_db, "alice", "viewer")

        decoded = jwt.decode(
            token_str,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["HS256"],
        )
        assert decoded["iss"] == "sentora"

    @pytest.mark.asyncio
    async def test_rotate_rejects_wrong_issuer(self) -> None:
        """rotate_refresh_token rejects tokens with wrong issuer."""
        settings = _mock_settings()
        claims = {
            "sub": "alice",
            "role": "viewer",
            "type": "refresh",
            "jti": "tok-1",
            "fam": "fam-1",
            "iss": "evil",
            "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + timedelta(days=7),
        }
        token = jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")

        mock_db = MagicMock()
        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import rotate_refresh_token

            with pytest.raises(ValueError, match="Invalid refresh token"):
                await rotate_refresh_token(mock_db, token)


# ── AUDIT-025: TOTP secret encryption at rest ───────────────────────────────


class TestTotpEncryption:
    """TOTP secrets must be encrypted when stored and decrypted when read."""

    def test_doc_to_user_decrypts_totp_secret(self) -> None:
        """_doc_to_user decrypts an encrypted TOTP secret."""
        settings = _mock_settings()
        with patch("config.get_settings", return_value=settings):
            from utils.crypto import encrypt_field

            encrypted = encrypt_field("JBSWY3DPEHPK3PXP")

        doc = {
            "_id": "user-1",
            "username": "alice",
            "email": "alice@example.com",
            "role": "viewer",
            "hashed_password": "bcrypt-hash",
            "totp_secret": encrypted,
            "totp_enabled": True,
        }

        with (
            patch("domains.auth.service.get_settings", return_value=settings),
            patch("config.get_settings", return_value=settings),
        ):
            from domains.auth.service import _doc_to_user

            user = _doc_to_user(doc)

        assert user.totp_secret == "JBSWY3DPEHPK3PXP"

    def test_doc_to_user_handles_legacy_plaintext(self) -> None:
        """_doc_to_user handles legacy plaintext TOTP secrets transparently."""
        settings = _mock_settings()
        doc = {
            "_id": "user-2",
            "username": "bob",
            "email": "bob@example.com",
            "role": "viewer",
            "hashed_password": "bcrypt-hash",
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "totp_enabled": True,
        }

        with (
            patch("domains.auth.service.get_settings", return_value=settings),
            patch("config.get_settings", return_value=settings),
        ):
            from domains.auth.service import _doc_to_user

            user = _doc_to_user(doc)

        assert user.totp_secret == "JBSWY3DPEHPK3PXP"

    def test_doc_to_user_handles_null_totp(self) -> None:
        """_doc_to_user handles missing/null TOTP secret without error."""
        settings = _mock_settings()
        doc = {
            "_id": "user-3",
            "username": "charlie",
            "email": "charlie@example.com",
            "role": "viewer",
            "hashed_password": "bcrypt-hash",
        }

        with patch("domains.auth.service.get_settings", return_value=settings):
            from domains.auth.service import _doc_to_user

            user = _doc_to_user(doc)

        assert user.totp_secret is None
