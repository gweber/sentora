"""Global exception handler middleware.

Converts ``SentoraError`` subclasses and unhandled exceptions into
consistent JSON error responses of the form:

    { "error_code": "...", "message": "...", "detail": {} }

Never expose raw stack traces in non-development environments.
"""

from __future__ import annotations

import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from config import get_settings
from database import DatabaseUnavailableError
from errors import SentoraError


async def sentora_error_handler(request: Request, exc: SentoraError) -> JSONResponse:
    """Handle all SentoraError subclasses and return a structured JSON response.

    Args:
        request: The incoming HTTP request (used for logging context).
        exc: The domain error that was raised.

    Returns:
        JSONResponse with the error payload and appropriate HTTP status code.
    """
    logger.warning(
        "Domain error on {} {}: [{}] {}",
        request.method,
        request.url.path,
        exc.error_code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message, "detail": exc.detail},
    )


async def database_unavailable_handler(
    request: Request, exc: DatabaseUnavailableError
) -> JSONResponse:
    """Return 503 with a clear message when MongoDB is not reachable.

    Args:
        request: The incoming HTTP request.
        exc: The DatabaseUnavailableError.

    Returns:
        JSONResponse with HTTP 503 and a user-friendly error message.
    """
    logger.warning("DB unavailable on {} {}: {}", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "error_code": "DB_UNAVAILABLE",
            "message": "Database not available — make sure MongoDB is running",
            "detail": {},
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions and return a generic 500 error.

    Stack traces are included only in development mode.

    Args:
        request: The incoming HTTP request.
        exc: The unhandled exception.

    Returns:
        JSONResponse with a generic error payload and HTTP 500.
    """
    logger.exception("Unhandled exception on {} {}", request.method, request.url.path)
    detail: dict[str, object] = {}
    if get_settings().is_development:
        detail["traceback"] = traceback.format_exc()

    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": detail,
        },
    )
