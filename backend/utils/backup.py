"""Automated MongoDB backup and restore manager.

Supports two storage backends:
- **local**: ``mongodump --gzip`` to a local filesystem directory (default).
- **s3**: ``mongodump --archive --gzip`` piped to S3-compatible storage
  (MinIO, AWS S3, GCS). No filesystem required.

Backup metadata is always stored in the ``backup_history`` MongoDB collection.
The storage backend is selected via ``BACKUP_STORAGE_TYPE`` (``local`` or ``s3``).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shutil
import tempfile
import time
import uuid as _uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from utils.dt import utc_now


@dataclass
class BackupRecord:
    """Metadata for a single backup."""

    id: str
    timestamp: str
    size_bytes: int = 0
    checksum_sha256: str = ""
    storage_type: str = "local"
    storage_path: str = ""
    status: str = "in_progress"  # in_progress | completed | failed
    triggered_by: str = "manual"
    duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for MongoDB insertion."""
        d = asdict(self)
        d["_id"] = d.pop("id")
        return d

    @classmethod
    def from_doc(cls, doc: dict) -> BackupRecord:
        """Construct a BackupRecord from a MongoDB document."""
        doc = dict(doc)
        doc["id"] = doc.pop("_id")
        # Drop unknown keys that may be in the document
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in doc.items() if k in known})


def _compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file or directory tree."""
    h = hashlib.sha256()
    if path.is_file():
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    elif path.is_dir():
        for root, _dirs, files in sorted(os.walk(path)):
            for name in sorted(files):
                fp = Path(root) / name
                with open(fp, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
    return h.hexdigest()


def _dir_size(path: Path) -> int:
    """Return the total size in bytes of all files under *path*."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += (Path(root) / name).stat().st_size
    return total


async def _run_mongo_tool(
    tool: str,
    mongo_uri: str,
    extra_args: list[str],
) -> tuple[int, bytes, bytes]:
    """Launch a MongoDB CLI tool without leaking credentials in process args.

    Writes the connection URI to a temporary config file and passes it via
    ``--config=``, so credentials are not visible in ``ps aux`` output.

    Args:
        tool: Binary name (``mongodump`` or ``mongorestore``).
        mongo_uri: Full MongoDB connection URI (may contain credentials).
        extra_args: Additional command-line arguments for the tool.

    Returns:
        Tuple of (return_code, stdout_bytes, stderr_bytes).
    """
    # mongodump/mongorestore accept a YAML config file via --config.
    # Placing the URI there keeps it out of the process argument list.
    config_content = f'uri: "{mongo_uri}"\n'
    fd, config_path = tempfile.mkstemp(prefix="mongo_cfg_", suffix=".yaml")
    try:
        os.write(fd, config_content.encode())
        os.close(fd)
        # Restrict permissions to owner-only
        os.chmod(config_path, 0o600)

        cmd = [tool, f"--config={config_path}", *extra_args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode or 0, stdout or b"", stderr or b""
    finally:
        # Clean up the temp config file
        with contextlib.suppress(OSError):
            os.unlink(config_path)


def _get_s3_client():  # noqa: ANN202
    """Create a boto3 S3 client using backup config settings.

    Returns:
        A boto3 S3 client configured for the backup endpoint.
    """
    import boto3

    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.backup_s3_endpoint,
        aws_access_key_id=settings.backup_s3_access_key,
        aws_secret_access_key=settings.backup_s3_secret_key,
        region_name=settings.backup_s3_region,
    )


async def _upload_to_s3(local_path: Path, s3_key: str) -> int:
    """Upload a file or archive to S3 and return its size in bytes.

    Args:
        local_path: Path to the local file to upload.
        s3_key: The S3 object key (path within the bucket).

    Returns:
        Size of the uploaded file in bytes.
    """
    settings = get_settings()
    s3 = _get_s3_client()
    size = local_path.stat().st_size
    s3.upload_file(str(local_path), settings.backup_s3_bucket, s3_key)
    logger.info(
        "Uploaded {} to s3://{}/{} ({} bytes)",
        local_path.name,
        settings.backup_s3_bucket,
        s3_key,
        size,
    )
    return size


