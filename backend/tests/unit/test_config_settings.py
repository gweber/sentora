"""Unit tests for config.Settings validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestSSODefaultRoleValidator:
    """Tests for the SSO default role constraint (AUDIT-053)."""

    def test_viewer_is_valid(self) -> None:
        """'viewer' should be accepted as an OIDC/SAML default role."""
        from config import Settings

        s = Settings(
            oidc_default_role="viewer",
            saml_default_role="viewer",
            jwt_secret_key="x" * 64,
            field_encryption_key="x" * 64,
        )
        assert s.oidc_default_role == "viewer"
        assert s.saml_default_role == "viewer"

    def test_analyst_is_valid(self) -> None:
        """'analyst' should be accepted as an OIDC/SAML default role."""
        from config import Settings

        s = Settings(
            oidc_default_role="analyst",
            saml_default_role="analyst",
            jwt_secret_key="x" * 64,
            field_encryption_key="x" * 64,
        )
        assert s.oidc_default_role == "analyst"

    def test_admin_is_valid(self) -> None:
        """'admin' should be accepted as an OIDC/SAML default role."""
        from config import Settings

        s = Settings(
            oidc_default_role="admin",
            saml_default_role="admin",
            jwt_secret_key="x" * 64,
            field_encryption_key="x" * 64,
        )
        assert s.oidc_default_role == "admin"

    def test_invalid_oidc_role_rejected(self) -> None:
        """An arbitrary string for oidc_default_role should be rejected."""
        from config import Settings

        with pytest.raises(ValidationError, match="SSO default role"):
            Settings(
                oidc_default_role="superadmin",
                jwt_secret_key="x" * 64,
                field_encryption_key="x" * 64,
            )

    def test_invalid_saml_role_rejected(self) -> None:
        """An arbitrary string for saml_default_role should be rejected."""
        from config import Settings

        with pytest.raises(ValidationError, match="SSO default role"):
            Settings(
                saml_default_role="root",
                jwt_secret_key="x" * 64,
                field_encryption_key="x" * 64,
            )
