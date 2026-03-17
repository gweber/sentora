"""Unit tests for utils/http.py — client IP extraction and trusted proxy logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import utils.http as http_mod
from utils.http import _is_trusted_proxy, _trusted_networks, client_ip


@pytest.fixture(autouse=True)
def _reset_network_cache() -> None:
    """Clear the cached networks before each test."""
    http_mod._cached_networks = None


class TestTrustedNetworks:
    """Tests for _trusted_networks config loading."""

    def test_default_networks_include_localhost(self) -> None:
        networks = _trusted_networks()
        assert any("127.0.0.1" in str(n) for n in networks)

    def test_custom_cidrs_from_settings(self) -> None:
        mock_settings = MagicMock()
        mock_settings.trusted_proxy_cidrs = "10.0.0.0/8,172.16.0.0/12"
        with patch("utils.http.get_settings", return_value=mock_settings):
            networks = _trusted_networks()
            assert len(networks) == 2

    def test_caches_result(self) -> None:
        first = _trusted_networks()
        second = _trusted_networks()
        assert first is second


class TestIsTrustedProxy:
    """Tests for _is_trusted_proxy."""

    def test_localhost_is_trusted(self) -> None:
        assert _is_trusted_proxy("127.0.0.1") is True

    def test_public_ip_not_trusted(self) -> None:
        assert _is_trusted_proxy("8.8.8.8") is False

    def test_invalid_ip_returns_false(self) -> None:
        assert _is_trusted_proxy("not-an-ip") is False

    def test_ipv6_loopback_trusted(self) -> None:
        assert _is_trusted_proxy("::1") is True


class TestClientIp:
    """Tests for client_ip extraction."""

    def _make_request(
        self, host: str = "1.2.3.4", forwarded: str | None = None
    ) -> MagicMock:
        request = MagicMock()
        request.client.host = host
        request.headers = {}
        if forwarded is not None:
            request.headers["X-Forwarded-For"] = forwarded
        return request

    def test_direct_connection_returns_host(self) -> None:
        req = self._make_request(host="203.0.113.50")
        assert client_ip(req) == "203.0.113.50"

    def test_trusted_proxy_uses_forwarded_for(self) -> None:
        req = self._make_request(host="127.0.0.1", forwarded="203.0.113.50, 10.0.0.1")
        assert client_ip(req) == "203.0.113.50"

    def test_untrusted_proxy_ignores_forwarded_for(self) -> None:
        req = self._make_request(host="8.8.8.8", forwarded="203.0.113.50")
        assert client_ip(req) == "8.8.8.8"

    def test_no_client_returns_unknown(self) -> None:
        req = MagicMock()
        req.client = None
        assert client_ip(req) == "unknown"

    def test_trusted_proxy_empty_forwarded(self) -> None:
        req = self._make_request(host="127.0.0.1", forwarded="")
        assert client_ip(req) == "127.0.0.1"

    def test_trusted_proxy_no_forwarded_header(self) -> None:
        req = self._make_request(host="127.0.0.1")
        assert client_ip(req) == "127.0.0.1"
