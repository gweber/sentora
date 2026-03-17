"""CrowdStrike Falcon API client.

Wraps the FalconPy SDK with async execution (via ``asyncio.to_thread``),
rate-limit-aware retry, and structured error handling.  All sync modules
use this client instead of calling FalconPy directly.

FalconPy is synchronous — every SDK call is wrapped in ``to_thread`` so the
event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from .entities import AppPageResult, ConnectionTestDetail, ScrollResult
from .errors import (
    CSApiError,
    CSAuthError,
    CSDiscoverNotLicensedError,
    CSRateLimitError,
    CSScopeError,
)

# Maximum retries for transient errors (rate limit, 5xx)
_MAX_RETRIES = 3

# Base backoff seconds for rate-limit retries
_RATE_LIMIT_BACKOFF = 30

# Base backoff seconds for server-error retries
_SERVER_ERROR_BACKOFF = 15


def _check_response(resp: dict[str, Any], context: str = "") -> None:
    """Raise appropriate error for non-2xx FalconPy responses.

    FalconPy returns the HTTP status in ``resp["status_code"]`` rather than
    raising exceptions, so every call site must check the status.

    Args:
        resp: FalconPy response dict.
        context: Human-readable context for error messages.

    Raises:
        CSAuthError: On 401/403.
        CSRateLimitError: On 429.
        CSApiError: On any other non-2xx status.
    """
    status = resp.get("status_code", 0)
    if 200 <= status < 300:
        return

    body_str = str(resp.get("body", ""))[:300]
    if status in (401, 403):
        raise CSAuthError(f"Authentication failed ({status}): {body_str}")
    if status == 429:
        # Parse retry-after from headers if available
        headers = resp.get("headers", {})
        retry_after = int(headers.get("X-RateLimit-RetryAfter", _RATE_LIMIT_BACKOFF))
        raise CSRateLimitError(retry_after=retry_after, message=f"{context}: rate limited")
    raise CSApiError(status, body_str, context)


class CrowdStrikeClient:
    """Async wrapper around the FalconPy SDK.

    Creates one FalconPy service class per API domain (Hosts, Discover,
    HostGroup) with shared OAuth2 credentials.  Token refresh is handled
    automatically by FalconPy.

    All public methods are async — FalconPy's synchronous HTTP calls are
    dispatched via ``asyncio.to_thread`` to keep the event loop free.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = "auto",
        member_cid: str | None = None,
    ) -> None:
        from falconpy import Discover, HostGroup, Hosts

        kwargs: dict[str, Any] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if base_url and base_url != "auto":
            kwargs["base_url"] = base_url
        if member_cid:
            kwargs["member_cid"] = member_cid

        self._hosts = Hosts(**kwargs)
        self._discover = Discover(**kwargs)
        self._host_groups = HostGroup(**kwargs)

        # Simple rate-limit tracking
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0
        # CrowdStrike allows ~6000 calls / 15 min → ~6.67 calls/s
        self._min_interval: float = 0.15

    async def close(self) -> None:
        """Release resources.  FalconPy uses ``requests.Session`` internally."""
        # FalconPy doesn't expose an explicit close — nothing to do
        pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Enforce minimum interval between requests."""
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

    async def _call(self, fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401
        """Rate-limited, async FalconPy call with retry on transient errors.

        Args:
            fn: FalconPy service method (synchronous).
            *args: Positional args forwarded to ``fn``.
            **kwargs: Keyword args forwarded to ``fn``.

        Returns:
            FalconPy response dict.

        Raises:
            CSAuthError: On authentication failure (no retry).
            CSRateLimitError: After exhausting retries on 429.
            CSApiError: After exhausting retries on server errors.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            await self._throttle()
            try:
                resp: dict[str, Any] = await asyncio.to_thread(fn, *args, **kwargs)
                _check_response(resp, context=fn.__qualname__)
                return resp
            except CSAuthError:
                raise
            except CSRateLimitError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    backoff = min(exc.retry_after, _RATE_LIMIT_BACKOFF * (2**attempt))
                    logger.warning(
                        "CS rate limited, retry {}/{} in {}s",
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise
            except CSApiError as exc:
                last_exc = exc
                if exc.status_code >= 500 and attempt < _MAX_RETRIES:
                    backoff = min(_SERVER_ERROR_BACKOFF * (2**attempt), 120)
                    logger.warning(
                        "CS server error ({}), retry {}/{} in {}s",
                        exc.status_code,
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise

        # Should not reach here, but just in case
        if last_exc:
            raise last_exc
        raise CSApiError(0, "Unexpected retry loop exit")  # pragma: no cover

    # ── Hosts API ─────────────────────────────────────────────────────────────

    async def scroll_hosts(
        self,
        *,
        limit: int = 5000,
        offset: str = "",
        filter_fql: str = "",
    ) -> ScrollResult:
        """Scroll through host AIDs using cursor-based pagination.

        Args:
            limit: Max AIDs per page (up to 5000).
            offset: Scroll cursor from a previous call (empty for first page).
            filter_fql: FQL filter expression (e.g. ``"modified_timestamp:>'2024-01-01'"``).

        Returns:
            ScrollResult with AIDs and next cursor.
        """
        kwargs: dict[str, Any] = {
            "limit": min(limit, 5000),
            "sort": "hostname.asc",
        }
        if offset:
            kwargs["offset"] = offset
        if filter_fql:
            kwargs["filter"] = filter_fql

        resp = await self._call(self._hosts.query_devices_by_filter_scroll, **kwargs)
        body = resp.get("body", {})
        resources = body.get("resources", [])
        pagination = body.get("meta", {}).get("pagination", {})
        return ScrollResult(
            aids=resources,
            next_offset=pagination.get("offset", ""),
            total=pagination.get("total", 0),
        )

    async def get_host_details(self, aids: list[str]) -> list[dict[str, Any]]:
        """Fetch full device details for a batch of AIDs.

        Args:
            aids: List of Agent IDs (max 5000 per call).

        Returns:
            List of host detail dicts.
        """
        if not aids:
            return []
        # FalconPy accepts ids as a list
        resp = await self._call(self._hosts.get_device_details_v2, ids=aids)
        body = resp.get("body", {})
        return body.get("resources", [])

    async def scroll_all_hosts(
        self,
        *,
        filter_fql: str = "",
        batch_size: int = 5000,
    ) -> AsyncIterator[tuple[int, list[dict[str, Any]]]]:
        """Yield (total, batch_of_host_details) by scrolling + fetching details.

        Combines ``QueryDevicesByFilterScroll`` with ``GetDeviceDetailsV2``
        to stream host details in batches.  Yields ``(total, host_details)``
        where ``total`` is emitted on the first batch only (0 thereafter).

        Args:
            filter_fql: FQL filter for the scroll query.
            batch_size: AIDs per scroll page (max 5000).
        """
        offset = ""
        first_page = True
        while True:
            result = await self.scroll_hosts(
                limit=batch_size,
                offset=offset,
                filter_fql=filter_fql,
            )
            if not result.aids:
                break

            details = await self.get_host_details(result.aids)
            yield (result.total if first_page else 0), details
            first_page = False

            if not result.next_offset:
                break
            offset = result.next_offset

    # ── Host Groups API ───────────────────────────────────────────────────────

    async def get_host_groups(self) -> dict[str, str]:
        """Fetch all host groups and return a ``{group_id: group_name}`` mapping.

        Returns:
            Dict mapping CrowdStrike group IDs to their display names.
        """
        group_map: dict[str, str] = {}
        offset = 0
        while True:
            resp = await self._call(
                self._host_groups.query_combined_host_groups,
                limit=500,
                offset=offset,
            )
            body = resp.get("body", {})
            resources = body.get("resources", [])
            for grp in resources:
                gid = grp.get("id", "")
                gname = grp.get("name", "")
                if gid:
                    group_map[gid] = gname
            if len(resources) < 500:
                break
            offset += len(resources)
        return group_map

    # ── Discover API (Applications) ───────────────────────────────────────────

    async def get_applications(
        self,
        *,
        after: str = "",
        limit: int = 100,
        filter_fql: str = "",
    ) -> AppPageResult:
        """Fetch a page of applications from Falcon Discover.

        Args:
            after: Cursor for the next page (empty for first page).
            limit: Max applications per page (up to 100).
            filter_fql: FQL filter expression (e.g. ``"aid:'<device_id>'"``).

        Returns:
            AppPageResult with applications and next cursor.

        Raises:
            CSDiscoverNotLicensedError: If Falcon Discover is not licensed.
        """
        kwargs: dict[str, Any] = {
            "limit": min(limit, 100),
            "sort": "name.asc",
        }
        if after:
            kwargs["after"] = after
        if filter_fql:
            kwargs["filter"] = filter_fql

        try:
            resp = await self._call(
                self._discover.query_combined_applications,
                **kwargs,
            )
        except CSApiError as exc:
            # 403 on Discover typically means the module is not licensed
            if exc.status_code == 403 and "discover" in exc.body.lower():
                raise CSDiscoverNotLicensedError from exc
            raise

        body = resp.get("body", {})
        resources = body.get("resources", [])
        pagination = body.get("meta", {}).get("pagination", {})
        return AppPageResult(
            applications=resources,
            after=pagination.get("after", ""),
            total=pagination.get("total", 0),
        )

    async def scroll_all_applications(
        self,
        *,
        filter_fql: str = "",
        page_size: int = 100,
    ) -> AsyncIterator[tuple[int, dict[str, Any]]]:
        """Yield (total, app_dict) for all applications via cursor pagination.

        ``total`` is emitted on the first item only (0 for all subsequent).

        Args:
            filter_fql: FQL filter to scope the query.
            page_size: Applications per page (max 100).
        """
        after = ""
        first_item = True
        while True:
            page = await self.get_applications(
                after=after,
                limit=page_size,
                filter_fql=filter_fql,
            )
            for app in page.applications:
                yield (page.total if first_item else 0), app
                first_item = False

            if not page.after:
                break
            after = page.after

    # ── Connection Test ───────────────────────────────────────────────────────

    async def test_connection(self) -> ConnectionTestDetail:
        """Verify credentials and detect available API scopes.

        Returns:
            ConnectionTestDetail with scope availability and host count.
        """
        detail = ConnectionTestDetail()
        start = time.monotonic()

        # 1. Test Hosts: READ
        try:
            result = await self.scroll_hosts(limit=1)
            detail = ConnectionTestDetail(
                hosts_readable=True,
                host_count=result.total,
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except CSAuthError:
            return ConnectionTestDetail(
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except (CSApiError, CSScopeError):
            pass

        # 2. Test Falcon Discover: READ
        try:
            await self.get_applications(limit=1)
            detail = ConnectionTestDetail(
                hosts_readable=detail.hosts_readable,
                discover_readable=True,
                host_groups_readable=detail.host_groups_readable,
                host_count=detail.host_count,
                latency_ms=detail.latency_ms,
            )
        except (CSDiscoverNotLicensedError, CSApiError, CSScopeError):
            pass

        # 3. Test Host Groups: READ
        try:
            await self._call(
                self._host_groups.query_combined_host_groups,
                limit=1,
            )
            detail = ConnectionTestDetail(
                hosts_readable=detail.hosts_readable,
                discover_readable=detail.discover_readable,
                host_groups_readable=True,
                host_count=detail.host_count,
                latency_ms=detail.latency_ms,
            )
        except (CSApiError, CSScopeError):
            pass

        return detail
