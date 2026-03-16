"""Chocolatey package adapter.

Fetches popular Windows package definitions from the Chocolatey Community
Repository OData v2 API and converts them to library entries.

The Chocolatey API only returns Atom XML (no JSON support). Query parameters
must be percent-encoded with ``%20`` for spaces — httpx's default ``+``
encoding is rejected by the OData v2 parser.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import defusedxml.ElementTree as ET
import httpx
from loguru import logger

from .base import RawEntry, SourceAdapter

# Chocolatey Community API — OData v2 endpoint for packages
CHOCO_BASE = "https://community.chocolatey.org/api/v2/Packages()"

# Atom / OData XML namespaces
_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
}


def _build_url(min_downloads: int, page_size: int, skip: int) -> str:
    """Build the OData query URL with proper percent-encoding.

    httpx encodes spaces as ``+`` which the Chocolatey OData parser rejects.
    We construct the URL ourselves using ``%20`` instead.
    """
    filt = quote(f"IsLatestVersion eq true and DownloadCount gt {min_downloads}", safe="")
    order = quote("DownloadCount desc", safe="")
    return f"{CHOCO_BASE}?$filter={filt}&$orderby={order}&$top={page_size}&$skip={skip}"


def _parse_entries(xml_text: str) -> list[dict[str, str]]:
    """Parse Atom XML response into a list of package property dicts."""
    root = ET.fromstring(xml_text)  # nosec B314 — input is from Chocolatey public API, not user-supplied
    results: list[dict[str, str]] = []
    for entry in root.findall("a:entry", _NS):
        # Package ID is in the Atom <title> element
        pkg_id = entry.findtext("a:title", "", _NS).strip()
        props = entry.find("m:properties", _NS)
        if props is None:
            continue
        results.append(
            {
                "Id": pkg_id,
                "Title": props.findtext("d:Title", "", _NS).strip() or pkg_id,
                "Authors": props.findtext("d:Authors", "", _NS).strip(),
                "Summary": props.findtext("d:Summary", "", _NS).strip(),
                "Description": props.findtext("d:Description", "", _NS).strip(),
                "Tags": props.findtext("d:Tags", "", _NS).strip(),
                "DownloadCount": props.findtext("d:DownloadCount", "0", _NS).strip(),
            }
        )
    return results


class ChocolateyAdapter(SourceAdapter):
    """Ingests package definitions from the Chocolatey Community Repository."""

    source_name = "chocolatey"
    description = "Chocolatey Community Repository — Windows packages"

    def __init__(self) -> None:
        self._current_skip: int = 0
        self._count: int = 0

    def get_resume_state(self) -> dict[str, Any] | None:
        """Return adapter state for checkpoint serialisation."""
        return {
            "skip": self._current_skip,
            "count": self._count,
        }

    async def fetch(
        self,
        config: dict,
        *,
        resume_state: dict[str, Any] | None = None,
    ) -> AsyncIterator[RawEntry]:
        """Fetch popular Chocolatey packages.

        Args:
            config: Optional keys:
                - ``min_downloads``: Minimum total downloads (default 10 000).
                - ``max_results``: Total max entries to fetch (default 10 000).
            resume_state: If resuming, contains ``skip`` and ``count``
                to continue from where we left off.

        Yields:
            RawEntry for each package.
        """
        min_downloads = config.get("min_downloads", 1_000)
        max_results = config.get("max_results", 10_000)

        seen: set[str] = set()
        page_size = 100

        # Resume from checkpoint if available
        if resume_state:
            skip = resume_state.get("skip", 0)
            count = resume_state.get("count", 0)
            logger.info("Chocolatey resuming from skip={}, count={}", skip, count)
        else:
            skip = 0
            count = 0

        self._current_skip = skip
        self._count = count

        async with httpx.AsyncClient(timeout=30.0) as client:
            while count < max_results:
                url = _build_url(min_downloads, page_size, skip)

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    entries = _parse_entries(resp.text)
                except (httpx.HTTPError, ET.ParseError) as exc:
                    logger.warning("Chocolatey API request failed at skip {}: {}", skip, exc)
                    break

                if not entries:
                    break

                for pkg in entries:
                    if count >= max_results:
                        break

                    pkg_id = pkg["Id"]
                    if not pkg_id or pkg_id.lower() in seen:
                        continue
                    seen.add(pkg_id.lower())

                    title = pkg["Title"] or pkg_id
                    authors = pkg["Authors"]
                    description = pkg["Summary"] or pkg["Description"]
                    if len(description) > 500:
                        description = description[:497] + "..."

                    # Build patterns from package ID and title
                    patterns = []
                    clean_id = pkg_id.lower().replace(".", " ").replace("-", " ")
                    if len(clean_id) >= 3:
                        patterns.append(f"*{clean_id}*")
                    clean_title = title.lower()
                    if clean_title != clean_id and len(clean_title) >= 3:
                        patterns.append(f"*{clean_title}*")

                    if not patterns:
                        continue

                    tags_str = pkg["Tags"]
                    tags = ["chocolatey", "windows"]
                    for t in tags_str.split():
                        if t and len(t) >= 2 and t not in tags:
                            tags.append(t.lower())
                            if len(tags) >= 10:
                                break

                    yield RawEntry(
                        upstream_id=f"chocolatey:{pkg_id}",
                        name=title,
                        vendor=authors.split(",")[0].strip() if authors else "",
                        category="package_manager",
                        description=description,
                        tags=tags,
                        patterns=patterns,
                        version="",
                    )
                    count += 1
                    self._count = count

                skip += page_size
                self._current_skip = skip
                await asyncio.sleep(1.0)  # respect rate limits

        logger.info("Chocolatey ingestion complete: {} packages fetched", count)
