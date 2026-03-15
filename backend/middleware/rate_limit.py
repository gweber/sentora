"""Global sliding-window rate limiting middleware.

Applies per-IP rate limits to all inbound API requests.  Uses the shared
``RateLimiter`` from ``utils.rate_limit`` to avoid duplicating the
sliding-window implementation.

Exempt paths: /health, /health/ready, /metrics (infrastructure endpoints).
Stricter limits on /api/v1/auth/login to mitigate brute-force attacks.
"""

from __future__ import annotations

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from config import get_settings
from utils.http import client_ip
from utils.rate_limit import RateLimiter

# Paths exempt from rate limiting
_EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/health/ready", "/metrics"})

# Paths with stricter rate limits (requests per minute)
_STRICT_LIMITS: dict[str, int] = {
    "/api/v1/auth/login": 5,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP.

    Uses the shared ``RateLimiter`` class for both global and per-path
    buckets.  Stale entries are cleaned up by the underlying implementation.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        settings = get_settings()

        # Global rate limiter
        self._global_limiter = RateLimiter(
            max_requests=settings.rate_limit_per_minute,
            window_seconds=60,
        )

        # Per-path strict limiters
        self._strict_limiters: dict[str, RateLimiter] = {
            path: RateLimiter(max_requests=limit, window_seconds=60)
            for path, limit in _STRICT_LIMITS.items()
        }

        logger.info(
            "Rate limit middleware initialised: {} req/min global, strict paths: {}",
            settings.rate_limit_per_minute,
            _STRICT_LIMITS,
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:  # type: ignore[override]
        """Check rate limits before forwarding the request.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            The HTTP response, or 429 if rate limited.
        """
        path = request.url.path.rstrip("/") or "/"

        if path in _EXEMPT_PATHS:
            return await call_next(request)

        ip = client_ip(request)

        # Check strict per-path limit first
        strict = self._strict_limiters.get(path)
        if strict and strict.is_limited(ip):
            logger.warning("Rate limit (strict) hit: ip={} path={}", ip, path)
            return self._too_many_requests()

        # Check global limit
        if self._global_limiter.is_limited(ip):
            logger.warning("Rate limit (global) hit: ip={}", ip)
            return self._too_many_requests()

        return await call_next(request)

    @staticmethod
    def _too_many_requests() -> JSONResponse:
        """Return a 429 JSON response with Retry-After header."""
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": "60"},
        )
