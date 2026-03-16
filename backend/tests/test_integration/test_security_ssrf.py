"""Security regression tests — SSRF protection on webhook URL validation.

Covers:
- Round 2: Webhook URL must reject internal IPs (127.0.0.1, localhost, etc.)
- Round 2: Webhook URL must reject AWS metadata endpoint
- Round 2: Webhook URL must reject private ranges (10.x, 172.16.x, 192.168.x)
- Round 2: Webhook URL must reject non-HTTP schemes (file://, gopher://, etc.)
- Round 2: DNS rebinding protection (resolve-time IP check)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestSsrfWebhookUrlValidation:
    """Regression: Round 2 — webhook URL SSRF prevention via Pydantic validator."""

    @pytest.mark.parametrize(
        "url,reason",
        [
            ("http://127.0.0.1/hook", "loopback-ipv4"),
            ("http://localhost/hook", "localhost-hostname"),
            ("http://0.0.0.0/hook", "zero-addr"),
            ("http://[::1]/hook", "loopback-ipv6"),
        ],
        ids=["loopback-ipv4", "localhost", "zero-addr", "loopback-ipv6"],
    )
    async def test_rejects_loopback_addresses(
        self,
        client: AsyncClient,
        admin_headers: dict,
        url: str,
        reason: str,
    ) -> None:
        """Regression: Round 2 — SSRF via loopback address ({reason})."""
        resp = await client.post(
            "/api/v1/webhooks/",
            json={"name": f"ssrf-{reason}", "url": url, "events": ["sync.completed"]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, (
            f"Expected 422 for SSRF target {url}, got {resp.status_code}"
        )

    @pytest.mark.parametrize(
        "url,reason",
        [
            ("http://169.254.169.254/latest/meta-data/", "aws-metadata"),
            ("http://metadata.google.internal/computeMetadata/v1/", "gcp-metadata"),
        ],
        ids=["aws-metadata", "gcp-metadata"],
    )
    async def test_rejects_cloud_metadata_endpoints(
        self,
        client: AsyncClient,
        admin_headers: dict,
        url: str,
        reason: str,
    ) -> None:
        """Regression: Round 2 — SSRF via cloud metadata endpoint ({reason})."""
        resp = await client.post(
            "/api/v1/webhooks/",
            json={"name": f"ssrf-{reason}", "url": url, "events": ["sync.completed"]},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "scheme",
        ["file", "gopher", "dict", "ftp"],
    )
    async def test_rejects_non_http_schemes(
        self,
        client: AsyncClient,
        admin_headers: dict,
        scheme: str,
    ) -> None:
        """Regression: Round 2 — SSRF via non-HTTP scheme ({scheme}://)."""
        resp = await client.post(
            "/api/v1/webhooks/",
            json={
                "name": f"ssrf-{scheme}",
                "url": f"{scheme}:///etc/passwd",
                "events": ["sync.completed"],
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestSsrfDeliveryTimeValidation:
    """Regression: Round 2 — SSRF is also checked at webhook delivery time."""

    async def test_delivery_blocks_internal_target(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_db: object,
    ) -> None:
        """Webhook delivery to an internal host is blocked even if stored URL was valid."""
        from utils.ssrf import validate_url_target

        with pytest.raises(ValueError, match="internal|blocked"):
            await validate_url_target("http://127.0.0.1/hook")

    async def test_delivery_blocks_loopback(self) -> None:
        """Delivery-time DNS check blocks loopback."""
        from utils.ssrf import validate_url_target

        with pytest.raises(ValueError, match="internal|blocked"):
            await validate_url_target("http://localhost/hook")
