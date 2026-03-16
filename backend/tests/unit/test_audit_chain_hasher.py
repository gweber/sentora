"""Unit tests for audit hash-chain hasher module.

Verifies deterministic hash computation, genesis sentinel handling,
and export hash integrity.
"""

from __future__ import annotations

from datetime import UTC, datetime

from audit.chain.hasher import (
    compute_entry_hash,
    compute_export_hash,
)


class TestComputeEntryHash:
    """Tests for ``compute_entry_hash``."""

    def test_deterministic_same_input_same_hash(self) -> None:
        """Same input always produces the same hash."""
        entry = {
            "sequence": 1,
            "epoch": 0,
            "timestamp": "2026-03-15T12:00:00+00:00",
            "domain": "auth",
            "action": "auth.login",
            "actor": "user",
            "status": "success",
            "summary": "User logged in",
            "details": {"ip": "10.0.0.1"},
            "tenant_id": None,
        }
        h1 = compute_entry_hash(entry, "abc123")
        h2 = compute_entry_hash(entry, "abc123")
        assert h1 == h2

    def test_different_previous_hash_different_result(self) -> None:
        """Changing the previous hash changes the output hash."""
        entry = {
            "sequence": 1,
            "epoch": 0,
            "timestamp": "2026-03-15T12:00:00+00:00",
            "domain": "sync",
            "action": "sync.completed",
            "actor": "system",
            "status": "success",
            "summary": "Sync completed",
            "details": {},
            "tenant_id": None,
        }
        h1 = compute_entry_hash(entry, "hash_a")
        h2 = compute_entry_hash(entry, "hash_b")
        assert h1 != h2

    def test_genesis_uses_sentinel(self) -> None:
        """Genesis entry (previous_hash=None) uses GENESIS sentinel."""
        entry = {
            "sequence": 0,
            "epoch": 0,
            "timestamp": "2026-03-15T12:00:00+00:00",
            "domain": "system",
            "action": "system.genesis",
            "actor": "admin",
            "status": "info",
            "summary": "Chain initialized",
            "details": {},
            "tenant_id": None,
        }
        h = compute_entry_hash(entry, None)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest length

    def test_datetime_object_handled(self) -> None:
        """datetime objects are serialised via isoformat."""
        dt = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
        entry = {
            "sequence": 5,
            "epoch": 0,
            "timestamp": dt,
            "domain": "config",
            "action": "config.updated",
            "actor": "user",
            "status": "success",
            "summary": "Settings changed",
            "details": None,
            "tenant_id": "tenant_1",
        }
        h = compute_entry_hash(entry, "prev")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_hash_is_hex_lowercase(self) -> None:
        """Hash is lowercase hex."""
        entry = {
            "sequence": 0,
            "epoch": 0,
            "timestamp": "2026-01-01T00:00:00Z",
            "domain": "system",
            "action": "system.genesis",
            "actor": "system",
            "status": "info",
            "summary": "Init",
            "details": {},
            "tenant_id": None,
        }
        h = compute_entry_hash(entry, None)
        assert h == h.lower()
        assert all(c in "0123456789abcdef" for c in h)

    def test_changing_any_field_changes_hash(self) -> None:
        """Modifying any content field must change the hash."""
        base = {
            "sequence": 3,
            "epoch": 0,
            "timestamp": "2026-03-15T12:00:00Z",
            "domain": "auth",
            "action": "auth.login",
            "actor": "user",
            "status": "success",
            "summary": "Login",
            "details": {"key": "val"},
            "tenant_id": None,
        }
        base_hash = compute_entry_hash(base, "prev")

        for field, alt_value in [
            ("sequence", 99),
            ("epoch", 1),
            ("timestamp", "2026-03-16T12:00:00Z"),
            ("domain", "sync"),
            ("action", "auth.logout"),
            ("actor", "system"),
            ("status", "failure"),
            ("summary", "Different"),
            ("details", {"key": "other"}),
            ("tenant_id", "other_tenant"),
        ]:
            modified = dict(base)
            modified[field] = alt_value
            assert compute_entry_hash(modified, "prev") != base_hash, (
                f"Changing '{field}' should change the hash"
            )


class TestComputeExportHash:
    """Tests for ``compute_export_hash``."""

    def test_deterministic(self) -> None:
        """Same entries always produce the same export hash."""
        entries = [
            {"sequence": 0, "hash": "a", "data": "test"},
            {"sequence": 1, "hash": "b", "data": "test2"},
        ]
        h1 = compute_export_hash(entries)
        h2 = compute_export_hash(entries)
        assert h1 == h2

    def test_order_matters(self) -> None:
        """Reordering entries changes the export hash."""
        e1 = {"sequence": 0, "data": "first"}
        e2 = {"sequence": 1, "data": "second"}
        h1 = compute_export_hash([e1, e2])
        h2 = compute_export_hash([e2, e1])
        assert h1 != h2

    def test_modification_changes_hash(self) -> None:
        """Modifying any entry changes the export hash."""
        entries = [{"sequence": 0, "data": "original"}]
        h1 = compute_export_hash(entries)
        modified = [{"sequence": 0, "data": "modified"}]
        h2 = compute_export_hash(modified)
        assert h1 != h2

    def test_empty_list(self) -> None:
        """Empty list produces a valid hash (SHA-256 of nothing)."""
        h = compute_export_hash([])
        assert isinstance(h, str)
        assert len(h) == 64
