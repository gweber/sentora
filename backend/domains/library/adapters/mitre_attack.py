"""MITRE ATT&CK Software adapter.

Fetches the ATT&CK Enterprise software list from the MITRE CTI GitHub
repository (STIX 2.1 format) and converts software entries to library
entries with glob patterns derived from software names and aliases.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger

from .base import RawEntry, SourceAdapter

# MITRE ATT&CK STIX bundle URL (enterprise software)
ATTACK_SOFTWARE_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)


class MitreAttackAdapter(SourceAdapter):
    """Ingests software definitions from the MITRE ATT&CK framework."""

    source_name = "mitre"
    description = "MITRE ATT&CK Enterprise — Software (malware & tools)"

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
        """Fetch ATT&CK software objects from the STIX bundle.

        Args:
            config: Optional keys:
                - ``url``: Override STIX bundle URL.
                - ``include_malware``: Include malware entries (default True).
                - ``include_tools``: Include tool entries (default True).
            resume_state: If resuming, contains ``index`` — the position
                in the STIX objects list to resume from.

        Yields:
            RawEntry for each ATT&CK software object.
        """
        url = config.get("url", ATTACK_SOFTWARE_URL)
        include_malware = config.get("include_malware", True)
        include_tools = config.get("include_tools", True)

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                bundle = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.error("Failed to fetch ATT&CK STIX bundle: {}", exc)
                return

        objects = bundle.get("objects", [])
        software_types = set()
        if include_malware:
            software_types.add("malware")
        if include_tools:
            software_types.add("tool")

        # Resume from checkpoint: skip already-processed objects
        start_index = 0
        if resume_state:
            start_index = resume_state.get("index", 0)
            logger.info("MITRE ATT&CK resuming from index={}", start_index)

        self._current_index = start_index
        count = 0

        for i, obj in enumerate(objects):
            if i < start_index:
                continue

            obj_type = obj.get("type", "")
            if obj_type not in software_types:
                self._current_index = i + 1
                continue

            # Skip revoked or deprecated entries
            if obj.get("revoked") or obj.get("x_mitre_deprecated"):
                self._current_index = i + 1
                continue

            name = obj.get("name", "")
            if not name:
                self._current_index = i + 1
                continue

            # External references — find the ATT&CK ID (e.g. S0001)
            attack_id = ""
            for ref in obj.get("external_references", []):
                if ref.get("source_name") == "mitre-attack":
                    attack_id = ref.get("external_id", "")
                    break

            upstream_id = attack_id or obj.get("id", "")

            # Build patterns from name and aliases
            aliases = obj.get("x_mitre_aliases", [])
            all_names = [name] + [a for a in aliases if a.lower() != name.lower()]

            patterns = []
            for n in all_names:
                clean = n.lower().strip()
                if len(clean) >= 3:
                    patterns.append(f"*{clean}*")

            description = obj.get("description", "")
            # Truncate long descriptions
            if len(description) > 500:
                description = description[:497] + "..."

            tags = ["mitre", "attack", obj_type]
            platforms = obj.get("x_mitre_platforms", [])
            for p in platforms:
                tags.append(p.lower().replace(" ", "_"))

            yield RawEntry(
                upstream_id=upstream_id,
                name=name,
                vendor="",
                category=f"attack_{obj_type}",
                description=description,
                tags=tags,
                patterns=patterns,
                version=obj.get("modified", ""),
            )
            count += 1
            self._current_index = i + 1

        logger.info("ATT&CK ingestion complete: {} software entries fetched", count)
