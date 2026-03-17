"""Canonical collection name constants.

Single source of truth for all MongoDB collection names used by the
canonical data model.  Every module that reads or writes these collections
MUST import the name from here instead of hardcoding a string literal.
"""

# ── Canonical data collections ──────────────────────────────────────────────
AGENTS = "agents"
INSTALLED_APPS = "installed_apps"
GROUPS = "groups"
SITES = "sites"
SOURCE_TAGS = "source_tags"

# ── Sync infrastructure collections ─────────────────────────────────────────
SYNC_RUNS = "sync_runs"
SYNC_META = "sync_meta"
SYNC_CHECKPOINT = "sync_checkpoint"
