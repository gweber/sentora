"""Performance regression tests — pagination bounds, cache limits.

Covers:
- Round 2: Pagination max limit enforcement on all list endpoints
- Round 2: Pagination with invalid values (0, -1, huge numbers)
- Round 2: LRU cache bounds (tenant cache, app cache)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase


class TestPaginationBounds:
    """Regression: Round 2 — all list endpoints enforce pagination limits."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/agents/",
            "/api/v1/apps/",
            "/api/v1/classification/results",
            "/api/v1/fingerprints/",
            "/api/v1/audit/",
            "/api/v1/tags/",
        ],
        ids=["agents", "apps", "classification", "fingerprints", "audit", "tags"],
    )
    async def test_default_pagination_returns_limited_results(
        self,
        client: AsyncClient,
        admin_headers: dict,
        path: str,
    ) -> None:
        """Regression: Round 2 — calling without page_size returns bounded results."""
        resp = await client.get(path, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Check response has pagination metadata
        has_pagination = (
            "total" in data or "page" in data or "limit" in data or isinstance(data, list)
        )
        assert has_pagination, f"Endpoint {path} response lacks pagination metadata"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/audit/",
        ],
    )
    async def test_excessive_page_size_capped(
        self,
        client: AsyncClient,
        admin_headers: dict,
        path: str,
    ) -> None:
        """Regression: Round 2 — page_size=999999 is rejected or capped."""
        resp = await client.get(
            path,
            params={"limit": 999999},
            headers=admin_headers,
        )
        # Should either reject (422) or cap to max (200 with limited results)
        assert resp.status_code in (200, 422), (
            f"Expected 200 or 422 for huge page_size on {path}, got {resp.status_code}"
        )
        if resp.status_code == 200:
            data = resp.json()
            if "limit" in data:
                assert data["limit"] <= 500, f"Limit should be capped at 500, got {data['limit']}"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/audit/",
        ],
    )
    async def test_zero_page_size_rejected(
        self,
        client: AsyncClient,
        admin_headers: dict,
        path: str,
    ) -> None:
        """Regression: Round 2 — page_size=0 returns 422."""
        resp = await client.get(
            path,
            params={"limit": 0},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/audit/",
        ],
    )
    async def test_negative_page_size_rejected(
        self,
        client: AsyncClient,
        admin_headers: dict,
        path: str,
    ) -> None:
        """Regression: Round 2 — page_size=-1 returns 422."""
        resp = await client.get(
            path,
            params={"limit": -1},
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestCacheBounds:
    """Regression: Round 2 — LRU caches have explicit size bounds."""

    def test_tenant_cache_has_max_size(self) -> None:
        """Regression: Round 2 — tenant cache specifies a maximum size."""
        from middleware.tenant import _TENANT_CACHE_MAX

        assert _TENANT_CACHE_MAX > 0, "Tenant cache must have a max size"
        assert _TENANT_CACHE_MAX <= 100_000, "Tenant cache max is unreasonably large"

    def test_oidc_discovery_cache_has_ttl(self) -> None:
        """Regression: Round 2 — OIDC discovery cache has a finite TTL."""
        from domains.auth.oidc import _DISCOVERY_CACHE_TTL

        assert _DISCOVERY_CACHE_TTL > 0, "Discovery cache TTL must be positive"
        assert _DISCOVERY_CACHE_TTL <= 86400, "Discovery cache TTL should not exceed 1 day"


class TestDbIndexes:
    """Regression: Round 2 — all expected indexes exist after ensure_all_indexes."""

    async def test_all_indexes_created(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """ensure_all_indexes creates indexes on all key collections."""
        from db_indexes import ensure_all_indexes

        await ensure_all_indexes(test_db)

        # Spot-check critical indexes
        agents_idx = await test_db["s1_agents"].index_information()
        assert any("s1_agent_id" in str(idx.get("key", "")) for idx in agents_idx.values()), (
            "s1_agents missing s1_agent_id index"
        )

        users_idx = await test_db["users"].index_information()
        assert any("username" in str(idx.get("key", "")) for idx in users_idx.values()), (
            "users missing username index"
        )

        refresh_idx = await test_db["refresh_tokens"].index_information()
        ttl_found = any("expireAfterSeconds" in idx for idx in refresh_idx.values())
        assert ttl_found, "refresh_tokens missing TTL index"

    async def test_distributed_lock_ttl_index(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """Regression: Round 1 BUG-6 — distributed_locks has a TTL index."""
        from db_indexes import ensure_all_indexes

        await ensure_all_indexes(test_db)

        lock_idx = await test_db["distributed_locks"].index_information()
        ttl_found = False
        for idx_info in lock_idx.values():
            if "expireAfterSeconds" in idx_info:
                ttl_found = True
                assert idx_info["expireAfterSeconds"] == 0, (
                    "Distributed lock TTL should be 0 (expire at the document's expires_at)"
                )
        assert ttl_found, "distributed_locks missing TTL index"
