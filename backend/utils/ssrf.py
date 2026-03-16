"""SSRF protection constants and utilities.

Provides a shared set of blocked hostnames used by both webhook URL
validation (DTO layer) and delivery-time DNS resolution checks (service
layer).  Keeping these in one place prevents the two lists from drifting.
"""

from __future__ import annotations

import asyncio
import ipaddress

#: Hostnames that must never be targeted by outbound HTTP requests.
BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",  # noqa: S104  # nosec B104 — SSRF blocklist entry, not a bind address
        "metadata.google.internal",
    }
)


def is_private_ip(addr_str: str) -> bool:
    """Check if an IP address string is private, loopback, link-local, or reserved.

    Args:
        addr_str: IP address as a string.

    Returns:
        True if the address is internal/reserved.
    """
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        return False
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


async def validate_url_target(url: str) -> None:
    """Validate that a URL does not resolve to an internal/reserved host.

    Performs async DNS resolution and checks each resolved address against
    the private/reserved ranges.

    Args:
        url: The URL to validate.

    Raises:
        ValueError: If the URL targets a blocked host, uses a disallowed
            scheme, or resolves to an internal IP address.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)

    # AUDIT-046: Only allow http and https schemes
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed — only http and https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("No hostname in URL")

    if hostname.lower() in BLOCKED_HOSTS:
        raise ValueError(f"Delivery blocked: internal host {hostname}")

    loop = asyncio.get_running_loop()
    addrs = await loop.getaddrinfo(hostname, None)
    for info in addrs:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError(f"Delivery blocked: resolves to internal IP ({addr})")


async def resolve_and_validate(url: str) -> str:
    """Validate a URL and return the resolved IP for connection pinning.

    This addresses DNS rebinding attacks (AUDIT-007) by resolving DNS
    during validation and returning the resolved IP so callers can pin
    their HTTP connection to the validated address rather than re-resolving
    at connect time.

    Args:
        url: The URL to validate.

    Returns:
        The first safe resolved IP address as a string. Callers should
        use this IP for the actual HTTP request to prevent DNS rebinding.

    Raises:
        ValueError: If the URL is unsafe (blocked host, private IP,
            disallowed scheme, etc.).
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed — only http and https")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("No hostname in URL")

    if hostname.lower() in BLOCKED_HOSTS:
        raise ValueError(f"Delivery blocked: internal host {hostname}")

    loop = asyncio.get_running_loop()
    addrs = await loop.getaddrinfo(hostname, None)

    safe_ip: str | None = None
    for info in addrs:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError(f"Delivery blocked: resolves to internal IP ({addr})")
        if safe_ip is None:
            safe_ip = str(addr)

    if safe_ip is None:
        raise ValueError(f"DNS resolution returned no addresses for {hostname}")

    return safe_ip
