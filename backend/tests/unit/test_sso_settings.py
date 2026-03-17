"""Tests for SSO settings resolver (OIDC and SAML)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.auth.sso_settings import (
    OIDCSettings,
    SAMLSettings,
    resolve_oidc_settings,
    resolve_saml_settings,
)


def _mock_env() -> MagicMock:
    env = MagicMock()
    env.oidc_enabled = False
    env.oidc_discovery_url = "https://env.example.com/.well-known"
    env.oidc_client_id = "env-client-id"
    env.oidc_client_secret = "env-secret"
    env.oidc_redirect_uri = "https://app.example.com/callback"
    env.oidc_default_role = "viewer"
    env.saml_enabled = False
    env.saml_idp_metadata_url = "https://idp.example.com/metadata"
    env.saml_sp_entity_id = "env-sp-entity"
    env.saml_sp_acs_url = "https://app.example.com/saml/acs"
    env.saml_default_role = "viewer"
    return env


class TestResolveOidcSettings:
    @pytest.mark.asyncio
    async def test_env_fallback_when_no_db_config(self) -> None:
        """Falls back to env vars when DB has no config."""
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value=None)

        with patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()):
            result = await resolve_oidc_settings(db)

        assert isinstance(result, OIDCSettings)
        assert result.enabled is False
        assert result.client_id == "env-client-id"

    @pytest.mark.asyncio
    async def test_env_fallback_when_oidc_disabled_in_db(self) -> None:
        """Falls back to env when DB config has oidc_enabled=False."""
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value={"_id": "global", "oidc_enabled": False})

        with patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()):
            result = await resolve_oidc_settings(db)

        assert result.enabled is False

    @pytest.mark.asyncio
    async def test_db_config_used_when_enabled(self) -> None:
        """Uses DB config when oidc_enabled=True."""
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value={
            "_id": "global",
            "oidc_enabled": True,
            "oidc_discovery_url": "https://db.example.com/.well-known",
            "oidc_client_id": "db-client-id",
            "oidc_client_secret": "encrypted-secret",
            "oidc_redirect_uri": "https://db.example.com/callback",
            "oidc_default_role": "analyst",
        })

        with (
            patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()),
            patch("utils.crypto.decrypt_field", return_value="decrypted-secret"),
        ):
            result = await resolve_oidc_settings(db)

        assert result.enabled is True
        assert result.client_id == "db-client-id"
        assert result.client_secret == "decrypted-secret"
        assert result.default_role == "analyst"

    @pytest.mark.asyncio
    async def test_decrypt_failure_returns_empty_secret(self) -> None:
        """When decrypt_field raises ValueError, client_secret is empty."""
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value={
            "_id": "global",
            "oidc_enabled": True,
            "oidc_client_secret": "bad-encrypted",
        })

        with (
            patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()),
            patch("utils.crypto.decrypt_field", side_effect=ValueError("bad")),
        ):
            result = await resolve_oidc_settings(db)

        assert result.client_secret == ""


class TestResolveSamlSettings:
    @pytest.mark.asyncio
    async def test_env_fallback(self) -> None:
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value=None)

        with patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()):
            result = await resolve_saml_settings(db)

        assert isinstance(result, SAMLSettings)
        assert result.enabled is False
        assert result.sp_entity_id == "env-sp-entity"

    @pytest.mark.asyncio
    async def test_db_config_used_when_enabled(self) -> None:
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value={
            "_id": "global",
            "saml_enabled": True,
            "saml_idp_metadata_url": "https://db-idp.example.com/metadata",
            "saml_sp_entity_id": "db-sp",
            "saml_sp_acs_url": "https://db.example.com/saml/acs",
            "saml_default_role": "admin",
        })

        with patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()):
            result = await resolve_saml_settings(db)

        assert result.enabled is True
        assert result.sp_entity_id == "db-sp"
        assert result.default_role == "admin"

    @pytest.mark.asyncio
    async def test_saml_disabled_in_db(self) -> None:
        db = AsyncMock(spec=AsyncIOMotorDatabase)
        db.__getitem__ = MagicMock(return_value=db)
        db.find_one = AsyncMock(return_value={"_id": "global", "saml_enabled": False})

        with patch("domains.auth.sso_settings.get_settings", return_value=_mock_env()):
            result = await resolve_saml_settings(db)

        assert result.enabled is False
