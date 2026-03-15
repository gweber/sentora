"""NIST CPE Dictionary adapter.

Fetches software product definitions from the NVD CPE API and converts
CPE URIs into glob patterns suitable for matching against SentinelOne
installed application names.

CPE 2.3 format:
    cpe:2.3:a:vendor:product:version:update:edition:language:sw_edition:target_sw:target_hw:other

We extract vendor + product and generate multiple glob patterns with
different specificity levels.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger

from .base import RawEntry, SourceAdapter

# NVD CPE API v2 endpoint
CPE_API_URL = "https://services.nvd.nist.gov/rest/json/cpes/2.0"

# Rate limit: NVD allows 5 requests per 30s without API key, 50 with key
RATE_LIMIT_DELAY = 6.0  # seconds between requests (no API key)
RATE_LIMIT_DELAY_WITH_KEY = 0.6


def parse_cpe_uri(cpe_uri: str) -> dict[str, str] | None:
    """Parse a CPE 2.3 URI into vendor, product, and version components.

    Args:
        cpe_uri: CPE URI string (e.g. "cpe:2.3:a:google:chrome:120.0:*:*:*:*:*:*:*")

    Returns:
        Dict with vendor, product, version keys, or None if unparseable.
    """
    parts = cpe_uri.split(":")
    if len(parts) < 6 or parts[1] != "2.3" or parts[2] != "a":
        return None

    vendor = parts[3].replace("_", " ").replace("\\", "")
    product = parts[4].replace("_", " ").replace("\\", "")
    version = parts[5] if len(parts) > 5 and parts[5] not in ("*", "-") else ""

    if not vendor or not product or vendor == "*" or product == "*":
        return None

    return {"vendor": vendor, "product": product, "version": version}


def cpe_to_patterns(cpe_uri: str) -> list[dict[str, object]]:
    """Convert a CPE URI to candidate glob patterns for app name matching.

    Returns multiple patterns at different specificity levels:
    - Broad: ``*product*`` (high recall, lower precision)
    - Vendor-qualified: ``*vendor*product*`` (balanced)

    Args:
        cpe_uri: CPE 2.3 URI string.

    Returns:
        List of dicts with ``pattern``, ``weight``, and ``source_detail`` keys.
    """
    parsed = parse_cpe_uri(cpe_uri)
    if not parsed:
        return []

    vendor = parsed["vendor"].lower()
    product = parsed["product"].lower()

    patterns: list[dict[str, object]] = []

    # Vendor-qualified pattern (preferred — more specific)
    patterns.append(
        {
            "pattern": f"*{vendor}*{product}*",
            "weight": 1.0,
            "display_name": f"{parsed['vendor'].title()} {parsed['product'].title()}",
            "source_detail": cpe_uri,
        }
    )

    # Broad product-only pattern (fallback)
    if len(product) >= 4:  # skip very short product names to avoid noise
        patterns.append(
            {
                "pattern": f"*{product}*",
                "weight": 0.8,
                "display_name": parsed["product"].title(),
                "source_detail": cpe_uri,
            }
        )

    return patterns


class NistCpeAdapter(SourceAdapter):
    """Ingests software definitions from the NVD CPE Dictionary API."""

    source_name = "nist_cpe"
    description = "NIST National Vulnerability Database — CPE Dictionary"

    def __init__(self) -> None:
        self._current_start_index: int = 0
        self._total_fetched: int = 0

    def get_resume_state(self) -> dict[str, Any] | None:
        return {
            "start_index": self._current_start_index,
            "total_fetched": self._total_fetched,
        }

    async def fetch(
        self,
        config: dict,
        *,
        resume_state: dict[str, Any] | None = None,
    ) -> AsyncIterator[RawEntry]:
        """Fetch CPE entries from the NVD API with pagination.

        Args:
            config: Optional keys:
                - ``api_key``: NVD API key for higher rate limits.
                - ``keyword``: Filter CPEs by keyword (e.g. "microsoft").
                - ``max_results``: Total max entries to fetch (default 5000).
            resume_state: If resuming, contains ``start_index`` and
                ``total_fetched`` to skip already-processed pages.

        Yields:
            RawEntry for each unique vendor:product pair.
        """
        api_key = config.get("api_key", "")

        # If no key in adapter config, try loading from persisted AppConfig
        # (covers resume-from-checkpoint where the original trigger had no key)
        if not api_key:
            try:
                from database import get_db
                from domains.config import repository as config_repo

                cfg = await config_repo.get(get_db())
                api_key = cfg.nvd_api_key or ""
            except Exception:
                pass  # proceed without key

        keyword = config.get("keyword", "")
        max_results = config.get("max_results", 20_000)
        delay = RATE_LIMIT_DELAY_WITH_KEY if api_key else RATE_LIMIT_DELAY

        if api_key:
            logger.info("NVD API key configured — using fast rate limit ({:.1f}s delay)", delay)
        else:
            logger.info("No NVD API key — using slow rate limit ({:.1f}s delay)", delay)

        headers: dict[str, str] = {}
        if api_key:
            headers["apiKey"] = api_key

        seen_products: set[str] = set()
        results_per_page = 500

        # Resume from checkpoint if available
        if resume_state:
            start_index = resume_state.get("start_index", 0)
            self._total_fetched = resume_state.get("total_fetched", 0)
            logger.info(
                "CPE resuming from start_index={}, total_fetched={}",
                start_index,
                self._total_fetched,
            )
        else:
            start_index = 0
            self._total_fetched = 0

        self._current_start_index = start_index
        total_fetched = self._total_fetched

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            while total_fetched < max_results:
                params: dict[str, str | int] = {
                    "startIndex": start_index,
                    "resultsPerPage": results_per_page,
                }
                if keyword:
                    params["keywordSearch"] = keyword

                try:
                    resp = await client.get(CPE_API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("CPE API request failed at index {}: {}", start_index, exc)
                    break

                products = data.get("products", [])
                if not products:
                    break

                for product_entry in products:
                    cpe = product_entry.get("cpe", {})
                    cpe_name = cpe.get("cpeName", "")
                    if not cpe_name:
                        continue

                    parsed = parse_cpe_uri(cpe_name)
                    if not parsed:
                        continue

                    # Deduplicate by vendor:product pair
                    dedup_key = f"{parsed['vendor'].lower()}:{parsed['product'].lower()}"
                    if dedup_key in seen_products:
                        continue
                    seen_products.add(dedup_key)

                    patterns = cpe_to_patterns(cpe_name)
                    if not patterns:
                        continue

                    titles = cpe.get("titles", [])
                    description = ""
                    for title_entry in titles:
                        if title_entry.get("lang") == "en":
                            description = title_entry.get("title", "")
                            break

                    yield RawEntry(
                        upstream_id=dedup_key,  # vendor:product (version-agnostic)
                        name=f"{parsed['vendor'].title()} {parsed['product'].title()}",
                        vendor=parsed["vendor"].title(),
                        category="cpe_software",
                        description=description or f"CPE: {cpe_name}",
                        tags=["cpe", "nist"],
                        patterns=[str(p["pattern"]) for p in patterns],
                        version="",
                    )

                    total_fetched += 1
                    self._total_fetched = total_fetched
                    if total_fetched >= max_results:
                        break

                start_index += results_per_page
                self._current_start_index = start_index
                total_results = data.get("totalResults", 0)
                if start_index >= total_results:
                    break

                await asyncio.sleep(delay)

        logger.info("CPE ingestion complete: {} unique products fetched", total_fetched)
