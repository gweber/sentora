"""Tests for SSRF protection utilities."""

from __future__ import annotations

import pytest

from utils.ssrf import BLOCKED_HOSTS, is_private_ip


class TestBlockedHosts:
    """Verify the blocked hosts constant contains all expected entries."""

    def test_contains_localhost(self) -> None:
        assert "localhost" in BLOCKED_HOSTS

    def test_contains_loopback_ipv4(self) -> None:
        assert "127.0.0.1" in BLOCKED_HOSTS

    def test_contains_loopback_ipv6(self) -> None:
        assert "::1" in BLOCKED_HOSTS

    def test_contains_gcp_metadata(self) -> None:
        assert "metadata.google.internal" in BLOCKED_HOSTS


class TestIsPrivateIp:
    """Test private/reserved IP detection."""

    def test_loopback_is_private(self) -> None:
        assert is_private_ip("127.0.0.1") is True

    def test_rfc1918_10_is_private(self) -> None:
        assert is_private_ip("10.0.0.1") is True

    def test_rfc1918_172_is_private(self) -> None:
        assert is_private_ip("172.16.0.1") is True

    def test_rfc1918_192_is_private(self) -> None:
        assert is_private_ip("192.168.1.1") is True

    def test_public_ip_is_not_private(self) -> None:
        assert is_private_ip("8.8.8.8") is False

    def test_invalid_string_returns_false(self) -> None:
        assert is_private_ip("not-an-ip") is False

    def test_link_local_is_private(self) -> None:
        assert is_private_ip("169.254.1.1") is True


@pytest.mark.asyncio
async def test_validate_url_target_blocks_localhost() -> None:
    """validate_url_target should reject URLs targeting localhost."""
    from utils.ssrf import validate_url_target

    with pytest.raises(ValueError, match="internal host"):
        await validate_url_target("https://localhost:8080/hook")


@pytest.mark.asyncio
async def test_validate_url_target_blocks_private_ip() -> None:
    """validate_url_target should reject URLs resolving to private IPs."""
    from utils.ssrf import validate_url_target

    with pytest.raises(ValueError, match="internal"):
        await validate_url_target("http://127.0.0.1:9999/hook")
