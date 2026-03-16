"""SentinelOne Management API client.

Wraps the S1 REST API with async pagination helpers and token-bucket
rate limiting. The caller is responsible for closing the client
via ``await client.close()``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC
from typing import Any

import httpx
from loguru import logger

_FAR_FUTURE = "2099-12-31T23:59:59Z"


def parse_cursor(cursor: str) -> dict[str, Any]:
    """Decode an S1 cursor (URL-safe base64 JSON) into its payload dict.

    S1 cursors are plain JSON, base64-encoded, sometimes URL-encoded.
    No expiry, no HMAC — just a keyset-pagination bookmark.
    """
    import base64
    import json
    import urllib.parse

    decoded = urllib.parse.unquote(cursor)
    # Add padding if needed
    padded = decoded + "=" * (-len(decoded) % 4)
    return json.loads(base64.b64decode(padded))


def _make_cursor(id_column: str, after_id: int) -> str:
    """Build an S1 cursor for the given view column and ID value."""
    import base64
    import json

    payload = {
        "id_column": id_column,
        "id_value": after_id,
        "id_sort_order": "asc",
        "sort_by_column": id_column,
        "sort_by_value": after_id,
        "sort_order": "asc",
    }
    return base64.b64encode(json.dumps(payload, separators=(",", ": ")).encode()).decode()


def make_app_cursor(after_id: int) -> str:
    """Construct an S1 installed-applications cursor that starts after ``after_id``."""
    return _make_cursor("ApplicationView.id", after_id)


def make_agent_cursor(after_id: int) -> str:
    """Construct an S1 agents cursor that starts after ``after_id``."""
    return _make_cursor("AgentView.id", after_id)


def _s1_dt(dt_str: str) -> str:
    """Normalize an ISO-8601 datetime string to the format S1 accepts.

    S1 rejects microseconds and the ``+00:00`` timezone suffix — it expects
    ``YYYY-MM-DDTHH:MM:SSZ`` (UTC, no sub-seconds, Z suffix).
    """
    from datetime import datetime

    return datetime.fromisoformat(dt_str).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class S1ApiError(Exception):
    """Raised when the S1 API returns a non-2xx response."""

    def __init__(self, status: int, body: str, url: str = "") -> None:
        url_part = f" [{url}]" if url else ""
        super().__init__(f"S1 API error {status}{url_part}: {body[:200]}")
        self.status = status


class S1RateLimitError(S1ApiError):
    """Raised on HTTP 429 — caller should back off."""


class S1Client:
    """Async HTTP client for the SentinelOne Management API.

    Uses cursor-based pagination for list endpoints and a token bucket
    to stay within the configured per-minute rate limit.
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        rate_limit_per_minute: int = 100,
    ) -> None:
        raw = base_url.rstrip("/")
        # Ensure the S1 REST API version prefix is always present
        if not raw.endswith("/web/api/v2.1"):
            raw = f"{raw}/web/api/v2.1"
        self._base_url = raw
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"ApiToken {api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        # Semaphore limits concurrent requests, sleep enforces per-minute rate
        self._rate_limit = rate_limit_per_minute
        self._min_interval = 60.0 / max(rate_limit_per_minute, 1)
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        raw_query: str | None = None,
    ) -> dict[str, Any]:
        """Make a rate-limited GET request.

        ``raw_query`` is appended to the URL verbatim (not percent-encoded) —
        use for S1 range params like ``installedAt__between=a,b`` where the
        comma must not be encoded.

        Raises S1RateLimitError on 429, S1ApiError on other non-2xx.
        """
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

        base = httpx.URL(f"{self._base_url}{path}")
        if params:
            base = base.copy_merge_params({k: v for k, v in params.items() if v is not None})
        if raw_query:
            sep = "&" if base.query else "?"
            url = str(base) + sep + raw_query
        else:
            url = str(base)
        logger.debug("S1 GET {}", url)
        resp = await self._client.get(url)
        if resp.status_code == 429:
            raise S1RateLimitError(429, resp.text, url)
        if not resp.is_success:
            raise S1ApiError(resp.status_code, resp.text, url)
        return resp.json()  # type: ignore[return-value]

    async def _post(
        self,
        path: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Make a rate-limited POST request with a JSON body.

        Raises S1RateLimitError on 429, S1ApiError on other non-2xx.
        """
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

        url = f"{self._base_url}{path}"
        logger.debug("S1 POST {}", url)
        resp = await self._client.post(url, json=body)
        if resp.status_code == 429:
            raise S1RateLimitError(429, resp.text, url)
        if not resp.is_success:
            raise S1ApiError(resp.status_code, resp.text, url)
        return resp.json()  # type: ignore[return-value]

    async def get_tags(self) -> AsyncIterator[dict[str, Any]]:
        """Yield all agent tags from the S1 ``/agents/tags`` endpoint.

        Each tag object contains: id, key, value, description, type,
        scopeLevel, scopeId, scopePath, createdBy, createdAt, updatedAt,
        totalEndpoints, endpointsInCurrentScope, allowEdit.
        """
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "limit": 200,
                "includeChildren": "true",
                "includeParents": "true",
            }
            if cursor:
                params["cursor"] = cursor
            data = await self._get("/agents/tags", params=params)
            for item in data.get("data", []):
                yield item
            cursor = (data.get("pagination") or {}).get("nextCursor")
            if not cursor:
                break

    async def create_tag(
        self,
        name: str,
        scope: str = "account",
        scope_id: str = "",
        value: str = "",
    ) -> dict[str, Any]:
        """Create a new endpoint tag in SentinelOne via the tag-manager API.

        Uses ``POST /tag-manager`` (the newer endpoint-tag system) which stores
        tags with a ``key`` field — matching what ``GET /agents/tags`` returns.

        Args:
            name: Tag key / name (e.g. ``"manufacturing"``).
            scope: Tag scope — ``"account"``, ``"site"``, or ``"group"``.
            scope_id: The scope entity ID (account/site/group ID). Required for
                      all scopes; for account scope pass the account ID.
            value: Optional tag value.

        Returns:
            The created tag object from the S1 API response.
        """
        body: dict[str, Any] = {
            "data": {
                "key": name,
                "type": "endpoints",
                "value": value,
            },
            "filter": {},
        }
        # Scope filter is required by the tag-manager API
        if scope == "site" and scope_id:
            body["filter"]["siteIds"] = [scope_id]
        elif scope == "group" and scope_id:
            body["filter"]["groupIds"] = [scope_id]
        elif scope_id:
            body["filter"]["accountIds"] = [scope_id]
        else:
            # Default: tenant-wide scope (no specific account ID needed)
            body["filter"]["tenant"] = True
        result = await self._post("/tag-manager", body)
        return result.get("data", {})

    async def tag_agents(
        self,
        agent_ids: list[str],
        tag_id: str,
    ) -> None:
        """Add a tag to a list of agents via the S1 manage-tags action endpoint.

        Args:
            agent_ids: S1 agent IDs to tag (pass at most ~100 per call).
            tag_id: The S1 tag ID to apply.
        """
        if not agent_ids:
            return
        body: dict[str, Any] = {
            "filter": {"ids": agent_ids},
            "data": [{"tagId": tag_id, "operation": "add"}],
        }
        await self._post("/agents/actions/manage-tags", body)

    async def get_sites(self) -> AsyncIterator[dict[str, Any]]:
        """Yield all sites, paginating with cursor.

        Note: the sites endpoint wraps results under ``data.sites``
        (not the usual ``data`` array), and includes an ``allSites`` summary key.
        """
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = await self._get("/sites", params=params)
            for item in (data.get("data") or {}).get("sites", []):
                yield item
            cursor = (data.get("pagination") or {}).get("nextCursor")
            if not cursor:
                break

    async def get_groups(
        self,
        updated_since: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield all groups (or those updated since ``updated_since``), paginating with cursor."""
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            if updated_since:
                params["updatedAt__gte"] = _s1_dt(updated_since)
            data = await self._get("/groups", params=params)
            for item in data.get("data", []):
                yield item
            cursor = (data.get("pagination") or {}).get("nextCursor")
            if not cursor:
                break

    async def get_agents(
        self,
        updated_since: str | None = None,
        page_size: int = 100,
        resume_cursor: str | None = None,
    ) -> AsyncIterator[tuple]:
        """Yield (total, page_cursor, item) tuples for active agents.

        Args:
            updated_since: ISO-8601 datetime string for incremental sync.
            page_size: Records per API page (default 100, max ~1000).
            resume_cursor: S1 cursor to resume a previously interrupted sweep.
        """
        cursor = resume_cursor
        first_page = resume_cursor is None
        while True:
            params: dict[str, Any] = {"limit": page_size, "isDecommissioned": "false"}
            if cursor:
                params["cursor"] = cursor
            if updated_since:
                params["updatedAt__gte"] = _s1_dt(updated_since)
            data = await self._get("/agents", params=params)
            items = data.get("data", [])
            pagination = data.get("pagination") or {}
            page_cursor = cursor  # cursor that produced this page — resume point
            total = pagination.get("totalItems") or None
            if first_page:
                logger.info(
                    "S1 /agents first page: {} items, totalItems={}, nextCursor={}",
                    len(items),
                    total,
                    bool(pagination.get("nextCursor")),
                )
            first_page = False
            for item in items:
                yield total, page_cursor, item
                total = None  # only emit once per page (first item)
            cursor = pagination.get("nextCursor")
            if not cursor:
                break

    async def get_decommissioned_agent_ids(
        self,
        updated_since: str | None = None,
    ) -> list[str]:
        """Return IDs of agents decommissioned since ``updated_since``.

        Used during incremental sync to remove stale records from our DB.
        Uses ``decommissionedAt__gte`` so only recently decommissioned agents
        are returned, not the entire historical decommission list.
        """
        ids: list[str] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 100, "isDecommissioned": "true"}
            if cursor:
                params["cursor"] = cursor
            if updated_since:
                params["decommissionedAt__gte"] = updated_since
            data = await self._get("/agents", params=params)
            for item in data.get("data", []):
                if item.get("id"):
                    ids.append(item["id"])
            cursor = (data.get("pagination") or {}).get("nextCursor")
            if not cursor:
                break
        return ids

    async def get_installed_applications(
        self,
        page_size: int = 1000,
        resume_cursor: str | None = None,
        installed_since: str | None = None,
    ) -> AsyncIterator[tuple]:
        """Yield (total, page_cursor, item) tuples for installed applications.

        Args:
            page_size: Records per API page (default 1000, max 1000).
            resume_cursor: S1 cursor to resume a previously interrupted sweep.
            installed_since: ISO-8601 datetime. When set, only apps with
                ``installedAt >= installed_since`` are returned (refresh mode).
                Uses ``installedAt__between=[installed_since, _FAR_FUTURE]``.
        """
        cursor = resume_cursor
        while True:
            params: dict[str, Any] = {
                "limit": page_size,
                "agentIsDecommissioned": "false",
            }
            if cursor:
                params["cursor"] = cursor
            # Pass as raw_query so the comma separator is not percent-encoded
            raw_query = (
                f"installedAt__between={_s1_dt(installed_since)},{_FAR_FUTURE}"
                if installed_since
                else None
            )
            data = await self._get("/installed-applications", params=params, raw_query=raw_query)
            pagination = data.get("pagination") or {}
            page_cursor = cursor  # cursor that produced this page — resume point
            total = pagination.get("totalItems") or None
            for item in data.get("data", []):
                yield total, page_cursor, item
                total = None  # only emit on first item
            cursor = pagination.get("nextCursor")
            if not cursor:
                break
