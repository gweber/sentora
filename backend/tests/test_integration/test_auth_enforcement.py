"""Integration tests verifying auth enforcement on API routes.

All data-plane routes now require a valid JWT via ``get_current_user`` or
``require_role``. These tests confirm that unauthenticated requests are
rejected and authenticated requests are accepted.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestAuthEnforcementGET:
    """Unauthenticated GET requests to protected endpoints must be rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/agents/",
            "/api/v1/apps/",
            "/api/v1/groups/",
            "/api/v1/dashboard/fleet",
            "/api/v1/classification/results",
            "/api/v1/fingerprints/",
            "/api/v1/taxonomy/",
            "/api/v1/config/",
            "/api/v1/audit/",
            "/api/v1/tags/",
        ],
        ids=[
            "agents",
            "apps",
            "groups",
            "dashboard",
            "classification",
            "fingerprints",
            "taxonomy",
            "config",
            "audit",
            "tags",
        ],
    )
    async def test_requires_auth(self, client: AsyncClient, path: str) -> None:
        """GET {path} without credentials returns 401 or 403."""
        response = await client.get(path)
        assert response.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated GET {path}, got {response.status_code}"
        )


class TestAuthEnforcementWithToken:
    """Authenticated GET requests to protected endpoints must NOT be rejected."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/agents/",
            "/api/v1/apps/",
            "/api/v1/groups/",
            "/api/v1/dashboard/fleet",
            "/api/v1/classification/results",
            "/api/v1/fingerprints/",
            "/api/v1/taxonomy/",
            "/api/v1/config/",
            "/api/v1/audit/",
            "/api/v1/tags/",
        ],
        ids=[
            "agents",
            "apps",
            "groups",
            "dashboard",
            "classification",
            "fingerprints",
            "taxonomy",
            "config",
            "audit",
            "tags",
        ],
    )
    async def test_with_admin_token_not_rejected(
        self, client: AsyncClient, admin_headers: dict, path: str
    ) -> None:
        """GET {path} with a valid admin JWT is not 401 or 403."""
        response = await client.get(path, headers=admin_headers)
        assert response.status_code not in (401, 403), (
            f"Expected non-auth-error for authenticated GET {path}, got {response.status_code}"
        )
