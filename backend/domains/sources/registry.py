"""Source adapter registry.

Pattern matches the compliance framework registry — register adapters
by name, look them up at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import SourceAdapter

_ADAPTERS: dict[str, type[SourceAdapter]] = {}


def register_adapter(source_name: str, adapter_class: type[SourceAdapter]) -> None:
    """Register a source adapter class.

    Args:
        source_name: Unique source identifier (e.g. ``"sentinelone"``).
        adapter_class: SourceAdapter subclass to register.

    Raises:
        ValueError: If an adapter with this name is already registered.
    """
    if source_name in _ADAPTERS:
        msg = f"Source adapter already registered: {source_name}"
        raise ValueError(msg)
    _ADAPTERS[source_name] = adapter_class


def get_adapter(source_name: str) -> type[SourceAdapter]:
    """Look up a registered source adapter by name.

    Args:
        source_name: Source identifier.

    Returns:
        The registered SourceAdapter subclass.

    Raises:
        KeyError: If no adapter is registered for this source.
    """
    if source_name not in _ADAPTERS:
        msg = f"Unknown source adapter: {source_name}. Registered: {sorted(_ADAPTERS)}"
        raise KeyError(msg)
    return _ADAPTERS[source_name]


def list_adapters() -> list[str]:
    """Return names of all registered source adapters.

    Returns:
        Sorted list of registered source names.
    """
    return sorted(_ADAPTERS)
