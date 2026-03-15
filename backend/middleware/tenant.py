"""Tenant resolution middleware.

Resolves the current tenant from the X-Tenant-ID header or subdomain
and sets the tenant database name on the request state.

When multi-tenancy is disabled, this middleware is not mounted and
all requests use the default database.
"""

from __future__ import annotations

import time
from collections import OrderedDict

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from config import get_settings
from database import DatabaseUnavailableError

# In-memory tenant cache: slug -> (tenant_doc, cached_at)
# Uses OrderedDict for LRU-style eviction to avoid thundering herd on full clear.
_tenant_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
_CACHE_TTL = 60  # seconds
_TENANT_CACHE_MAX = 10_000

# Paths exempt from tenant resolution
_EXEMPT_PREFIXES = (
    "/health",
    "/metrics",
    "/api/v1/tenants",
    "/api/v1/branding",
    "/api/v1/auth/saml/metadata",
    "/api/spec",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant from request headers or subdomain.

    Sets ``request.state.tenant`` and ``request.state.tenant_db_name``
    for downstream handlers to use.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:  # noqa: ANN001
        """Resolve tenant and set on request state."""
        path = request.url.path

        # Skip tenant resolution for exempt paths (match prefix + "/" or exact)
        if any(path == prefix or path.startswith(prefix + "/") for prefix in _EXEMPT_PREFIXES):
            request.state.tenant = None
            request.state.tenant_db_name = get_settings().mongo_db
            return await call_next(request)

        # Resolve tenant slug from header or subdomain
        slug = self._resolve_slug(request)
        if not slug:
            return JSONResponse(
                {
                    "detail": (
                        "Tenant not specified. Provide "
                        "X-Tenant-ID header or use a "
                        "tenant subdomain."
                    )
                },
                status_code=400,
            )

        # Look up tenant (with caching)
        tenant_doc = await self._get_tenant(slug)
        if tenant_doc is None:
            return JSONResponse(
                {"detail": f"Tenant '{slug}' not found"},
                status_code=404,
            )

        if tenant_doc.get("disabled"):
            return JSONResponse(
                {"detail": f"Tenant '{slug}' is disabled"},
                status_code=403,
            )

        request.state.tenant = tenant_doc
        request.state.tenant_db_name = tenant_doc.get("database_name", get_settings().mongo_db)

        return await call_next(request)

    @staticmethod
    def _resolve_slug(request: Request) -> str | None:
        """Extract tenant slug from X-Tenant-ID header or Host subdomain."""
        # 1. Check explicit header
        tenant_header = request.headers.get("x-tenant-id")
        if tenant_header:
            return tenant_header.strip().lower()

        # 2. Extract subdomain from Host header
        host = request.headers.get("host", "")
        # Strip port
        hostname = host.split(":")[0]
        parts = hostname.split(".")
        # Subdomain-based: acme.sentora.example.com → slug = "acme"
        if len(parts) >= 3:
            subdomain = parts[0]
            # Ignore common non-tenant subdomains
            if subdomain not in ("www", "api", "app", "localhost"):
                return subdomain

        return None

    async def _get_tenant(self, slug: str) -> dict | None:
        """Look up tenant by slug with in-memory cache."""
        now = time.time()
        cached = _tenant_cache.get(slug)
        if cached and (now - cached[1]) < _CACHE_TTL:
            if slug in _tenant_cache:
                _tenant_cache.move_to_end(slug)  # mark as recently used
            return cached[0]

        # Fetch from master database
        try:
            from database import get_client

            settings = get_settings()
            master_db = get_client()[settings.master_db_name]
            doc = await master_db["tenants"].find_one({"slug": slug})
            if doc:
                tenant_dict = {
                    "id": str(doc["_id"]),
                    "name": doc.get("name"),
                    "slug": doc.get("slug"),
                    "database_name": doc.get("database_name"),
                    "disabled": doc.get("disabled", False),
                    "plan": doc.get("plan", "standard"),
                }
                _tenant_cache[slug] = (tenant_dict, now)
                _tenant_cache.move_to_end(slug)
                while len(_tenant_cache) > _TENANT_CACHE_MAX:
                    _tenant_cache.popitem(last=False)  # evict oldest
                return tenant_dict
            return None
        except DatabaseUnavailableError:
            raise  # Let global error handler return 503
        except Exception as exc:
            logger.error("Tenant lookup failed for slug '{}': {}", slug, exc)
            raise
