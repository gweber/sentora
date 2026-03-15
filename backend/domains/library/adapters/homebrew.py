"""Homebrew formulae adapter.

Fetches the Homebrew formulae catalog from the public JSON API and
converts entries to library entries with glob patterns.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger

from .base import RawEntry, SourceAdapter

HOMEBREW_API_URL = "https://formulae.brew.sh/api/formula.json"


class HomebrewAdapter(SourceAdapter):
    """Ingests package definitions from the Homebrew formulae API."""

    source_name = "homebrew"
    description = "Homebrew — macOS/Linux package manager formulae"

    def __init__(self) -> None:
        self._current_index: int = 0

    def get_resume_state(self) -> dict[str, Any] | None:
        return {"index": self._current_index}

    async def fetch(
        self,
        config: dict,
        *,
        resume_state: dict[str, Any] | None = None,
    ) -> AsyncIterator[RawEntry]:
        """Fetch all Homebrew formulae.

        Args:
            config: Optional keys:
                - ``max_results``: Cap on entries to yield (default 5000).
            resume_state: If resuming, contains ``index`` — the position
                in the formulae list to resume from.

        Yields:
            RawEntry for each formula.
        """
        max_results = config.get("max_results", 50_000)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.get(HOMEBREW_API_URL)
                resp.raise_for_status()
                formulae = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.error("Failed to fetch Homebrew formulae: {}", exc)
                return

        # Resume from checkpoint: skip already-processed entries
        start_index = 0
        if resume_state:
            start_index = resume_state.get("index", 0)
            logger.info("Homebrew resuming from index={}", start_index)

        self._current_index = start_index
        count = 0

        for i, formula in enumerate(formulae):
            if i < start_index:
                continue
            if count >= max_results:
                break

            name = formula.get("name", "")
            if not name or len(name) < 3:
                self._current_index = i + 1
                continue

            full_name = formula.get("full_name", name)
            desc = formula.get("desc", "")

            # Build patterns from name and aliases
            patterns = [f"*{name.lower()}*"]
            aliases = formula.get("aliases", [])
            for alias in aliases:
                if alias.lower() != name.lower() and len(alias) >= 3:
                    patterns.append(f"*{alias.lower()}*")

            tags = ["homebrew", "package"]
            if formula.get("deprecated"):
                tags.append("deprecated")

            yield RawEntry(
                upstream_id=f"homebrew:{full_name}",
                name=name,
                vendor=formula.get("tap", "homebrew"),
                category="package_manager",
                description=desc,
                tags=tags,
                patterns=patterns,
                version=formula.get("versions", {}).get("stable", ""),
            )
            count += 1
            self._current_index = i + 1

        logger.info("Homebrew ingestion complete: {} formulae fetched", count)
