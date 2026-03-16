"""Homebrew Cask adapter.

Fetches the Homebrew Cask catalog (GUI applications for macOS) from the
public JSON API and converts entries to library entries with glob patterns.

Casks are more relevant for endpoint fingerprinting than CLI formulae
because they represent user-facing applications (Chrome, VS Code, Slack, etc.).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger

from .base import RawEntry, SourceAdapter

HOMEBREW_CASK_API_URL = "https://formulae.brew.sh/api/cask.json"


class HomebrewCaskAdapter(SourceAdapter):
    """Ingests GUI application definitions from the Homebrew Cask catalog."""

    source_name = "homebrew_cask"
    description = "Homebrew Cask — macOS GUI applications"

    def __init__(self) -> None:
        self._current_index: int = 0

    def get_resume_state(self) -> dict[str, Any] | None:
        """Return adapter state for checkpoint serialisation."""
        return {"index": self._current_index}

    async def fetch(
        self,
        config: dict,
        *,
        resume_state: dict[str, Any] | None = None,
    ) -> AsyncIterator[RawEntry]:
        """Fetch all Homebrew Cask definitions.

        Args:
            config: Optional keys:
                - ``max_results``: Cap on entries to yield (default 50 000).
            resume_state: If resuming, contains ``index`` — the position
                in the cask list to resume from.

        Yields:
            RawEntry for each cask.
        """
        max_results = config.get("max_results", 50_000)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.get(HOMEBREW_CASK_API_URL)
                resp.raise_for_status()
                casks = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.error("Failed to fetch Homebrew Cask catalog: {}", exc)
                return

        # Resume from checkpoint: skip already-processed entries
        start_index = 0
        if resume_state:
            start_index = resume_state.get("index", 0)
            logger.info("Homebrew Cask resuming from index={}", start_index)

        self._current_index = start_index
        count = 0

        for i, cask in enumerate(casks):
            if i < start_index:
                continue
            if count >= max_results:
                break

            token = cask.get("token", "")
            if not token or len(token) < 2:
                self._current_index = i + 1
                continue

            # Cask names are human-readable (e.g. "visual-studio-code")
            names = cask.get("name", [])
            display_name = names[0] if names else token.replace("-", " ").title()
            desc = cask.get("desc", "") or ""

            # Build patterns from token, names, and homepage
            patterns = []
            # Token pattern (e.g. "visual-studio-code" → "*visual studio code*")
            clean_token = token.lower().replace("-", " ")
            if len(clean_token) >= 3:
                patterns.append(f"*{clean_token}*")

            # Each human name as a pattern
            for name in names:
                clean = name.lower().strip()
                if clean != clean_token and len(clean) >= 3:
                    patterns.append(f"*{clean}*")

            if not patterns:
                self._current_index = i + 1
                continue

            tags = ["homebrew", "cask", "macos"]
            if cask.get("deprecated"):
                tags.append("deprecated")

            homepage = cask.get("homepage", "")
            vendor = ""
            if homepage:
                # Extract domain as rough vendor (e.g. "mozilla.org" → "mozilla")
                from urllib.parse import urlparse

                try:
                    domain = urlparse(homepage).netloc.lower()
                    # Strip "www." and TLD
                    parts = domain.replace("www.", "").split(".")
                    if parts:
                        vendor = parts[0]
                except Exception:
                    pass

            yield RawEntry(
                upstream_id=f"homebrew_cask:{token}",
                name=display_name,
                vendor=vendor,
                category="desktop_application",
                description=desc,
                tags=tags,
                patterns=patterns,
                version=cask.get("version", ""),
            )
            count += 1
            self._current_index = i + 1

        logger.info("Homebrew Cask ingestion complete: {} casks fetched", count)
