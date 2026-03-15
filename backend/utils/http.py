"""HTTP request utilities shared across middleware and domain code."""

from __future__ import annotations

import ipaddress

from fastapi import Request

from config import get_settings

#: Default proxy IPs trusted for X-Forwarded-For extraction
#: (localhost + common Docker bridge networks).
_DEFAULT_TRUSTED_PROXIES: frozenset[str] = frozenset(
    {
        "127.0.0.1",
        "::1",
        "172.17.0.1",
        "172.18.0.1",
    }
)

_cached_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None


def _trusted_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Return the list of trusted proxy networks, loading from config once.

    The config field ``trusted_proxy_cidrs`` accepts a comma-separated list
    of CIDRs (e.g. ``"10.0.0.0/8,172.16.0.0/12"``).  When empty, the
    hardcoded defaults are used.
    """
    global _cached_networks  # noqa: PLW0603
    if _cached_networks is not None:
        return _cached_networks

    settings = get_settings()
    raw = getattr(settings, "trusted_proxy_cidrs", "")
    cidrs: list[str] = [c.strip() for c in raw.split(",") if c.strip()] if raw else []
    if cidrs:
        _cached_networks = [ipaddress.ip_network(c, strict=False) for c in cidrs]
    else:
        _cached_networks = [ipaddress.ip_network(ip) for ip in _DEFAULT_TRUSTED_PROXIES]
    return _cached_networks


def _is_trusted_proxy(host: str) -> bool:
    """Check whether the given IP address belongs to a trusted proxy network."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_networks())


def client_ip(request: Request) -> str:
    """Extract the originating client IP from a FastAPI request.

    Trusts the ``X-Forwarded-For`` header only when the direct connection
    originates from a known reverse-proxy IP.  Otherwise returns the raw
    TCP peer address.

    Args:
        request: The incoming FastAPI/Starlette request.

    Returns:
        The client IP address as a string.
    """
    host = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(host):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return host
