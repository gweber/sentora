"""Unit tests for backup S3 storage paths and edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.backup import BackupManager, BackupRecord, _compute_sha256

_MOCK_PROC_SUCCESS = AsyncMock()
_MOCK_PROC_SUCCESS.communicate = AsyncMock(return_value=(b"ok", b""))
_MOCK_PROC_SUCCESS.returncode = 0

_MOCK_PROC_FAIL = AsyncMock()
_MOCK_PROC_FAIL.communicate = AsyncMock(return_value=(b"", b"mongodump: error"))
_MOCK_PROC_FAIL.returncode = 1


def _s3_settings(tmp_path: Path | None = None) -> MagicMock:
    s = MagicMock()
    s.backup_storage_type = "s3"
    s.backup_s3_endpoint = "http://minio:9000"
    s.backup_s3_bucket = "sentora-backups"
    s.backup_s3_access_key = "minioadmin"
    s.backup_s3_secret_key = "minioadmin"
    s.backup_s3_region = "us-east-1"
    s.mongo_uri = "mongodb://localhost:27017"
    s.mongo_db = "sentora_test"
    s.backup_local_path = str(tmp_path) if tmp_path else "/tmp/backups"
    s.backup_retention_count = 7
    return s


# ── S3 client factory ─────────────────────────────────────────────────────


def test_get_s3_client_creates_boto3_client() -> None:
    """_get_s3_client should call boto3.client with correct params."""
    mock_boto3 = MagicMock()
    with (
        patch("utils.backup.get_settings", return_value=_s3_settings()),
        patch.dict("sys.modules", {"boto3": mock_boto3}),
    ):
        from utils.backup import _get_s3_client

        _get_s3_client()
        mock_boto3.client.assert_called_once_with(
            "s3",
            endpoint_url="http://minio:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            region_name="us-east-1",
        )


# ── S3 upload / download / delete ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_to_s3(tmp_path: Path) -> None:
    archive = tmp_path / "test.archive.gz"
    archive.write_bytes(b"fake archive data")

    mock_s3 = MagicMock()
    with (
        patch("utils.backup.get_settings", return_value=_s3_settings()),
        patch("utils.backup._get_s3_client", return_value=mock_s3),
    ):
        from utils.backup import _upload_to_s3

        size = await _upload_to_s3(archive, "backups/test.archive.gz")

    assert size == len(b"fake archive data")
    mock_s3.upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_download_from_s3(tmp_path: Path) -> None:
    local = tmp_path / "downloaded.gz"

    mock_s3 = MagicMock()
    with (
        patch("utils.backup.get_settings", return_value=_s3_settings()),
        patch("utils.backup._get_s3_client", return_value=mock_s3),
    ):
        from utils.backup import _download_from_s3

        await _download_from_s3("backups/test.gz", local)

    mock_s3.download_file.assert_called_once()


@pytest.mark.asyncio
async def test_delete_from_s3() -> None:
    mock_s3 = MagicMock()
    with (
        patch("utils.backup.get_settings", return_value=_s3_settings()),
        patch("utils.backup._get_s3_client", return_value=mock_s3),
    ):
        from utils.backup import _delete_from_s3

        await _delete_from_s3("backups/test.gz")

    mock_s3.delete_object.assert_called_once_with(
        Bucket="sentora-backups", Key="backups/test.gz"
    )


# ── create_backup S3 path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_backup_s3(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """create_backup with S3 storage uploads to S3 and cleans up local temp."""
    mock_s3 = MagicMock()
    settings = _s3_settings(tmp_path)

    with (
        patch("utils.backup.get_settings", return_value=settings),
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_SUCCESS),
        patch("utils.backup._upload_to_s3", new_callable=AsyncMock, return_value=1024),
    ):
        record = await BackupManager.create_backup(test_db, triggered_by="test")

    assert record.status == "completed"
    assert record.storage_type == "s3"
    assert record.storage_path.startswith("s3://sentora-backups/")


@pytest.mark.asyncio
async def test_create_backup_s3_failure(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """create_backup S3 path records failure when mongodump fails."""
    settings = _s3_settings(tmp_path)

    with (
        patch("utils.backup.get_settings", return_value=settings),
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_FAIL),
    ):
        record = await BackupManager.create_backup(test_db, triggered_by="test")

    assert record.status == "failed"
    assert "mongodump" in (record.error or "")


# ── restore S3 path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_from_s3(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """restore_from_backup with S3 storage downloads, restores, and cleans up."""
    settings = _s3_settings(tmp_path)

    # Seed a completed S3 backup record
    record = BackupRecord(
        id="b_s3_restore",
        timestamp="2026-01-01T00:00:00",
        storage_type="s3",
        storage_path="s3://sentora-backups/backups/b_s3_restore.archive.gz",
        checksum_sha256="abc123",
        status="completed",
    )
    await test_db["backup_history"].insert_one(record.to_dict())

    with (
        patch("utils.backup.get_settings", return_value=settings),
        patch(
            "utils.backup._download_from_s3",
            new_callable=AsyncMock,
            side_effect=lambda key, path: path.write_bytes(b"archive"),
        ),
        patch(
            "utils.backup._compute_sha256",
            return_value="abc123",
        ),
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_SUCCESS),
    ):
        await BackupManager.restore_from_backup(test_db, "b_s3_restore")


# ── delete S3 backup ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_backup_s3(test_db: AsyncIOMotorDatabase) -> None:
    """delete_backup with S3 storage calls _delete_from_s3."""
    record = BackupRecord(
        id="b_s3_del",
        timestamp="2026-01-01T00:00:00",
        storage_type="s3",
        storage_path="s3://sentora-backups/backups/b_s3_del.archive.gz",
        status="completed",
    )
    await test_db["backup_history"].insert_one(record.to_dict())

    settings = _s3_settings()
    with (
        patch("utils.backup.get_settings", return_value=settings),
        patch("utils.backup._delete_from_s3", new_callable=AsyncMock),
    ):
        deleted = await BackupManager.delete_backup(test_db, "b_s3_del")
    assert deleted is True
    assert await test_db["backup_history"].count_documents({}) == 0


@pytest.mark.asyncio
async def test_delete_backup_s3_error_propagates(test_db: AsyncIOMotorDatabase) -> None:
    """delete_backup propagates S3 deletion errors."""
    record = BackupRecord(
        id="b_s3_err",
        timestamp="2026-01-01T00:00:00",
        storage_type="s3",
        storage_path="s3://sentora-backups/backups/b_s3_err.archive.gz",
        status="completed",
    )
    await test_db["backup_history"].insert_one(record.to_dict())

    settings = _s3_settings()
    with (
        patch("utils.backup.get_settings", return_value=settings),
        patch(
            "utils.backup._delete_from_s3",
            new_callable=AsyncMock,
            side_effect=RuntimeError("S3 error"),
        ),
    ):
        with pytest.raises(RuntimeError, match="S3 error"):
            await BackupManager.delete_backup(test_db, "b_s3_err")


# ── enforce_retention S3 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enforce_retention_local(test_db: AsyncIOMotorDatabase, tmp_path: Path) -> None:
    """enforce_retention deletes excess local backups beyond retention count."""
    for i in range(3):
        d = tmp_path / f"b_ret_s3_{i}"
        d.mkdir()
        (d / "data.bson").write_bytes(f"data{i}".encode())
        record = BackupRecord(
            id=f"b_ret_s3_{i}",
            timestamp=f"2026-01-0{i + 1}T00:00:00",
            storage_path=str(d),
            status="completed",
        )
        await test_db["backup_history"].insert_one(record.to_dict())

    settings = _s3_settings(tmp_path)
    settings.backup_retention_count = 2

    with patch("utils.backup.get_settings", return_value=settings):
        deleted = await BackupManager.enforce_retention(test_db)

    assert deleted == 1
    assert await test_db["backup_history"].count_documents({}) == 2
