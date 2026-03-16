"""Unit tests for the CLI verifier module.

Tests the verification logic used by the air-gapped CLI tool.
Ensures hash-chain integrity checks and cross-epoch validation work
correctly with stdlib-only dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add tools/ to path so we can import the standalone verifier
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools"))

from sentora_verify.hasher import compute_entry_hash  # noqa: E402
from sentora_verify.verifier import verify_cross_epoch, verify_epoch  # noqa: E402


def _make_entry(seq: int, epoch: int, prev_hash: str | None) -> dict:
    """Create a minimal valid entry for testing."""
    entry = {
        "sequence": seq,
        "epoch": epoch,
        "timestamp": "2026-03-15T12:00:00+00:00",
        "domain": "test",
        "action": "test.event",
        "actor": "system",
        "status": "success",
        "summary": f"Test entry {seq}",
        "details": {},
        "tenant_id": None,
        "previous_hash": prev_hash,
    }
    entry["hash"] = compute_entry_hash(entry, prev_hash)
    return entry


def _make_chain(count: int, start_seq: int = 0, epoch: int = 0) -> list[dict]:
    """Build a valid chain of entries."""
    entries = []
    prev_hash: str | None = None
    for i in range(count):
        entry = _make_entry(start_seq + i, epoch, prev_hash)
        prev_hash = entry["hash"]
        entries.append(entry)
    return entries


class TestVerifyEpoch:
    """Tests for ``verify_epoch``."""

    def test_valid_chain(self) -> None:
        """Valid chain passes verification."""
        entries = _make_chain(10)
        data = {"export_metadata": {"epoch": 0}, "entries": entries}
        result = verify_epoch(data)
        assert result.valid
        assert result.entries_checked == 10

    def test_empty_entries(self) -> None:
        """Empty entries list fails verification."""
        data: dict[str, Any] = {"export_metadata": {}, "entries": []}
        result = verify_epoch(data)
        assert not result.valid
        assert "No entries" in result.message

    def test_sequence_gap_detected(self) -> None:
        """Missing sequence is detected."""
        entries = _make_chain(5)
        # Remove entry at sequence 2 to create a gap
        entries.pop(2)
        data = {"export_metadata": {"epoch": 0}, "entries": entries}
        result = verify_epoch(data)
        assert not result.valid
        assert result.broken_reason == "sequence_gap"

    def test_tampered_entry_detected(self) -> None:
        """Modifying an entry's data is detected via hash mismatch."""
        entries = _make_chain(5)
        # Tamper with entry 3's summary
        entries[3]["summary"] = "TAMPERED"
        data = {"export_metadata": {"epoch": 0}, "entries": entries}
        result = verify_epoch(data)
        assert not result.valid
        assert result.broken_reason == "hash_mismatch"

    def test_broken_chain_link_detected(self) -> None:
        """Breaking the chain link (wrong previous_hash) is detected."""
        entries = _make_chain(5)
        # Break the link at entry 2 by changing its previous_hash
        entries[2]["previous_hash"] = "wrong_hash"
        entries[2]["hash"] = compute_entry_hash(entries[2], "wrong_hash")
        data = {"export_metadata": {"epoch": 0}, "entries": entries}
        result = verify_epoch(data)
        assert not result.valid
        assert result.broken_reason == "hash_mismatch"

    def test_export_hash_verified(self) -> None:
        """Export hash is verified when present in metadata."""
        from sentora_verify.hasher import compute_export_hash

        entries = _make_chain(3)
        export_hash = compute_export_hash(entries)
        data = {
            "export_metadata": {"epoch": 0, "export_hash": export_hash},
            "entries": entries,
        }
        result = verify_epoch(data)
        assert result.valid

    def test_tampered_export_hash_detected(self) -> None:
        """Wrong export hash is detected."""
        entries = _make_chain(3)
        data = {
            "export_metadata": {"epoch": 0, "export_hash": "wrong_hash"},
            "entries": entries,
        }
        result = verify_epoch(data)
        assert not result.valid
        assert result.broken_reason == "export_hash_mismatch"


class TestVerifyCrossEpoch:
    """Tests for ``verify_cross_epoch``."""

    def test_valid_cross_epoch_link(self) -> None:
        """Valid cross-epoch chain link passes."""
        epoch0 = _make_chain(5, start_seq=0, epoch=0)
        epoch1_entries = _make_chain(5, start_seq=5, epoch=1)
        # Set previous_hash of first entry in epoch 1 to last hash of epoch 0
        epoch1_entries[0]["previous_hash"] = epoch0[-1]["hash"]
        epoch1_entries[0]["previous_epoch_hash"] = epoch0[-1]["hash"]
        epoch1_entries[0]["hash"] = compute_entry_hash(epoch1_entries[0], epoch0[-1]["hash"])

        current = {"export_metadata": {"epoch": 1}, "entries": epoch1_entries}
        previous = {"export_metadata": {"epoch": 0}, "entries": epoch0}

        result = verify_cross_epoch(current, previous)
        assert result.valid

    def test_broken_cross_epoch_link(self) -> None:
        """Broken cross-epoch link is detected."""
        epoch0 = _make_chain(5, start_seq=0, epoch=0)
        epoch1_entries = _make_chain(5, start_seq=5, epoch=1)
        epoch1_entries[0]["previous_epoch_hash"] = "wrong_hash"

        current = {"export_metadata": {"epoch": 1}, "entries": epoch1_entries}
        previous = {"export_metadata": {"epoch": 0}, "entries": epoch0}

        result = verify_cross_epoch(current, previous)
        assert not result.valid


class TestHasherIdentity:
    """Verify that CLI hasher produces identical results to backend hasher."""

    def test_backend_and_cli_hashers_identical(self) -> None:
        """Backend and CLI hasher produce the same hash for the same input."""
        from sentora_verify.hasher import compute_entry_hash as cli_hash

        from audit.chain.hasher import compute_entry_hash as backend_hash

        entry = {
            "sequence": 42,
            "epoch": 0,
            "timestamp": "2026-03-15T12:00:00+00:00",
            "domain": "auth",
            "action": "auth.login",
            "actor": "user",
            "status": "success",
            "summary": "User logged in",
            "details": {"ip": "10.0.0.1"},
            "tenant_id": "test_tenant",
        }

        backend_result = backend_hash(entry, "prev_hash")
        cli_result = cli_hash(entry, "prev_hash")
        assert backend_result == cli_result

    def test_genesis_hash_identical(self) -> None:
        """Genesis hash (previous_hash=None) matches between backend and CLI."""
        from sentora_verify.hasher import compute_entry_hash as cli_hash

        from audit.chain.hasher import compute_entry_hash as backend_hash

        entry = {
            "sequence": 0,
            "epoch": 0,
            "timestamp": "2026-03-15T12:00:00+00:00",
            "domain": "system",
            "action": "system.genesis",
            "actor": "admin",
            "status": "info",
            "summary": "Chain initialized",
            "details": {"version": "1.0"},
            "tenant_id": None,
        }

        assert backend_hash(entry, None) == cli_hash(entry, None)
