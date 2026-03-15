"""Integration tests for the global RateLimitMiddleware.

Tests cover exempt paths, normal request passthrough, strict login limits,
and the shape of the 429 response.
"""

from __future__ import annotations

from httpx import AsyncClient

from middleware.rate_limit import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Tests for the global rate-limiting middleware."""

    async def test_health_exempt(self, client: AsyncClient) -> None:
        """GET /health is exempt from rate limiting and always returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_metrics_exempt(self, client: AsyncClient, admin_headers: dict) -> None:
        """GET /metrics is exempt from rate limiting (requires admin auth)."""
        response = await client.get("/metrics", headers=admin_headers)
        assert response.status_code == 200

    async def test_normal_request_passes(self, client: AsyncClient, admin_headers: dict) -> None:
        """A single authenticated request to a normal endpoint is not rate limited."""
        response = await client.get("/api/v1/dashboard/fleet", headers=admin_headers)
        # Should succeed (not 429)
        assert response.status_code != 429

    async def test_429_response_shape(self) -> None:
        """RateLimitMiddleware._too_many_requests returns correct JSON and headers."""
        # Create a standalone instance to inspect the 429 response.
        # We cannot call __init__ normally because it needs an ASGI app,
        # so we instantiate with a no-op app and inspect the helper directly.
        from starlette.applications import Starlette

        mw = RateLimitMiddleware(Starlette())
        resp = mw._too_many_requests()

        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "60"
        # Decode the body (JSONResponse stores bytes internally)
        assert resp.body is not None
        import json

        body = json.loads(resp.body.decode())
        assert "detail" in body
        assert "Too many requests" in body["detail"]

    async def test_login_strict_limit_triggers_429(self, client: AsyncClient) -> None:
        """The /api/v1/auth/login path has a strict 5 req/min limit.

        After 5 requests the middleware should return 429 on the 6th,
        regardless of whether the login itself succeeds or fails.
        """
        payload = {"username": "nonexistent", "password": "wrong"}
        statuses: list[int] = []
        for _ in range(7):
            resp = await client.post("/api/v1/auth/login", json=payload)
            statuses.append(resp.status_code)

        # At least the last request(s) must be 429
        assert 429 in statuses, f"Expected at least one 429 in {statuses}"
        # The first few should NOT be 429 (they hit the real handler)
        assert statuses[0] != 429

    async def test_429_has_retry_after_header(self, client: AsyncClient) -> None:
        """When the middleware returns 429 it includes a Retry-After header."""
        payload = {"username": "nonexistent", "password": "wrong"}
        last_resp = None
        for _ in range(7):
            last_resp = await client.post("/api/v1/auth/login", json=payload)
            if last_resp.status_code == 429:
                break

        assert last_resp is not None
        assert last_resp.status_code == 429
        assert "Retry-After" in last_resp.headers
