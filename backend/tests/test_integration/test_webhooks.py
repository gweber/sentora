"""Integration tests for the webhooks API endpoints.

Tests cover full CRUD lifecycle, access control (admin-only enforcement),
request validation, enable/disable toggling, and SSRF DNS rebinding prevention.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

# ── Helpers ───────────────────────────────────────────────────────────────────


def _webhook_payload(
    name: str = "CI Notifier",
    url: str = "https://example.com/webhook",
    events: list[str] | None = None,
    secret: str = "",
) -> dict:
    return {
        "name": name,
        "url": url,
        "events": events or ["sync.completed"],
        "secret": secret,
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def webhook_id(client: AsyncClient, admin_headers: dict) -> str:
    """Create a webhook and return its id."""
    r = await client.post("/api/v1/webhooks/", json=_webhook_payload(), headers=admin_headers)
    assert r.status_code == 201
    return r.json()["id"]


# ── TestWebhookCRUD ──────────────────────────────────────────────────────────


class TestWebhookCRUD:
    """Full create / list / get / update / delete lifecycle."""

    async def test_create_returns_201(self, client: AsyncClient, admin_headers: dict) -> None:
        r = await client.post("/api/v1/webhooks/", json=_webhook_payload(), headers=admin_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "CI Notifier"
        assert data["url"] == "https://example.com/webhook"
        assert data["events"] == ["sync.completed"]
        assert data["enabled"] is True
        assert data["failure_count"] == 0

    async def test_create_response_shape(self, client: AsyncClient, admin_headers: dict) -> None:
        r = await client.post("/api/v1/webhooks/", json=_webhook_payload(), headers=admin_headers)
        assert r.status_code == 201
        data = r.json()
        for field in (
            "id",
            "name",
            "url",
            "events",
            "enabled",
            "created_at",
            "last_triggered_at",
            "failure_count",
        ):
            assert field in data, f"Missing field: {field}"

    async def test_create_with_multiple_events(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        payload = _webhook_payload(
            events=["sync.completed", "sync.failed", "classification.completed"]
        )
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 201
        assert set(r.json()["events"]) == {
            "sync.completed",
            "sync.failed",
            "classification.completed",
        }

    async def test_create_with_custom_secret(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        payload = _webhook_payload(secret="my-secret-key")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 201
        # Secret is not exposed in the response
        assert "secret" not in r.json()

    async def test_list_returns_created_webhook(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.get("/api/v1/webhooks/", headers=admin_headers)
        assert r.status_code == 200
        ids = [w["id"] for w in r.json()]
        assert webhook_id in ids

    async def test_list_empty(self, client: AsyncClient, admin_headers: dict) -> None:
        r = await client.get("/api/v1/webhooks/", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_get_by_id(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.get(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["id"] == webhook_id
        assert r.json()["name"] == "CI Notifier"

    async def test_get_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.get("/api/v1/webhooks/nonexistent_id", headers=admin_headers)
        assert r.status_code == 404

    async def test_update_name(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"name": "Slack Alerts"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Slack Alerts"

    async def test_update_url(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"url": "https://hooks.slack.com/new"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["url"] == "https://hooks.slack.com/new"

    async def test_update_events(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"events": ["sync.failed", "classification.completed"]},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert set(r.json()["events"]) == {"sync.failed", "classification.completed"}

    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.put(
            "/api/v1/webhooks/nonexistent_id",
            json={"name": "Ghost"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_update_persists(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"name": "Updated Name"},
            headers=admin_headers,
        )
        r = await client.get(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        assert r.json()["name"] == "Updated Name"

    async def test_delete_returns_204(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        assert r.status_code == 204

    async def test_deleted_webhook_not_in_list(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        r = await client.get("/api/v1/webhooks/", headers=admin_headers)
        ids = [w["id"] for w in r.json()]
        assert webhook_id not in ids

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        r = await client.delete("/api/v1/webhooks/nonexistent_id", headers=admin_headers)
        assert r.status_code == 404

    async def test_get_after_delete_returns_404(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        r = await client.get(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        assert r.status_code == 404


# ── TestWebhookAccess ────────────────────────────────────────────────────────


class TestWebhookAccess:
    """Admin-only endpoints reject analyst and unauthenticated requests."""

    async def test_list_analyst_returns_403(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        r = await client.get("/api/v1/webhooks/", headers=analyst_headers)
        assert r.status_code == 403

    async def test_create_analyst_returns_403(
        self, client: AsyncClient, analyst_headers: dict
    ) -> None:
        r = await client.post("/api/v1/webhooks/", json=_webhook_payload(), headers=analyst_headers)
        assert r.status_code == 403

    async def test_update_analyst_returns_403(
        self,
        client: AsyncClient,
        webhook_id: str,
        analyst_headers: dict,
    ) -> None:
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"name": "Hacked"},
            headers=analyst_headers,
        )
        assert r.status_code == 403

    async def test_delete_analyst_returns_403(
        self,
        client: AsyncClient,
        webhook_id: str,
        analyst_headers: dict,
    ) -> None:
        r = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=analyst_headers)
        assert r.status_code == 403

    async def test_list_unauthenticated_rejected(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/webhooks/")
        assert r.status_code in (401, 403)

    async def test_create_unauthenticated_rejected(self, client: AsyncClient) -> None:
        r = await client.post("/api/v1/webhooks/", json=_webhook_payload())
        assert r.status_code in (401, 403)

    async def test_delete_unauthenticated_rejected(self, client: AsyncClient) -> None:
        r = await client.delete("/api/v1/webhooks/some_id")
        assert r.status_code in (401, 403)

    async def test_test_webhook_analyst_returns_403(
        self,
        client: AsyncClient,
        webhook_id: str,
        analyst_headers: dict,
    ) -> None:
        r = await client.post(f"/api/v1/webhooks/{webhook_id}/test", headers=analyst_headers)
        assert r.status_code == 403


# ── TestWebhookValidation ────────────────────────────────────────────────────


class TestWebhookValidation:
    """Request body validation for create and update."""

    async def test_create_missing_name_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        payload = {"url": "https://example.com/hook", "events": ["sync.completed"]}
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_create_empty_name_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        payload = _webhook_payload(name="")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_create_missing_url_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        payload = {"name": "Test Hook", "events": ["sync.completed"]}
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_create_missing_events_returns_422(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        payload = {"name": "Test Hook", "url": "https://example.com/hook"}
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_create_with_empty_events_list(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Empty events list is rejected by the DTO (min_length=1) with 422."""
        payload = {"name": "Test Hook", "url": "https://example.com/hook", "events": []}
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_create_with_unknown_event_type(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Unknown event names are rejected by the service with WebhookError (500)."""
        payload = _webhook_payload(events=["not.a.real.event"])
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 500


# ── TestWebhookToggle ────────────────────────────────────────────────────────


class TestWebhookToggle:
    """Enable and disable webhooks via the update endpoint."""

    async def test_disable_webhook(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"enabled": False},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    async def test_enable_webhook(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        # Disable first
        await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"enabled": False},
            headers=admin_headers,
        )
        # Re-enable
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"enabled": True},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True

    async def test_toggle_persists(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"enabled": False},
            headers=admin_headers,
        )
        r = await client.get(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        assert r.json()["enabled"] is False

    async def test_reenable_resets_failure_count(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
        seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> None:
        """Re-enabling a webhook resets the failure counter to zero."""
        # Manually set failure_count in the database
        await seeded_db["webhooks"].update_one(
            {"_id": webhook_id},
            {"$set": {"failure_count": 5, "enabled": False}},
        )
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"enabled": True},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True
        assert r.json()["failure_count"] == 0

    async def test_disable_does_not_change_other_fields(
        self,
        client: AsyncClient,
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        original = (
            await client.get(f"/api/v1/webhooks/{webhook_id}", headers=admin_headers)
        ).json()
        r = await client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"enabled": False},
            headers=admin_headers,
        )
        updated = r.json()
        assert updated["name"] == original["name"]
        assert updated["url"] == original["url"]
        assert updated["events"] == original["events"]


# ── TestWebhookSsrfProtection ──────────────────────────────────────────────


class TestWebhookSsrfProtection:
    """SSRF protection rejects URLs pointing to internal/private networks or disallowed schemes."""

    async def test_localhost_rejected(self, client: AsyncClient, admin_headers: dict) -> None:
        """Creating a webhook targeting localhost is rejected as an SSRF risk."""
        payload = _webhook_payload(url="http://localhost/hook")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_loopback_ip_rejected(self, client: AsyncClient, admin_headers: dict) -> None:
        """Creating a webhook targeting 127.0.0.1 is rejected as an SSRF risk."""
        payload = _webhook_payload(url="http://127.0.0.1/hook")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_cloud_metadata_ip_rejected(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Webhook targeting cloud metadata endpoint (169.254.169.254) is rejected."""
        payload = _webhook_payload(url="http://169.254.169.254/latest/meta-data/")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_private_network_ip_rejected(
        self, client: AsyncClient, admin_headers: dict
    ) -> None:
        """Creating a webhook targeting a private RFC-1918 address (10.x.x.x) is rejected."""
        payload = _webhook_payload(url="http://10.0.0.1/hook")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_ftp_scheme_rejected(self, client: AsyncClient, admin_headers: dict) -> None:
        """Creating a webhook with a non-HTTP(S) scheme (ftp) is rejected."""
        payload = _webhook_payload(url="ftp://example.com/hook")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 422

    async def test_valid_https_url_accepted(self, client: AsyncClient, admin_headers: dict) -> None:
        """Creating a webhook with a valid public HTTPS URL succeeds."""
        payload = _webhook_payload(url="https://example.com/hook")
        r = await client.post("/api/v1/webhooks/", json=payload, headers=admin_headers)
        assert r.status_code == 201


# ── TestWebhookDnsRebindingPrevention ───────────────────────────────────────


class TestWebhookDnsRebindingPrevention:
    """AUDIT-003: Verify that webhook delivery uses the resolved IP for the HTTP
    connection rather than re-resolving the original hostname, preventing DNS
    rebinding SSRF attacks."""

    async def test_build_pinned_url_replaces_hostname_with_ip(self) -> None:
        """_build_pinned_url should replace the hostname with the resolved IP."""
        from domains.webhooks.service import _build_pinned_url

        pinned_url, host_header = _build_pinned_url(
            "https://example.com/webhook/path", "93.184.216.34"
        )
        assert pinned_url == "https://93.184.216.34/webhook/path"
        assert host_header == "example.com"

    async def test_build_pinned_url_preserves_non_default_port(self) -> None:
        """_build_pinned_url should preserve a non-default port in both the URL and Host header."""
        from domains.webhooks.service import _build_pinned_url

        pinned_url, host_header = _build_pinned_url(
            "https://example.com:8443/hook", "93.184.216.34"
        )
        assert pinned_url == "https://93.184.216.34:8443/hook"
        assert host_header == "example.com:8443"

    async def test_build_pinned_url_omits_default_https_port(self) -> None:
        """_build_pinned_url should not include port 443 for https in the Host header."""
        from domains.webhooks.service import _build_pinned_url

        pinned_url, host_header = _build_pinned_url("https://example.com:443/hook", "93.184.216.34")
        assert host_header == "example.com"
        assert "443" not in pinned_url

    async def test_build_pinned_url_omits_default_http_port(self) -> None:
        """_build_pinned_url should not include port 80 for http in the Host header."""
        from domains.webhooks.service import _build_pinned_url

        pinned_url, host_header = _build_pinned_url("http://example.com:80/hook", "93.184.216.34")
        assert host_header == "example.com"
        assert "80" not in pinned_url

    async def test_build_pinned_url_preserves_query_and_path(self) -> None:
        """_build_pinned_url should preserve path and query string from the original URL."""
        from domains.webhooks.service import _build_pinned_url

        pinned_url, _ = _build_pinned_url(
            "https://example.com/webhook?token=abc&v=2", "93.184.216.34"
        )
        assert pinned_url == "https://93.184.216.34/webhook?token=abc&v=2"

    @pytest.mark.asyncio
    async def test_test_webhook_sends_to_resolved_ip(
        self,
        seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        """test_webhook must POST to the resolved IP, not the original hostname.

        Calls the service function directly with a mocked resolve_and_validate
        and httpx client to capture the actual URL used for the request.
        """
        from domains.webhooks.service import test_webhook

        captured_requests: list[str] = []
        captured_headers: list[dict[str, str]] = []

        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def _capture_post(url: str, **kwargs: object) -> AsyncMock:
            captured_requests.append(url)
            hdrs = kwargs.get("headers")
            captured_headers.append(dict(hdrs) if isinstance(hdrs, dict) else {})
            return mock_response

        with (
            patch(
                "utils.ssrf.resolve_and_validate",
                new_callable=AsyncMock,
                return_value="93.184.216.34",
            ),
            patch("domains.webhooks.service.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_instance = AsyncMock()
            mock_client_instance.post = _capture_post
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            result = await test_webhook(seeded_db, webhook_id)

        assert result.success is True
        # The HTTP request must target the resolved IP, not the original hostname
        assert len(captured_requests) == 1, "Expected exactly one outbound HTTP request"
        assert "93.184.216.34" in captured_requests[0], (
            f"Request URL should contain the resolved IP, got: {captured_requests[0]}"
        )
        assert "example.com" not in captured_requests[0], (
            f"Request URL should NOT contain the original hostname, got: {captured_requests[0]}"
        )
        # The Host header must carry the original hostname for correct virtual hosting
        assert captured_headers[0].get("Host") == "example.com"

    @pytest.mark.asyncio
    async def test_deliver_sends_to_resolved_ip(
        self,
        seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        webhook_id: str,
        admin_headers: dict,
    ) -> None:
        """_deliver must POST to the resolved IP, not the original hostname.

        Directly invokes _deliver with a mocked resolve_and_validate and httpx
        client to verify the connection target.
        """
        from domains.webhooks import repository
        from domains.webhooks.service import _deliver

        webhook = await repository.get_by_id(seeded_db, webhook_id)
        assert webhook is not None

        captured_requests: list[str] = []
        captured_headers: list[dict[str, str]] = []

        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def _capture_post(url: str, **kwargs: object) -> AsyncMock:
            captured_requests.append(url)
            hdrs = kwargs.get("headers")
            captured_headers.append(dict(hdrs) if isinstance(hdrs, dict) else {})
            return mock_response

        with (
            patch(
                "utils.ssrf.resolve_and_validate",
                new_callable=AsyncMock,
                return_value="93.184.216.34",
            ),
            patch("domains.webhooks.service.httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_instance = AsyncMock()
            mock_client_instance.post = _capture_post
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client_instance

            await _deliver(seeded_db, webhook, "sync.completed", {"key": "value"})

        assert len(captured_requests) == 1, "Expected exactly one outbound HTTP request"
        assert "93.184.216.34" in captured_requests[0], (
            f"Request URL should contain the resolved IP, got: {captured_requests[0]}"
        )
        assert "example.com" not in captured_requests[0], (
            f"Request URL should NOT contain the original hostname, got: {captured_requests[0]}"
        )
        assert captured_headers[0].get("Host") == "example.com"
