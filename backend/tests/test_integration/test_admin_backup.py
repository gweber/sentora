"""Integration tests for admin backup/restore endpoints.

Tests the admin router's backup CRUD operations via the HTTP API.
Actual mongodump/mongorestore calls are not tested here — those require
the mongodb-database-tools binary. Instead, we test the API layer
and database record management.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.backup import BackupRecord, _compute_sha256

# ── Helpers ─────────────────────────────────────────────────────────────────


async def _seed_backup(
    db: AsyncIOMotorDatabase, backup_id: str = "b_test", **overrides: object
) -> None:
    """Insert a backup record directly into the test database."""
    defaults = {
        "id": backup_id,
        "timestamp": "2026-03-15T10:00:00",
        "status": "completed",
        "size_bytes": 1024,
        "storage_path": f"/backups/{backup_id}",
    }
    defaults.update(overrides)
    record = BackupRecord(**defaults)  # type: ignore[arg-type]  # kwargs from dynamic dict
    await db["backup_history"].insert_one(record.to_dict())


# ── List backups ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_backups_empty(client: AsyncClient, admin_headers: dict) -> None:
    """List backups returns empty list when none exist."""
    resp = await client.get("/api/v1/admin/backups", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["backups"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_backups_with_data(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """List backups returns seeded records."""
    await _seed_backup(seeded_db, "b1", timestamp="2026-01-01T00:00:00")
    await _seed_backup(seeded_db, "b2", timestamp="2026-01-02T00:00:00")

    resp = await client.get("/api/v1/admin/backups", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # Sorted by timestamp descending
    assert data["backups"][0]["id"] == "b2"


@pytest.mark.asyncio
async def test_list_backups_pagination(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """List backups supports skip/limit pagination."""
    for i in range(5):
        await _seed_backup(seeded_db, f"bp_{i}", timestamp=f"2026-01-0{i + 1}T00:00:00")

    resp = await client.get("/api/v1/admin/backups?skip=2&limit=2", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["backups"]) == 2


# ── Get single backup ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_backup_found(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """Get backup by ID returns the record."""
    await _seed_backup(seeded_db, "b_found")
    resp = await client.get("/api/v1/admin/backups/b_found", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == "b_found"
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_get_backup_not_found(client: AsyncClient, admin_headers: dict) -> None:
    """Get nonexistent backup returns 404."""
    resp = await client.get("/api/v1/admin/backups/nonexistent", headers=admin_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# ── Delete backup ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_backup(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """Delete backup removes the DB record."""
    await _seed_backup(seeded_db, "b_delete")
    resp = await client.delete("/api/v1/admin/backups/b_delete", headers=admin_headers)
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get("/api/v1/admin/backups/b_delete", headers=admin_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_backup_not_found(client: AsyncClient, admin_headers: dict) -> None:
    """Delete nonexistent backup returns 404."""
    resp = await client.delete("/api/v1/admin/backups/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


# ── Auth enforcement ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_backups_requires_admin(client: AsyncClient, analyst_headers: dict) -> None:
    """Analyst role cannot access admin backup endpoints."""
    resp = await client.get("/api/v1/admin/backups", headers=analyst_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_backups_unauthenticated(client: AsyncClient) -> None:
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/v1/admin/backups")
    assert resp.status_code == 401


# ── Trigger backup (mocked subprocess) ─────────────────────────────────────

_MOCK_PROC_SUCCESS = AsyncMock()
_MOCK_PROC_SUCCESS.communicate = AsyncMock(return_value=(b"ok", b""))
_MOCK_PROC_SUCCESS.returncode = 0


@pytest.mark.asyncio
async def test_trigger_backup(client: AsyncClient, admin_headers: dict, tmp_path: Path) -> None:
    """POST /admin/backup triggers mongodump and returns a backup record."""
    with (
        patch("utils.backup.get_settings") as mock_settings,
        patch("asyncio.create_subprocess_exec", return_value=_MOCK_PROC_SUCCESS),
    ):
        mock_settings.return_value.backup_local_path = str(tmp_path)
        mock_settings.return_value.mongo_uri = "mongodb://localhost:27017"
        mock_settings.return_value.mongo_db = "sentora_test"

        resp = await client.post("/api/v1/admin/backup", headers=admin_headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert data["triggered_by"] == "manual"


# ── Verify backup endpoint ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_backup_endpoint(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase, tmp_path: Path
) -> None:
    """POST /admin/backups/{id}/verify returns valid=True for intact backup."""
    backup_dir = tmp_path / "b_verify_api"
    backup_dir.mkdir()
    (backup_dir / "data.bson").write_bytes(b"test data")
    checksum = _compute_sha256(backup_dir)

    await _seed_backup(
        seeded_db,
        "b_verify_api",
        storage_path=str(backup_dir),
        checksum_sha256=checksum,
    )
    resp = await client.post("/api/v1/admin/backups/b_verify_api/verify", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_verify_backup_endpoint_not_found(client: AsyncClient, admin_headers: dict) -> None:
    """POST /admin/backups/{id}/verify returns 404 for nonexistent backup."""
    resp = await client.post("/api/v1/admin/backups/nonexistent/verify", headers=admin_headers)
    assert resp.status_code == 404


# ── Restore backup endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_endpoint_not_found(client: AsyncClient, admin_headers: dict) -> None:
    """POST /admin/restore returns 404 when backup doesn't exist."""
    resp = await client.post(
        "/api/v1/admin/restore",
        json={"backup_id": "nonexistent"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_endpoint_accepted(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """POST /admin/restore returns 200 with accepted status for valid backup."""
    await _seed_backup(seeded_db, "b_restore_api")
    resp = await client.post(
        "/api/v1/admin/restore",
        json={"backup_id": "b_restore_api"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert "b_restore_api" in data["message"]
