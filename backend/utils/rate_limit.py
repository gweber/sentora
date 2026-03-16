"""In-memory sliding-window rate limiter.

Provides a lightweight, dependency-free rate limiter suitable for
single-worker deployments.  For multi-worker scaling, replace with
a Redis-backed implementation.

.. warning:: Multi-worker limitation

    This limiter maintains state in process-local memory.  When running
    behind a process-based server (e.g. ``uvicorn --workers N``, gunicorn),
    each worker holds its own counter, so the effective limit is multiplied
    by the number of workers.  A startup warning is emitted when
    ``WEB_CONCURRENCY`` or ``--workers`` indicates more than one process.
    For strict enforcement across workers, use a shared store such as Redis.

Used by both:
- ``middleware/rate_limit.py`` (global per-IP middleware)
- Individual endpoint limiters in domain routers (e.g. login, register)

Usage::

    from utils.rate_limit import RateLimiter

    _login_limiter = RateLimiter(max_requests=5, window_seconds=60)

    @router.post("/login")
    async def login(request: Request):
        _login_limiter.check(request)
        ...
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from utils.http import client_ip


def _check_multi_worker_warning() -> None:
    """Emit a warning at import time if multiple workers are detected."""
    workers = os.environ.get("WEB_CONCURRENCY", "1")
    try:
        if int(workers) > 1:
            import logging

            logging.getLogger(__name__).warning(
                "In-memory RateLimiter is active with WEB_CONCURRENCY=%s. "
                "Rate limits will be per-worker, effectively multiplied by "
                "the worker count. Consider a Redis-backed limiter for "
                "accurate cross-worker enforcement.",
                workers,
            )
    except (ValueError, TypeError):
        pass


_check_multi_worker_warning()


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP.

    Args:
        max_requests: Maximum number of requests allowed within the window.
        window_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._request_count: int = 0

    def is_limited(self, ip: str) -> bool:
        """Check if the IP has exceeded the rate limit; record the hit if not.

        Returns True if rate-limited, False otherwise.  When False, the
        current request is counted towards the window.

        Args:
            ip: Client IP address string.

        Returns:
            True if the client should be rejected (rate-limited).
        """
        now = time.monotonic()
        cutoff = now - self._window

        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

        if len(self._hits[ip]) >= self._max:
            return True

        self._hits[ip].append(now)

        # Periodic cleanup of stale IPs
        self._request_count += 1
        if self._request_count % 200 == 0:
            self._cleanup()

        return False

    def check(self, request: Request) -> None:
        """Raise 429 if the client has exceeded the rate limit.

        Convenience method for endpoint-level usage.

        Args:
            request: The incoming FastAPI request.

        Raises:
            HTTPException: 429 Too Many Requests.
        """
        ip = client_ip(request)
        if self.is_limited(ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded — max {self._max} requests per {self._window}s",
                headers={"Retry-After": str(self._window)},
            )

    def _cleanup(self) -> None:
        """Remove IPs whose newest timestamp is older than the window."""
        cutoff = time.monotonic() - self._window
        stale = [ip for ip, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for ip in stale:
            del self._hits[ip]

    def reset(self) -> None:
        """Clear all tracked hits. Useful for testing."""
        self._hits.clear()
