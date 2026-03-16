"""Integration tests for the audit hash-chain subsystem.

Tests the full chain lifecycle: initialization, appending entries,
verification, epoch management, and export.  Uses a real MongoDB
test database.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.chain.commands import append_chained_entry, initialize_chain
from audit.chain.hasher import compute_entry_hash
from audit.chain.queries import export_epoch, get_chain_status, verify_chain
from audit.chain.repository import save_epoch_size


class TestChainInitialization:
    """Tests for chain initialization (genesis entry)."""

    @pytest.mark.asyncio
    async def test_initialize_creates_genesis(self, test_db: AsyncIOMotorDatabase) -> None:
        """Initializing the chain creates a genesis entry at sequence 0."""
        entry = await initialize_chain(test_db, initialized_by="test_admin")
        assert entry["sequence"] == 0
        assert entry["epoch"] == 0
        assert entry["action"] == "system.genesis"
        assert entry["previous_hash"] is None
        assert entry["is_epoch_start"] is True
        assert isinstance(entry["hash"], str)
        assert len(entry["hash"]) == 64

    @pytest.mark.asyncio
    async def test_initialize_is_idempotent(self, test_db: AsyncIOMotorDatabase) -> None:
        """Calling initialize twice returns the same genesis entry."""
        entry1 = await initialize_chain(test_db)
        entry2 = await initialize_chain(test_db)
        assert entry1["hash"] == entry2["hash"]
        assert entry1["sequence"] == entry2["sequence"]

    @pytest.mark.asyncio
    async def test_genesis_hash_is_correct(self, test_db: AsyncIOMotorDatabase) -> None:
        """Genesis hash matches the recomputed value."""
        entry = await initialize_chain(test_db)
        recomputed = compute_entry_hash(entry, None)
        assert entry["hash"] == recomputed


class TestChainAppend:
    """Tests for appending entries to the chain."""

    @pytest.mark.asyncio
    async def test_append_increments_sequence(self, test_db: AsyncIOMotorDatabase) -> None:
        """Each appended entry gets a monotonically increasing sequence."""
        await initialize_chain(test_db)
        entries = []
        for i in range(5):
            entry = await append_chained_entry(
                test_db,
                domain="test",
                action="test.event",
                summary=f"Event {i}",
            )
            entries.append(entry)
        assert [e["sequence"] for e in entries] == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_chain_links_are_correct(self, test_db: AsyncIOMotorDatabase) -> None:
        """Each entry's previous_hash matches the preceding entry's hash."""
        genesis = await initialize_chain(test_db)
        prev_hash = genesis["hash"]
        for i in range(3):
            entry = await append_chained_entry(
                test_db,
                domain="auth",
                action="auth.login",
                summary=f"Login {i}",
            )
            assert entry["previous_hash"] == prev_hash
            prev_hash = entry["hash"]

    @pytest.mark.asyncio
    async def test_entry_hash_is_verifiable(self, test_db: AsyncIOMotorDatabase) -> None:
        """Each entry's hash matches the recomputed value."""
        await initialize_chain(test_db)
        entry = await append_chained_entry(
            test_db,
            domain="sync",
            action="sync.completed",
            summary="Sync done",
            details={"count": 42},
        )
        recomputed = compute_entry_hash(entry, entry["previous_hash"])
        assert entry["hash"] == recomputed


class TestChainVerification:
    """Tests for chain verification."""

    @pytest.mark.asyncio
    async def test_valid_chain_verifies(self, test_db: AsyncIOMotorDatabase) -> None:
        """A valid chain passes verification."""
        await initialize_chain(test_db)
        for i in range(10):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )
        result = await verify_chain(test_db)
        assert result.status.value == "valid"
        assert result.verified_entries == 11  # genesis + 10

    @pytest.mark.asyncio
    async def test_tampered_entry_detected(self, test_db: AsyncIOMotorDatabase) -> None:
        """Modifying an entry in the DB is detected by verification."""
        await initialize_chain(test_db)
        for i in range(5):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )
        # Tamper with entry at sequence 3
        await test_db["audit_log"].update_one(
            {"sequence": 3},
            {"$set": {"summary": "TAMPERED"}},
        )
        result = await verify_chain(test_db)
        assert result.status.value == "broken"
        assert result.broken_at_sequence == 3
        assert result.broken_reason is not None
        assert result.broken_reason.value == "hash_mismatch"

    @pytest.mark.asyncio
    async def test_deleted_entry_detected(self, test_db: AsyncIOMotorDatabase) -> None:
        """Deleting an entry creates a sequence gap detected by verification."""
        await initialize_chain(test_db)
        for i in range(5):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )
        # Delete entry at sequence 2
        await test_db["audit_log"].delete_one({"sequence": 2})
        result = await verify_chain(test_db)
        assert result.status.value in ("broken", "gap_detected")

    @pytest.mark.asyncio
    async def test_empty_chain_valid(self, test_db: AsyncIOMotorDatabase) -> None:
        """An initialized but empty chain (just genesis) is valid."""
        await initialize_chain(test_db)
        result = await verify_chain(test_db)
        assert result.status.value == "valid"
        assert result.verified_entries == 1


