"""Request logging middleware.

Logs every incoming request and outgoing response with:
  - HTTP method and path
  - Response status code
  - Response time in milliseconds
  - A correlation ID (taken from ``X-Request-ID`` header or auto-generated)

Uses loguru for structured output.
"""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs each request/response pair with timing and a correlation ID.

    Attaches an ``X-Request-ID`` header to every response for distributed
    tracing. The correlation ID is taken from the incoming header if present,
    otherwise a new UUID4 is generated.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request, log it, and attach timing/correlation headers.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler in the chain.

        Returns:
            The HTTP response with ``X-Request-ID`` header attached.
        """
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning(
                "{} {} 500 {}ms [rid={}]",
                request.method,
                request.url.path,
                elapsed_ms,
                correlation_id,
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = correlation_id

        logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=elapsed_ms,
            correlation_id=correlation_id,
        ).info("{} {} {} {}ms", request.method, request.url.path, response.status_code, elapsed_ms)

        return response
