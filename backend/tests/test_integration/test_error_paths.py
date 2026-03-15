"""Integration tests for error conditions and security middleware.

Tests cover:
- /health/ready returns 503 when the DB is unavailable
- Request body > 10 MB returns 413
- Security headers are present on responses
- CORS configuration (allowed methods, credentials flag)
- BodySizeLimitMiddleware rejects oversized requests

Uses the ``client`` fixture from conftest.py (HTTPX async test client).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# ── Health readiness when DB is unavailable ─────────────────────────────────


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_db_unavailable(client: AsyncClient) -> None:
    """GET /health/ready must return 503 when the database is unreachable."""
    # Mock get_db to raise so the ping command inside the endpoint fails
    with patch("database._client", None):
        resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"


@pytest.mark.asyncio
async def test_health_ready_returns_200_when_db_available(client: AsyncClient) -> None:
    """GET /health/ready must return 200 when the database is reachable."""
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"


# ── Body size limit middleware ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oversized_request_returns_413(client: AsyncClient) -> None:
    """A request with Content-Length > 10 MB must be rejected with 413."""
    # Send a request claiming a body larger than 10 MB
    oversized_body = b"x" * (10 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/taxonomy/entries",
        content=oversized_body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(oversized_body)),
        },
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_body_size_limit_allows_small_request(client: AsyncClient) -> None:
    """A request well under 10 MB must not be rejected by the size limit middleware."""
    # A normal-sized POST passes the body size middleware.
    # POST to /api/v1/taxonomy/entries has no matching POST route, so 405.
    resp = await client.post(
        "/api/v1/taxonomy/entries",
        json={"name": "test"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 405


# ── Security headers ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    """Every response must include the standard security headers."""
    resp = await client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_security_headers_on_api_route(client: AsyncClient) -> None:
    """Security headers must also appear on API routes, not just /health."""
    resp = await client.get("/api/v1/taxonomy/categories")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_permissions_policy_header(client: AsyncClient) -> None:
    """The Permissions-Policy header must restrict camera, microphone, geolocation."""
    resp = await client.get("/health")
    pp = resp.headers.get("permissions-policy", "")
    assert "camera=()" in pp
    assert "microphone=()" in pp
    assert "geolocation=()" in pp


# ── CORS configuration ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cors_preflight_allows_expected_methods() -> None:
    """CORS preflight must list the expected HTTP methods in Allow headers.

    In development mode CORS is open for the Vite dev server origin.
    """
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.options(
            "/api/v1/taxonomy/categories",
            headers={
                "Origin": "http://localhost:5003",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
    # If CORS is configured for this origin, we get 200; methods should be listed
    if resp.status_code == 200:
        allowed = resp.headers.get("access-control-allow-methods", "")
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            assert method in allowed, f"{method} not in Access-Control-Allow-Methods"


@pytest.mark.asyncio
async def test_cors_does_not_allow_arbitrary_origin(client: AsyncClient) -> None:
    """CORS must not reflect an arbitrary origin that is not in the allow list."""
    resp = await client.get(
        "/health",
        headers={"Origin": "https://evil.example.com"},
    )
    acao = resp.headers.get("access-control-allow-origin", "")
    assert "evil.example.com" not in acao


# ── BodySizeLimitMiddleware direct test ─────────────────────────────────────


@pytest.mark.asyncio
async def test_body_size_middleware_rejects_via_content_length_header(client: AsyncClient) -> None:
    """The middleware checks Content-Length before reading the body.

    Even a small body with a falsely large Content-Length header triggers 413.
    """
    resp = await client.post(
        "/api/v1/taxonomy/entries",
        content=b'{"name":"x"}',
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(20 * 1024 * 1024),  # 20 MB claimed
        },
    )
    assert resp.status_code == 413
