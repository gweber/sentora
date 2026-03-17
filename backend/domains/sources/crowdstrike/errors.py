"""CrowdStrike-specific error types.

All errors inherit from ``CrowdStrikeError`` so callers can catch the base
class for generic handling or specific subclasses for targeted recovery.
"""

from __future__ import annotations


class CrowdStrikeError(Exception):
    """Base error for all CrowdStrike adapter failures."""


class CSAuthError(CrowdStrikeError):
    """OAuth2 authentication failed (invalid client_id/secret or expired token)."""


class CSRateLimitError(CrowdStrikeError):
    """HTTP 429 — API rate limit exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying (from ``X-RateLimit-RetryAfter``).
    """

    def __init__(self, retry_after: int = 60, message: str = "") -> None:
        self.retry_after = retry_after
        super().__init__(message or f"Rate limited — retry after {retry_after}s")


class CSApiError(CrowdStrikeError):
    """Non-2xx API response from CrowdStrike.

    Attributes:
        status_code: HTTP status code from the response.
        body: Response body (truncated).
    """

    def __init__(self, status_code: int, body: str, url: str = "") -> None:
        url_part = f" [{url}]" if url else ""
        super().__init__(f"CrowdStrike API error {status_code}{url_part}: {body[:300]}")
        self.status_code = status_code
        self.body = body


class CSDiscoverNotLicensedError(CrowdStrikeError):
    """Falcon Discover is not licensed — application inventory unavailable."""

    def __init__(self) -> None:
        super().__init__(
            "Falcon Discover is not licensed on this CrowdStrike tenant. "
            "Application inventory will not be available."
        )


class CSScopeError(CrowdStrikeError):
    """Required API scope is missing from the CrowdStrike API client.

    Attributes:
        scope: The missing scope name.
    """

    def __init__(self, scope: str) -> None:
        self.scope = scope
        super().__init__(f"Missing required CrowdStrike API scope: {scope}")
