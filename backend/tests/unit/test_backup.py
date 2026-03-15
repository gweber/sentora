"""Unit tests for the backup manager.

Tests BackupRecord serialisation, checksum computation, list/get/delete/
verify/retention operations against a real test database. Backup creation
and restore (which shell out to mongodump/mongorestore) are tested with
mocked subprocesses.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.backup import BackupManager, BackupRecord, _compute_sha256, _dir_size

# Process mock that simulates a successful mongodump/mongorestore
_MOCK_PROC_SUCCESS = AsyncMock()
_MOCK_PROC_SUCCESS.communicate = AsyncMock(return_value=(b"ok", b""))
_MOCK_PROC_SUCCESS.returncode = 0

_MOCK_PROC_FAIL = AsyncMock()
_MOCK_PROC_FAIL.communicate = AsyncMock(return_value=(b"", b"mongodump: error"))
_MOCK_PROC_FAIL.returncode = 1


# ── BackupRecord serialisation ──────────────────────────────────────────────


def test_backup_record_to_dict() -> None:
    """to_dict() maps 'id' to '_id' for MongoDB insertion."""
    record = BackupRecord(id="backup_001", timestamp="2026-01-01T00:00:00")
    d = record.to_dict()
    assert d["_id"] == "backup_001"
    assert "id" not in d
    assert d["status"] == "in_progress"


def test_backup_record_from_doc() -> None:
    """from_doc() maps '_id' back to 'id' and ignores unknown fields."""
    doc = {
        "_id": "backup_002",
        "timestamp": "2026-01-01T00:00:00",
        "status": "completed",
        "size_bytes": 1024,
        "unknown_field": "should be ignored",
    }
    record = BackupRecord.from_doc(doc)
    assert record.id == "backup_002"
    assert record.status == "completed"
    assert record.size_bytes == 1024


def test_backup_record_roundtrip() -> None:
    """to_dict → from_doc roundtrip preserves all fields."""
    original = BackupRecord(
        id="rt_001",
        timestamp="2026-03-15T10:00:00",
        size_bytes=512,
        checksum_sha256="abc123",
        storage_path="/backups/rt_001",
        status="completed",
        triggered_by="scheduler",
        duration_seconds=5.5,
    )
    restored = BackupRecord.from_doc(original.to_dict())
    assert restored.id == original.id
    assert restored.size_bytes == original.size_bytes
    assert restored.checksum_sha256 == original.checksum_sha256
    assert restored.triggered_by == original.triggered_by


# ── Checksum / size helpers ─────────────────────────────────────────────────


def test_compute_sha256_file(tmp_path: Path) -> None:
    """SHA-256 of a single file matches hashlib directly."""
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert _compute_sha256(f) == expected


def test_compute_sha256_directory(tmp_path: Path) -> None:
    """SHA-256 of a directory hashes all files deterministically."""
    (tmp_path / "a.txt").write_bytes(b"aaa")
    (tmp_path / "b.txt").write_bytes(b"bbb")
    result = _compute_sha256(tmp_path)
    # Should be consistent across runs
    assert len(result) == 64  # hex digest length
    assert _compute_sha256(tmp_path) == result  # idempotent


def test_dir_size(tmp_path: Path) -> None:
    """_dir_size sums the byte count of all files in the tree."""
    (tmp_path / "file1.txt").write_bytes(b"abc")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "file2.txt").write_bytes(b"defgh")
    assert _dir_size(tmp_path) == 8  # 3 + 5


# ── Database operations ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_backups_empty(test_db: AsyncIOMotorDatabase) -> None:
    """List backups returns empty list and zero total on fresh database."""
    records, total = await BackupManager.list_backups(test_db)
    assert records == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_backups_with_data(test_db: AsyncIOMotorDatabase) -> None:
    """List backups returns records sorted by timestamp descending."""
    await test_db["backup_history"].insert_many(
        [
            BackupRecord(id="b1", timestamp="2026-01-01T00:00:00", status="completed").to_dict(),
            BackupRecord(id="b2", timestamp="2026-01-02T00:00:00", status="completed").to_dict(),
        ]
    )
    records, total = await BackupManager.list_backups(test_db)
    assert total == 2
    assert records[0].id == "b2"  # most recent first
    assert records[1].id == "b1"


@pytest.mark.asyncio
async def test_get_backup_found(test_db: AsyncIOMotorDatabase) -> None:
    """get_backup returns the record when it exists."""
    await test_db["backup_history"].insert_one(
        BackupRecord(id="b_get", timestamp="2026-01-01T00:00:00", status="completed").to_dict()
    )
    record = await BackupManager.get_backup(test_db, "b_get")
    assert record is not None
    assert record.id == "b_get"


@pytest.mark.asyncio
async def test_get_backup_not_found(test_db: AsyncIOMotorDatabase) -> None:
    """get_backup returns None for nonexistent backup."""
    record = await BackupManager.get_backup(test_db, "nonexistent")
    assert record is None


@pytest.mark.asyncio
async def test_delete_backup_found(
    test_db: AsyncIOMotorDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """delete_backup removes both the DB record and files on disk."""
    backup_dir = tmp_path / "b_del"
    backup_dir.mkdir()
    (backup_dir / "data.bson").write_bytes(b"data")

    # Point backup_local_path at the tmp directory so path-traversal guard passes
    from config import get_settings

    monkeypatch.setattr(get_settings(), "backup_local_path", str(tmp_path))

    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_del",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(backup_dir),
            status="completed",
        ).to_dict()
    )
    deleted = await BackupManager.delete_backup(test_db, "b_del")
    assert deleted is True
    assert not backup_dir.exists()
    assert await test_db["backup_history"].count_documents({}) == 0


@pytest.mark.asyncio
async def test_delete_backup_not_found(test_db: AsyncIOMotorDatabase) -> None:
    """delete_backup returns False for nonexistent backup."""
    deleted = await BackupManager.delete_backup(test_db, "nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_verify_backup_valid(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """verify_backup returns True when checksum matches."""
    backup_dir = tmp_path / "b_verify"
    backup_dir.mkdir()
    (backup_dir / "data.bson").write_bytes(b"hello")
    checksum = _compute_sha256(backup_dir)

    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_verify",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(backup_dir),
            checksum_sha256=checksum,
            status="completed",
        ).to_dict()
    )
    valid = await BackupManager.verify_backup(test_db, "b_verify")
    assert valid is True


@pytest.mark.asyncio
async def test_verify_backup_tampered(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """verify_backup returns False when file content changed after backup."""
    backup_dir = tmp_path / "b_tamper"
    backup_dir.mkdir()
    (backup_dir / "data.bson").write_bytes(b"original")
    old_checksum = _compute_sha256(backup_dir)

    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_tamper",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(backup_dir),
            checksum_sha256=old_checksum,
            status="completed",
        ).to_dict()
    )

    # Tamper with the file
    (backup_dir / "data.bson").write_bytes(b"tampered")

    valid = await BackupManager.verify_backup(test_db, "b_tamper")
    assert valid is False


@pytest.mark.asyncio
async def test_verify_backup_not_found(test_db: AsyncIOMotorDatabase) -> None:
    """verify_backup raises ValueError for nonexistent backup."""
    with pytest.raises(ValueError, match="not found"):
        await BackupManager.verify_backup(test_db, "nonexistent")


@pytest.mark.asyncio
async def test_verify_backup_no_checksum(test_db: AsyncIOMotorDatabase) -> None:
    """verify_backup raises ValueError when backup has no stored checksum."""
    await test_db["backup_history"].insert_one(
        BackupRecord(id="b_nochk", timestamp="2026-01-01T00:00:00", status="completed").to_dict()
    )
    with pytest.raises(ValueError, match="no stored checksum"):
        await BackupManager.verify_backup(test_db, "b_nochk")


# ── Retention enforcement ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enforce_retention_deletes_oldest(
    test_db: AsyncIOMotorDatabase, tmp_path: Path
) -> None:
    """enforce_retention deletes oldest backups exceeding the retention count."""
    # Create 3 backups, retention=2 (default is 7, override via settings)
    for i in range(3):
        d = tmp_path / f"b_ret_{i}"
        d.mkdir()
        (d / "data.bson").write_bytes(f"data{i}".encode())
        await test_db["backup_history"].insert_one(
            BackupRecord(
                id=f"b_ret_{i}",
                timestamp=f"2026-01-0{i + 1}T00:00:00",
                storage_path=str(d),
                status="completed",
            ).to_dict()
        )

    with patch("utils.backup.get_settings") as mock_settings:
        mock_settings.return_value.backup_retention_count = 2
        mock_settings.return_value.backup_local_path = str(tmp_path)
        deleted = await BackupManager.enforce_retention(test_db)

    assert deleted == 1  # oldest (b_ret_0) should be deleted
    assert await test_db["backup_history"].count_documents({}) == 2
    remaining = await BackupManager.get_backup(test_db, "b_ret_0")
    assert remaining is None  # oldest was removed


@pytest.mark.asyncio
async def test_enforce_retention_no_excess(test_db: AsyncIOMotorDatabase) -> None:
    """enforce_retention returns 0 when within retention limit."""
    await test_db["backup_history"].insert_one(
        BackupRecord(id="b_only", timestamp="2026-01-01T00:00:00", status="completed").to_dict()
    )
    deleted = await BackupManager.enforce_retention(test_db)
    assert deleted == 0


# ── create_backup with mocked subprocess ────────────────────────────────────


@pytest.mark.asyncio
async def test_create_backup_success(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """create_backup runs mongodump and records a completed backup."""
    with (
        patch("utils.backup.get_settings") as mock_settings,
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_SUCCESS),
    ):
        mock_settings.return_value.backup_local_path = str(tmp_path)
        mock_settings.return_value.mongo_uri = "mongodb://localhost:27017"
        mock_settings.return_value.mongo_db = "sentora_test"

        record = await BackupManager.create_backup(test_db, triggered_by="test")

    assert record.status == "completed"
    assert record.triggered_by == "test"
    assert record.duration_seconds >= 0
    # Record persisted in DB
    doc = await test_db["backup_history"].find_one({"_id": record.id})
    assert doc is not None
    assert doc["status"] == "completed"


@pytest.mark.asyncio
async def test_create_backup_failure(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """create_backup records a failed backup when mongodump returns non-zero."""
    with (
        patch("utils.backup.get_settings") as mock_settings,
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_FAIL),
    ):
        mock_settings.return_value.backup_local_path = str(tmp_path)
        mock_settings.return_value.mongo_uri = "mongodb://localhost:27017"
        mock_settings.return_value.mongo_db = "sentora_test"

        record = await BackupManager.create_backup(test_db, triggered_by="test")

    assert record.status == "failed"
    assert record.error is not None
    assert "mongodump" in record.error


# ── restore_from_backup with mocked subprocess ─────────────────────────────


@pytest.mark.asyncio
async def test_restore_backup_success(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """restore_from_backup runs mongorestore on an existing backup."""
    backup_dir = tmp_path / "b_restore"
    backup_dir.mkdir()
    (backup_dir / "sentora_test").mkdir()
    checksum = _compute_sha256(backup_dir)

    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_restore",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(backup_dir),
            checksum_sha256=checksum,
            status="completed",
        ).to_dict()
    )

    with (
        patch("utils.backup.get_settings") as mock_settings,
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_SUCCESS),
    ):
        mock_settings.return_value.mongo_uri = "mongodb://localhost:27017"
        mock_settings.return_value.mongo_db = "sentora_test"
        mock_settings.return_value.backup_local_path = str(tmp_path)
        # Should not raise
        await BackupManager.restore_from_backup(test_db, "b_restore")


@pytest.mark.asyncio
async def test_restore_backup_not_found(test_db: AsyncIOMotorDatabase) -> None:
    """restore_from_backup raises ValueError for nonexistent backup."""
    with pytest.raises(ValueError, match="not found"):
        await BackupManager.restore_from_backup(test_db, "nonexistent")


@pytest.mark.asyncio
async def test_restore_backup_checksum_mismatch(
    test_db: AsyncIOMotorDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restore_from_backup raises ValueError when checksum doesn't match."""
    backup_dir = tmp_path / "b_mismatch"
    backup_dir.mkdir()
    (backup_dir / "data.bson").write_bytes(b"original")

    from config import get_settings

    monkeypatch.setattr(get_settings(), "backup_local_path", str(tmp_path))

    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_mismatch",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(backup_dir),
            checksum_sha256="wrong_checksum_value",
            status="completed",
        ).to_dict()
    )

    with pytest.raises(ValueError, match="Checksum mismatch"):
        await BackupManager.restore_from_backup(test_db, "b_mismatch")


@pytest.mark.asyncio
async def test_restore_backup_dir_missing(
    test_db: AsyncIOMotorDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """restore_from_backup raises ValueError when backup directory is missing."""
    from config import get_settings

    monkeypatch.setattr(get_settings(), "backup_local_path", str(tmp_path))

    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_missing_dir",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(tmp_path / "does_not_exist"),
            status="completed",
        ).to_dict()
    )

    with pytest.raises(ValueError, match="does not exist"):
        await BackupManager.restore_from_backup(test_db, "b_missing_dir")


@pytest.mark.asyncio
async def test_verify_backup_dir_missing(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """verify_backup returns False when backup directory no longer exists."""
    await test_db["backup_history"].insert_one(
        BackupRecord(
            id="b_gone",
            timestamp="2026-01-01T00:00:00",
            storage_path=str(tmp_path / "deleted_dir"),
            checksum_sha256="abc123",
            status="completed",
        ).to_dict()
    )
    valid = await BackupManager.verify_backup(test_db, "b_gone")
    assert valid is False