async def _download_from_s3(s3_key: str, local_path: Path) -> None:
    """Download an object from S3 to a local file.

    Args:
        s3_key: The S3 object key to download.
        local_path: Local path to write the downloaded file.
    """
    settings = get_settings()
    s3 = _get_s3_client()
    s3.download_file(settings.backup_s3_bucket, s3_key, str(local_path))
    logger.info("Downloaded s3://{}/{} → {}", settings.backup_s3_bucket, s3_key, local_path)


async def _delete_from_s3(s3_key: str) -> None:
    """Delete an object from S3.

    Args:
        s3_key: The S3 object key to delete.
    """
    settings = get_settings()
    s3 = _get_s3_client()
    s3.delete_object(Bucket=settings.backup_s3_bucket, Key=s3_key)
    logger.info("Deleted s3://{}/{}", settings.backup_s3_bucket, s3_key)


class BackupManager:
    """Manages MongoDB backup and restore operations."""

    @staticmethod
    async def create_backup(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        triggered_by: str = "manual",
    ) -> BackupRecord:
        """Create a new MongoDB backup using ``mongodump --gzip``.

        Args:
            db: The Motor database handle.
            triggered_by: Who or what initiated the backup (e.g. "manual", "scheduler").

        Returns:
            A BackupRecord with the outcome (completed or failed).
        """
        settings = get_settings()
        now = utc_now()
        backup_id = now.strftime("backup_%Y%m%d_%H%M%S") + "_" + _uuid.uuid4().hex[:6]
        use_s3 = settings.backup_storage_type == "s3"

        record = BackupRecord(
            id=backup_id,
            timestamp=now.isoformat(),
            storage_type="s3" if use_s3 else "local",
            triggered_by=triggered_by,
        )

        # Persist initial in_progress record
        await db["backup_history"].insert_one(record.to_dict())

        start = time.monotonic()
        try:
            if use_s3:
                # Archive mode → single gzipped file → upload to S3
                archive_path = Path(tempfile.mkdtemp()) / f"{backup_id}.archive.gz"
                logger.info("Starting backup {} → S3 ({})", backup_id, settings.backup_s3_bucket)

                returncode, _stdout, stderr = await _run_mongo_tool(
                    "mongodump",
                    settings.mongo_uri,
                    [
                        f"--db={settings.mongo_db}",
                        f"--archive={archive_path}",
                        "--gzip",
                    ],
                )
                if returncode != 0:
                    raise RuntimeError(stderr.decode().strip() if stderr else "mongodump failed")

                s3_key = f"backups/{backup_id}.archive.gz"
                record.size_bytes = await _upload_to_s3(archive_path, s3_key)
                record.checksum_sha256 = _compute_sha256(archive_path)
                record.storage_path = f"s3://{settings.backup_s3_bucket}/{s3_key}"

                # Clean up local temp file
                with contextlib.suppress(OSError):
                    archive_path.unlink()
                    archive_path.parent.rmdir()
            else:
                # Directory mode → local filesystem
                backup_dir = Path(settings.backup_local_path) / backup_id
                backup_dir.mkdir(parents=True, exist_ok=True)
                record.storage_path = str(backup_dir)
                logger.info("Starting backup {} → {}", backup_id, backup_dir)

                returncode, _stdout, stderr = await _run_mongo_tool(
                    "mongodump",
                    settings.mongo_uri,
                    [
                        f"--db={settings.mongo_db}",
                        f"--out={backup_dir}",
                        "--gzip",
                    ],
                )
                if returncode != 0:
                    raise RuntimeError(stderr.decode().strip() if stderr else "mongodump failed")

                record.size_bytes = _dir_size(backup_dir)
                record.checksum_sha256 = _compute_sha256(backup_dir)

            record.duration_seconds = round(time.monotonic() - start, 2)
            record.status = "completed"
            logger.info(
                "Backup {} completed — {:.1f}s, {} bytes, storage={}",
                backup_id,
                record.duration_seconds,
                record.size_bytes,
                record.storage_type,
            )
        except Exception as exc:
            record.duration_seconds = round(time.monotonic() - start, 2)
            record.status = "failed"
            record.error = str(exc)
            logger.error("Backup {} failed: {}", backup_id, exc)

        # Update the record in MongoDB
        update = {k: v for k, v in asdict(record).items() if k != "id"}
        await db["backup_history"].update_one({"_id": backup_id}, {"$set": update})

        return record

    @staticmethod
    async def restore_from_backup(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        backup_id: str,
    ) -> None:
        """Restore the database from a previously created backup.

        Args:
            db: The Motor database handle.
            backup_id: The ID of the backup to restore.

        Raises:
            ValueError: If the backup is not found or checksum verification fails.
            RuntimeError: If ``mongorestore`` returns a non-zero exit code.
        """
        settings = get_settings()

        doc = await db["backup_history"].find_one({"_id": backup_id})
        if not doc:
            raise ValueError(f"Backup '{backup_id}' not found")

        record = BackupRecord.from_doc(doc)

        if record.storage_type == "s3":
            # Download archive from S3, restore, then clean up
            s3_key = record.storage_path.replace(f"s3://{settings.backup_s3_bucket}/", "")
            tmp_dir = Path(tempfile.mkdtemp())
            archive_path = tmp_dir / f"{backup_id}.archive.gz"
            try:
                await _download_from_s3(s3_key, archive_path)

                if record.checksum_sha256:
                    current = _compute_sha256(archive_path)
                    if current != record.checksum_sha256:
                        raise ValueError(
                            f"Checksum mismatch: expected {record.checksum_sha256}, got {current}"
                        )

                logger.info("Restoring from S3 backup {}", backup_id)
                returncode, _stdout, stderr = await _run_mongo_tool(
                    "mongorestore",
                    settings.mongo_uri,
                    [
                        f"--db={settings.mongo_db}",
                        f"--archive={archive_path}",
                        "--gzip",
                        "--drop",
                    ],
                )
                if returncode != 0:
                    raise RuntimeError(stderr.decode().strip() if stderr else "mongorestore failed")
            finally:
                with contextlib.suppress(OSError):
                    archive_path.unlink()
                    tmp_dir.rmdir()
        else:
            # Local filesystem restore
            backup_dir = Path(record.storage_path).resolve()
            expected_base = Path(settings.backup_local_path).resolve()
            if not backup_dir.is_relative_to(expected_base):
                raise ValueError("Backup path outside expected directory")
            if not backup_dir.exists():
                raise ValueError(f"Backup directory does not exist: {backup_dir}")

            if record.checksum_sha256:
                current = _compute_sha256(backup_dir)
                if current != record.checksum_sha256:
                    raise ValueError(
                        f"Checksum mismatch: expected {record.checksum_sha256}, got {current}"
                    )

            dump_path = backup_dir / settings.mongo_db
            if not dump_path.exists():
                dump_path = backup_dir

            logger.info("Restoring from local backup {} ({})", backup_id, dump_path)
            returncode, _stdout, stderr = await _run_mongo_tool(
                "mongorestore",
                settings.mongo_uri,
                [
                    f"--db={settings.mongo_db}",
                    "--gzip",
                    "--drop",
                    str(dump_path),
                ],
            )
            if returncode != 0:
                raise RuntimeError(stderr.decode().strip() if stderr else "mongorestore failed")

        logger.info("Restore from backup {} completed successfully", backup_id)

    @staticmethod
    async def list_backups(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[BackupRecord], int]:
        """List backups sorted by timestamp descending.

        Args:
            db: The Motor database handle.
            skip: Number of records to skip (pagination).
            limit: Maximum number of records to return.

        Returns:
            Tuple of (list of BackupRecords, total count).
        """
        total = await db["backup_history"].count_documents({})
        cursor = db["backup_history"].find().sort("timestamp", -1).skip(skip).limit(limit)
        records = [BackupRecord.from_doc(doc) async for doc in cursor]
        return records, total

    @staticmethod
    async def get_backup(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        backup_id: str,
    ) -> BackupRecord | None:
        """Fetch a single backup record by ID.

        Args:
            db: The Motor database handle.
            backup_id: The backup ID to look up.

        Returns:
            The BackupRecord if found, else None.
        """
        doc = await db["backup_history"].find_one({"_id": backup_id})
        if doc is None:
            return None
        return BackupRecord.from_doc(doc)

    @staticmethod
    async def enforce_retention(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    ) -> int:
        """Delete the oldest backups exceeding the retention count.

        Deletes both the backup files on disk and the corresponding
        ``backup_history`` documents.

        Args:
            db: The Motor database handle.

        Returns:
            Number of backups deleted.
        """
        settings = get_settings()
        retention = settings.backup_retention_count

        total = await db["backup_history"].count_documents({})
        if total <= retention:
            return 0

        excess = total - retention
        cursor = (
            db["backup_history"]
            .find()
            .sort("timestamp", 1)  # oldest first
            .limit(excess)
        )

        expected_base = Path(settings.backup_local_path).resolve()

        deleted = 0
        async for doc in cursor:
            record = BackupRecord.from_doc(doc)
            # Remove files from disk
            backup_path = Path(record.storage_path).resolve()

            # Guard against path traversal — same check used by restore/delete
            if not backup_path.is_relative_to(expected_base):
                logger.warning(
                    "Retention skip: backup path '{}' is outside expected base '{}'",
                    backup_path,
                    expected_base,
                )
                continue

            if backup_path.exists():
                try:
                    shutil.rmtree(backup_path)
                    logger.info("Deleted backup files: {}", backup_path)
                except OSError as exc:
                    logger.warning("Failed to delete backup files {}: {}", backup_path, exc)
                    continue  # skip DB record deletion — avoid orphaning

            await db["backup_history"].delete_one({"_id": record.id})
            deleted += 1
            logger.info("Removed backup record: {}", record.id)

        if deleted:
            logger.info("Retention enforcement: deleted {} old backup(s)", deleted)
        return deleted

    @staticmethod
    async def verify_backup(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        backup_id: str,
    ) -> bool:
        """Verify the SHA-256 checksum of a stored backup.

        Args:
            db: The Motor database handle.
            backup_id: The backup ID to verify.

        Returns:
            True if the checksum matches, False otherwise.

        Raises:
            ValueError: If the backup is not found or has no checksum.
        """
        doc = await db["backup_history"].find_one({"_id": backup_id})
        if not doc:
            raise ValueError(f"Backup '{backup_id}' not found")

        record = BackupRecord.from_doc(doc)
        if not record.checksum_sha256:
            raise ValueError(f"Backup '{backup_id}' has no stored checksum")

        backup_path = Path(record.storage_path)
        if not backup_path.exists():
            return False

        current = _compute_sha256(backup_path)
        return current == record.checksum_sha256

    @staticmethod
    async def delete_backup(
        db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
        backup_id: str,
    ) -> bool:
        """Delete a single backup (files + record).

        Args:
            db: The Motor database handle.
            backup_id: The backup ID to delete.

        Returns:
            True if the backup was found and deleted, False if not found.
        """
        doc = await db["backup_history"].find_one({"_id": backup_id})
        if not doc:
            return False

        record = BackupRecord.from_doc(doc)
        settings = get_settings()

        if record.storage_type == "s3":
            s3_key = record.storage_path.replace(f"s3://{settings.backup_s3_bucket}/", "")
            try:
                await _delete_from_s3(s3_key)
            except Exception as exc:
                logger.warning("Failed to delete S3 object {}: {}", s3_key, exc)
                raise
        else:
            backup_path = Path(record.storage_path).resolve()
            expected_base = Path(settings.backup_local_path).resolve()
            if not backup_path.is_relative_to(expected_base):
                raise ValueError("Backup path outside expected directory")
            if backup_path.exists():
                try:
                    shutil.rmtree(backup_path)
                except OSError as exc:
                    logger.warning("Failed to delete backup files {}: {}", backup_path, exc)
                    raise

        await db["backup_history"].delete_one({"_id": backup_id})
        logger.info("Deleted backup {}", backup_id)
        return True
