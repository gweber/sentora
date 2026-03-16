"""Prometheus metrics middleware.

Tracks request count, duration, and in-flight requests as Prometheus
metrics with labels for method, path template, and status code.

Uses the FastAPI route path template (e.g. ``/api/v1/agents/{id}``)
rather than the actual URL to avoid high-cardinality label explosion.
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# ── Prometheus metrics ────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "path_template", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path_template", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "path_template"],
)


def _get_path_template(request: Request) -> str:
    """Resolve the route path template for the matched route.

    Falls back to the raw path if no route is matched (e.g. 404s) but
    truncates it to avoid cardinality explosion from random paths.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        The route path template string.
    """
    # FastAPI/Starlette stores the matched route on the request scope
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return route.path
    # Unmatched routes (404s, probes, etc.) — use a fixed label to prevent
    # unbounded Prometheus metric cardinality from random paths.
    return "/unmatched"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that records Prometheus request metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Record metrics for each request/response cycle.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            The HTTP response (unmodified).
        """
        path_template = _get_path_template(request)
        method = request.method

        REQUESTS_IN_PROGRESS.labels(method=method, path_template=path_template).inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Record 500 for unhandled exceptions that escape the middleware
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(
                method=method, path_template=path_template, status_code="500"
            ).inc()
            REQUEST_DURATION.labels(
                method=method, path_template=path_template, status_code="500"
            ).observe(duration)
            raise
        finally:
            REQUESTS_IN_PROGRESS.labels(method=method, path_template=path_template).dec()

        duration = time.perf_counter() - start
        status_code = str(response.status_code)
        REQUEST_COUNT.labels(
            method=method, path_template=path_template, status_code=status_code
        ).inc()
        REQUEST_DURATION.labels(
            method=method, path_template=path_template, status_code=status_code
        ).observe(duration)

        return response
