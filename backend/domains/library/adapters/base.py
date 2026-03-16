"""Base adapter interface for library source ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawEntry:
    """A raw entry from an upstream source before transformation."""

    upstream_id: str
    name: str
    vendor: str = ""
    category: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    version: str = ""


class SourceAdapter(ABC):
    """Abstract base for source ingestion adapters.

    Each adapter fetches raw data from an upstream source and yields
    RawEntry objects that the ingestion manager transforms into LibraryEntry
    documents.

    Adapters support resumable ingestion via ``resume_state`` — a dict of
    adapter-specific pagination/offset state that lets ``fetch()`` skip
    already-processed entries on resume.  Adapters expose their current
    pagination state via ``get_resume_state()`` so the runner can persist
    it in checkpoints.
    """

    source_name: str
    description: str

    @abstractmethod
    def fetch(
        self,
        config: dict,
        *,
        resume_state: dict[str, Any] | None = None,
    ) -> AsyncIterator[RawEntry]:
        """Yield raw entries from the upstream source.

        Args:
            config: Source-specific configuration (e.g. feed URLs, API keys).
            resume_state: Adapter-specific state for resuming an interrupted
                ingestion (e.g. pagination offset, start index).  ``None``
                means start from the beginning.

        Yields:
            RawEntry objects for each upstream software definition.
        """
        ...  # pragma: no cover

    def get_resume_state(self) -> dict[str, Any] | None:
        """Return current adapter pagination state for checkpoint storage.

        Override in subclasses that track pagination state.  The returned
        dict will be passed back as ``resume_state`` on the next
        ``fetch()`` call if the ingestion is resumed.

        Returns:
            Adapter-specific state dict, or None if not applicable.
        """
        return None
