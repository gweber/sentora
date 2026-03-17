"""Unit tests for CrowdStrike error types."""

from __future__ import annotations

from domains.sources.crowdstrike.errors import (
    CrowdStrikeError,
    CSApiError,
    CSAuthError,
    CSDiscoverNotLicensedError,
    CSRateLimitError,
    CSScopeError,
)


class TestCrowdStrikeErrors:
    """Verify error hierarchy and attributes."""

    def test_base_error_is_exception(self) -> None:
        """CrowdStrikeError inherits from Exception."""
        assert issubclass(CrowdStrikeError, Exception)

    def test_auth_error_inherits_base(self) -> None:
        """CSAuthError is a CrowdStrikeError."""
        err = CSAuthError("bad creds")
        assert isinstance(err, CrowdStrikeError)
        assert "bad creds" in str(err)

    def test_rate_limit_error_retry_after(self) -> None:
        """CSRateLimitError stores retry_after."""
        err = CSRateLimitError(retry_after=42)
        assert err.retry_after == 42
        assert isinstance(err, CrowdStrikeError)
        assert "42" in str(err)

    def test_rate_limit_error_default_retry(self) -> None:
        """CSRateLimitError defaults retry_after to 60."""
        err = CSRateLimitError()
        assert err.retry_after == 60

    def test_api_error_attributes(self) -> None:
        """CSApiError stores status_code and body."""
        err = CSApiError(502, "Bad Gateway", "/hosts/query")
        assert err.status_code == 502
        assert err.body == "Bad Gateway"
        assert "/hosts/query" in str(err)
        assert isinstance(err, CrowdStrikeError)

    def test_api_error_truncates_body(self) -> None:
        """CSApiError truncates long bodies to 300 chars."""
        long_body = "x" * 500
        err = CSApiError(500, long_body)
        assert len(str(err)) < 400

    def test_discover_not_licensed(self) -> None:
        """CSDiscoverNotLicensedError has a descriptive message."""
        err = CSDiscoverNotLicensedError()
        assert "not licensed" in str(err).lower()
        assert isinstance(err, CrowdStrikeError)

    def test_scope_error(self) -> None:
        """CSScopeError stores the missing scope."""
        err = CSScopeError("Hosts: READ")
        assert err.scope == "Hosts: READ"
        assert "Hosts: READ" in str(err)
        assert isinstance(err, CrowdStrikeError)