class TestChainStatus:
    """Tests for chain status queries."""

    @pytest.mark.asyncio
    async def test_status_after_initialization(self, test_db: AsyncIOMotorDatabase) -> None:
        """Chain status reflects genesis entry after initialization."""
        genesis = await initialize_chain(test_db)
        status = await get_chain_status(test_db)
        assert status.total_entries == 1
        assert status.current_epoch == 0
        assert status.current_sequence == 0
        assert status.genesis_hash == genesis["hash"]
        assert status.latest_hash == genesis["hash"]

    @pytest.mark.asyncio
    async def test_status_after_entries(self, test_db: AsyncIOMotorDatabase) -> None:
        """Chain status reflects all entries."""
        await initialize_chain(test_db)
        for i in range(5):
            last = await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )
        status = await get_chain_status(test_db)
        assert status.total_entries == 6
        assert status.current_sequence == 5
        assert status.latest_hash == last["hash"]


class TestEpochManagement:
    """Tests for epoch boundaries and management."""

    @pytest.mark.asyncio
    async def test_epoch_boundary_triggers(self, test_db: AsyncIOMotorDatabase) -> None:
        """Crossing the epoch size boundary creates a new epoch and marks epoch end."""
        # Use small epoch size for testing
        await save_epoch_size(test_db, 5)
        await initialize_chain(test_db, epoch_size=5)

        entries = []
        for i in range(9):
            entry = await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )
            entries.append(entry)

        # First epoch: sequences 0-4 (genesis + 4 entries)
        # Second epoch: sequences 5-9
        assert entries[3]["epoch"] == 0  # seq 4 → epoch 0
        assert entries[4]["epoch"] == 1  # seq 5 → epoch 1
        assert entries[4]["is_epoch_start"] is True
        assert entries[4]["previous_epoch_hash"] is not None

        # Verify epoch end was marked
        last_epoch0 = await test_db["audit_log"].find_one({"sequence": 4})
        assert last_epoch0 is not None
        assert last_epoch0.get("is_epoch_end") is True


class TestEpochExport:
    """Tests for epoch export functionality."""

    @pytest.mark.asyncio
    async def test_export_completed_epoch(self, test_db: AsyncIOMotorDatabase) -> None:
        """Completed epoch can be exported with correct metadata."""
        await save_epoch_size(test_db, 5)
        await initialize_chain(test_db, epoch_size=5)

        # Fill epoch 0 (sequences 0-4) and start epoch 1
        for i in range(5):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )

        export = await export_epoch(test_db, 0)
        assert export.metadata["epoch"] == 0
        assert export.metadata["entry_count"] == 5
        assert export.metadata["first_sequence"] == 0
        assert export.metadata["last_sequence"] == 4
        assert len(export.entries) == 5
        assert export.metadata["export_hash"]

    @pytest.mark.asyncio
    async def test_export_incomplete_epoch_fails(self, test_db: AsyncIOMotorDatabase) -> None:
        """Exporting an incomplete (current) epoch raises an error."""
        await save_epoch_size(test_db, 100)
        await initialize_chain(test_db, epoch_size=100)

        for i in range(5):
            await append_chained_entry(
                test_db, domain="test", action="test.event", summary=f"Event {i}"
            )

        from errors import EpochNotCompleteError

        with pytest.raises(EpochNotCompleteError):
            await export_epoch(test_db, 0)


