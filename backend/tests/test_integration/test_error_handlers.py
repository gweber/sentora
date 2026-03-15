"""Tests for the global error handler middleware.

Covers:
- SentoraError handler (sentora_error_handler)
- DatabaseUnavailableError handler (database_unavailable_handler)
- Unhandled exception handler (unhandled_exception_handler)
"""

from __future__ import annotations

from httpx import AsyncClient


class TestSentoraErrorHandler:
    """The SentoraError handler returns structured JSON responses."""

    async def test_domain_error_returns_structured_json(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """A domain error (e.g., FingerprintNotFound) returns the correct error shape."""
        resp = await client.get("/api/v1/fingerprints/nonexistent_group", headers=admin_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "error_code" in data
        assert "message" in data
        assert data["error_code"] == "FINGERPRINT_NOT_FOUND"

    async def test_domain_error_409_conflict(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        """Creating a duplicate fingerprint returns 409 with structured error."""
        gid = "err_dup_group"
        r1 = await client.post(f"/api/v1/fingerprints/{gid}", headers=analyst_headers)
        assert r1.status_code == 201
        r2 = await client.post(f"/api/v1/fingerprints/{gid}", headers=analyst_headers)
        assert r2.status_code == 409
        data = r2.json()
        assert data["error_code"] == "FINGERPRINT_ALREADY_EXISTS"

    async def test_marker_not_found_error(self, client: AsyncClient, analyst_headers: dict) -> None:
        """Deleting a nonexistent marker returns structured 404."""
        gid = "err_marker_group"
        await client.post(f"/api/v1/fingerprints/{gid}", headers=analyst_headers)
        resp = await client.delete(
            f"/api/v1/fingerprints/{gid}/markers/000000000000000000000000",
            headers=analyst_headers,
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["error_code"] == "MARKER_NOT_FOUND"


class TestDatabaseUnavailableHandler:
    """The DatabaseUnavailableError handler returns 503."""

    async def test_readiness_503_when_db_down(self, client: AsyncClient) -> None:
        """GET /health/ready returns 503 when the DB ping fails."""
        from unittest.mock import patch

        with patch("database._client", None):
            resp = await client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "not_ready"

    async def test_database_unavailable_handler_directly(self, client: AsyncClient) -> None:
        """Call database_unavailable_handler directly to cover its response shape."""
        import json

        from fastapi import Request

        from database import DatabaseUnavailableError
        from middleware.error_handler import database_unavailable_handler

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        mock_request = Request(scope)

        resp = await database_unavailable_handler(mock_request, DatabaseUnavailableError("DB down"))
        assert resp.status_code == 503
        data = json.loads(resp.body)
        assert data["error_code"] == "DB_UNAVAILABLE"
        assert "MongoDB" in data["message"] or "Database" in data["message"]


class TestUnhandledExceptionHandler:
    """The unhandled exception handler returns a generic 500."""

    async def test_unhandled_exception_returns_500(self, client: AsyncClient) -> None:
        """An unexpected exception in a route returns 500 with INTERNAL_ERROR."""

        # Directly call the error handler to verify its behavior
        from fastapi import Request

        from middleware.error_handler import unhandled_exception_handler

        # Build a minimal mock request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }
        mock_request = Request(scope)

        resp = await unhandled_exception_handler(mock_request, RuntimeError("boom"))
        assert resp.status_code == 500
        import json

        data = json.loads(resp.body)
        assert data["error_code"] == "INTERNAL_ERROR"
        assert data["message"] == "An unexpected error occurred"
        # In development mode, traceback is included
        assert "traceback" in data.get("detail", {})
