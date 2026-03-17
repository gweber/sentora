"""Extended tests for SSRF protection — covers validate_url_target and resolve_and_validate."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from utils.ssrf import is_private_ip, resolve_and_validate, validate_url_target


class TestValidateUrlTarget:
    """Tests for validate_url_target covering all rejection branches."""

    @pytest.mark.asyncio
    async def test_rejects_ftp_scheme(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            await validate_url_target("ftp://example.com/file")

    @pytest.mark.asyncio
    async def test_rejects_javascript_scheme(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            await validate_url_target("javascript:alert(1)")

    @pytest.mark.asyncio
    async def test_rejects_empty_hostname(self) -> None:
        with pytest.raises(ValueError, match="No hostname"):
            await validate_url_target("http:///path")

    @pytest.mark.asyncio
    async def test_rejects_blocked_host_metadata(self) -> None:
        with pytest.raises(ValueError, match="internal host"):
            await validate_url_target("http://metadata.google.internal/computeMetadata")

    @pytest.mark.asyncio
    async def test_rejects_zero_address(self) -> None:
        with pytest.raises(ValueError, match="internal"):
            await validate_url_target("http://0.0.0.0:80/hook")

    @pytest.mark.asyncio
    async def test_rejects_dns_resolving_to_private(self) -> None:
        """URL whose DNS resolves to a private IP must be rejected."""
        fake_addrs = [(2, 1, 6, "", ("10.0.0.1", 0))]
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=fake_addrs)
            with pytest.raises(ValueError, match="internal IP"):
                await validate_url_target("https://evil.example.com/hook")

    @pytest.mark.asyncio
    async def test_allows_public_ip(self) -> None:
        """URL resolving to a public IP should pass."""
        fake_addrs = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=fake_addrs)
            await validate_url_target("https://example.com/hook")


class TestResolveAndValidate:
    """Tests for resolve_and_validate covering all branches."""

    @pytest.mark.asyncio
    async def test_rejects_ftp_scheme(self) -> None:
        with pytest.raises(ValueError, match="not allowed"):
            await resolve_and_validate("ftp://example.com/file")

    @pytest.mark.asyncio
    async def test_rejects_empty_hostname(self) -> None:
        with pytest.raises(ValueError, match="No hostname"):
            await resolve_and_validate("http:///path")

    @pytest.mark.asyncio
    async def test_rejects_blocked_host(self) -> None:
        with pytest.raises(ValueError, match="internal host"):
            await resolve_and_validate("https://localhost/hook")

    @pytest.mark.asyncio
    async def test_rejects_private_ip_resolution(self) -> None:
        fake_addrs = [(2, 1, 6, "", ("192.168.1.1", 0))]
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=fake_addrs)
            with pytest.raises(ValueError, match="internal IP"):
                await resolve_and_validate("https://evil.example.com/hook")

    @pytest.mark.asyncio
    async def test_returns_safe_ip(self) -> None:
        fake_addrs = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=fake_addrs)
            ip = await resolve_and_validate("https://example.com/hook")
            assert ip == "93.184.216.34"

    @pytest.mark.asyncio
    async def test_rejects_empty_dns_result(self) -> None:
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=[])
            with pytest.raises(ValueError, match="no addresses"):
                await resolve_and_validate("https://no-records.example.com/hook")

    @pytest.mark.asyncio
    async def test_returns_first_safe_ip_from_multiple(self) -> None:
        fake_addrs = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("93.184.216.35", 0)),
        ]
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.getaddrinfo = AsyncMock(return_value=fake_addrs)
            ip = await resolve_and_validate("https://example.com/hook")
            assert ip == "93.184.216.34"


class TestIsPrivateIpExtended:
    """Additional edge cases for is_private_ip."""

    def test_ipv6_loopback(self) -> None:
        assert is_private_ip("::1") is True

    def test_ipv6_link_local(self) -> None:
        assert is_private_ip("fe80::1") is True

    def test_reserved_address(self) -> None:
        assert is_private_ip("240.0.0.1") is True

    def test_empty_string(self) -> None:
        assert is_private_ip("") is False