class TestChainAPIEndpoints:
    """Integration tests for the audit chain REST API."""

    @pytest.mark.asyncio
    async def test_chain_status_endpoint(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        seeded_db: AsyncIOMotorDatabase,
    ) -> None:
        """GET /audit/chain/status returns chain information."""
        # Ensure chain is initialized in the test DB
        await initialize_chain(seeded_db)
        resp = await client.get("/api/v1/audit/chain/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_entries" in data
        assert "current_epoch" in data
        assert "genesis_hash" in data

    @pytest.mark.asyncio
    async def test_verify_endpoint(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        seeded_db: AsyncIOMotorDatabase,
    ) -> None:
        """POST /audit/chain/verify returns verification result."""
        await initialize_chain(seeded_db)
        resp = await client.post(
            "/api/v1/audit/chain/verify",
            json={"epoch": None},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("valid", "broken", "gap_detected")
        assert "verified_entries" in data
        assert "verification_time_ms" in data

    @pytest.mark.asyncio
    async def test_epochs_endpoint(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """GET /audit/chain/epochs returns epoch list."""
        resp = await client.get("/api/v1/audit/chain/epochs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "epochs" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_initialize_endpoint_idempotent(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """POST /audit/chain/initialize is idempotent."""
        resp1 = await client.post("/api/v1/audit/chain/initialize", headers=admin_headers)
        assert resp1.status_code == 201
        resp2 = await client.post("/api/v1/audit/chain/initialize", headers=admin_headers)
        assert resp2.status_code == 201
        assert resp1.json()["hash"] == resp2.json()["hash"]

    @pytest.mark.asyncio
    async def test_viewer_cannot_verify(
        self, client: AsyncClient, viewer_headers: dict[str, str]
    ) -> None:
        """Viewers are denied access to verification."""
        resp = await client.post(
            "/api/v1/audit/chain/verify",
            json={"epoch": None},
            headers=viewer_headers,
        )
        assert resp.status_code == 403


class TestChainConcurrencySafety:
    """Tests that the audit chain uses distributed locking (AUDIT-007)."""

    @pytest.mark.asyncio
    async def test_concurrent_appends_maintain_chain_integrity(
        self, test_db: AsyncIOMotorDatabase
    ) -> None:
        """Concurrent append_chained_entry calls should produce a valid chain.

        This verifies the distributed lock prevents the race condition where
        two callers allocate adjacent sequences but the second reads a stale
        previous_hash before the first caller's insert completes.
        """
        import asyncio

        await initialize_chain(test_db)

        # Launch several concurrent appends
        tasks = [
            append_chained_entry(
                test_db,
                domain="test",
                action="test.concurrent",
                summary=f"Concurrent event {i}",
            )
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        # All sequences should be unique
        sequences = [r["sequence"] for r in results]
        assert len(set(sequences)) == 5

        # The full chain (genesis + 5 entries) should verify cleanly
        from audit.chain.queries import verify_chain

        verification = await verify_chain(test_db)
        assert verification.status.value == "valid"
        assert verification.verified_entries == 6  # genesis + 5


class TestAuditWriterChainIntegration:
    """Tests that the existing audit() function chains entries."""

    @pytest.mark.asyncio
    async def test_audit_function_produces_chained_entries(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """The audit() function creates chained entries when chain is active."""
        await initialize_chain(test_db)

        from audit.log import audit

        await audit(
            test_db,
            domain="auth",
            action="auth.login",
            actor="user",
            summary="User logged in",
            details={"username": "test"},
        )

        # Check the entry has chain fields
        entry = await test_db["audit_log"].find_one({"action": "auth.login"})
        assert entry is not None
        assert "sequence" in entry
        assert "hash" in entry
        assert "epoch" in entry
        assert entry["sequence"] == 1  # genesis is 0

    @pytest.mark.asyncio
    async def test_audit_function_without_chain(
        self,
        test_db: AsyncIOMotorDatabase,
    ) -> None:
        """The audit() function works without chain initialization (plain mode)."""
        from audit.log import audit

        await audit(
            test_db,
            domain="sync",
            action="sync.completed",
            actor="system",
            summary="Sync done",
        )

        entry = await test_db["audit_log"].find_one({"action": "sync.completed"})
        assert entry is not None
        assert "sequence" not in entry  # plain mode — no chain fields
        assert "hash" not in entry
