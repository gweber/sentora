"""Source adapter domain — canonical data model and multi-EDR abstraction.

Adapters are registered at import time so they are available to the sync
pipeline and the source registry lookups.
"""

from __future__ import annotations

import contextlib

from .registry import register_adapter

# Register CrowdStrike adapter (only if falconpy is installed)
with contextlib.suppress(ImportError):
    from .crowdstrike.adapter import CrowdStrikeAdapter

    register_adapter("crowdstrike", CrowdStrikeAdapter)
