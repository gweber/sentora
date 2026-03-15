"""Tests for the consolidated rate limiter."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from utils.rate_limit import RateLimiter


class TestRateLimiter:
    """Test the sliding-window rate limiter."""

    def test_allows_requests_under_limit(self) -> None:
        """Requests under the limit should not be rate-limited."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_limited("1.2.3.4") is False
        assert limiter.is_limited("1.2.3.4") is False
        assert limiter.is_limited("1.2.3.4") is False

    def test_blocks_requests_at_limit(self) -> None:
        """The request that hits the limit should be blocked."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_limited("1.2.3.4") is False  # 1st
        assert limiter.is_limited("1.2.3.4") is False  # 2nd
        assert limiter.is_limited("1.2.3.4") is True   # 3rd = blocked

    def test_different_ips_are_independent(self) -> None:
        """Each IP has its own counter."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_limited("1.1.1.1") is False
        assert limiter.is_limited("2.2.2.2") is False
        assert limiter.is_limited("1.1.1.1") is True  # 1.1.1.1 is now limited
        assert limiter.is_limited("2.2.2.2") is True  # 2.2.2.2 is now limited

    def test_window_expiry_resets_counter(self) -> None:
        """Requests older than the window should not count."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_limited("1.1.1.1") is False
        assert limiter.is_limited("1.1.1.1") is True

        # Manually expire the entry
        limiter._hits["1.1.1.1"] = [time.monotonic() - 2]
        assert limiter.is_limited("1.1.1.1") is False  # window expired

    def test_reset_clears_all(self) -> None:
        """reset() should clear all tracked hits."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_limited("1.1.1.1") is False
        assert limiter.is_limited("1.1.1.1") is True
        limiter.reset()
        assert limiter.is_limited("1.1.1.1") is False  # reset worked

    def test_check_raises_429_when_limited(self) -> None:
        """check() should raise HTTPException 429 when rate-limited."""
        from fastapi import HTTPException

        limiter = RateLimiter(max_requests=1, window_seconds=60)
        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {}

        limiter.check(mock_request)  # 1st — ok

        with pytest.raises(HTTPException) as exc_info:
            limiter.check(mock_request)  # 2nd — blocked

        assert exc_info.value.status_code == 429
