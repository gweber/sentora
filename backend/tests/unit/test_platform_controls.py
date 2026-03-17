"""Tests for compliance platform controls (SOC 2 + ISO 27001)."""

from __future__ import annotations

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.platform.controls import (
    iso_a5_access_control,
    iso_a6_people_controls,
    iso_a7_physical_controls,
    iso_a8_backup,
    iso_a8_logging,
    iso_a8_technological_controls,
    soc2_a1_1_availability,
    soc2_cc2_1_communication,
    soc2_cc3_1_risk_assessment,
    soc2_cc6_1_access_control,
    soc2_cc6_2_auth_mechanisms,
    soc2_cc6_3_access_revocation,
    soc2_cc7_2_monitoring,
    soc2_cc8_1_change_management,
)
from domains.compliance.platform.entities import ControlStatus


# ── SOC 2 Controls ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cc6_1_no_users(test_db: AsyncIOMotorDatabase) -> None:
    result = await soc2_cc6_1_access_control(test_db)
    assert result.status == ControlStatus.warning


@pytest.mark.asyncio
async def test_cc6_1_multiple_roles(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["users"].insert_many([
        {"username": "admin1", "email": "admin1@test.co", "role": "admin", "disabled": False},
        {"username": "viewer1", "email": "viewer1@test.co", "role": "viewer", "disabled": False},
    ])
    result = await soc2_cc6_1_access_control(test_db)
    assert result.status == ControlStatus.passing


@pytest.mark.asyncio
async def test_cc6_1_all_admins(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["users"].insert_many([
        {"username": "admin1", "email": "a1@test.co", "role": "admin", "disabled": False},
        {"username": "admin2", "email": "a2@test.co", "role": "admin", "disabled": False},
    ])
    result = await soc2_cc6_1_access_control(test_db)
    assert result.status == ControlStatus.warning


@pytest.mark.asyncio
async def test_cc6_2_with_mfa(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["users"].insert_many([
        {"username": "u1", "email": "u1@test.co", "totp_enabled": True},
        {"username": "u2", "email": "u2@test.co", "totp_enabled": False},
    ])
    result = await soc2_cc6_2_auth_mechanisms(test_db)
    assert result.control_id == "soc2-cc6.2"


@pytest.mark.asyncio
async def test_cc6_3_revocation(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["users"].insert_one({"username": "u1", "email": "u1@test.co", "disabled": True})
    result = await soc2_cc6_3_access_revocation(test_db)
    assert result.status == ControlStatus.passing


@pytest.mark.asyncio
async def test_cc7_2_no_audit_entries(test_db: AsyncIOMotorDatabase) -> None:
    result = await soc2_cc7_2_monitoring(test_db)
    assert result.status == ControlStatus.failing


@pytest.mark.asyncio
async def test_cc8_1_no_changes(test_db: AsyncIOMotorDatabase) -> None:
    result = await soc2_cc8_1_change_management(test_db)
    assert result.status == ControlStatus.warning


@pytest.mark.asyncio
async def test_a1_1_no_backups(test_db: AsyncIOMotorDatabase) -> None:
    result = await soc2_a1_1_availability(test_db)
    assert result.status == ControlStatus.failing


@pytest.mark.asyncio
async def test_a1_1_with_backups(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["backup_history"].insert_one({"status": "completed"})
    result = await soc2_a1_1_availability(test_db)
    assert result.status == ControlStatus.passing


@pytest.mark.asyncio
async def test_a1_1_with_failures(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["backup_history"].insert_many([
        {"status": "completed"},
        {"status": "failed"},
    ])
    result = await soc2_a1_1_availability(test_db)
    assert result.status == ControlStatus.warning


@pytest.mark.asyncio
async def test_cc3_1_no_agents(test_db: AsyncIOMotorDatabase) -> None:
    result = await soc2_cc3_1_risk_assessment(test_db)
    assert result.status == ControlStatus.warning


@pytest.mark.asyncio
async def test_cc2_1_no_webhooks(test_db: AsyncIOMotorDatabase) -> None:
    result = await soc2_cc2_1_communication(test_db)
    assert result.status == ControlStatus.passing  # optional


# ── ISO 27001 Controls ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iso_a5_no_users(test_db: AsyncIOMotorDatabase) -> None:
    result = await iso_a5_access_control(test_db)
    assert result.status == ControlStatus.warning
    assert result.framework == "iso27001"


@pytest.mark.asyncio
async def test_iso_a5_with_users(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["users"].insert_many([
        {"username": "u1", "email": "u1@test.co", "role": "admin"},
        {"username": "u2", "email": "u2@test.co", "role": "viewer"},
    ])
    result = await iso_a5_access_control(test_db)
    assert result.status == ControlStatus.passing


@pytest.mark.asyncio
async def test_iso_a6_people(test_db: AsyncIOMotorDatabase) -> None:
    await test_db["users"].insert_one({"username": "u1", "email": "u1@test.co", "disabled": False})
    result = await iso_a6_people_controls(test_db)
    assert result.status == ControlStatus.passing


@pytest.mark.asyncio
async def test_iso_a7_physical_na(test_db: AsyncIOMotorDatabase) -> None:
    result = await iso_a7_physical_controls(test_db)
    assert result.status == ControlStatus.not_applicable


@pytest.mark.asyncio
async def test_iso_a8_tech_no_audit(test_db: AsyncIOMotorDatabase) -> None:
    result = await iso_a8_technological_controls(test_db)
    assert result.status == ControlStatus.warning


@pytest.mark.asyncio
async def test_iso_a8_backup_none(test_db: AsyncIOMotorDatabase) -> None:
    result = await iso_a8_backup(test_db)
    assert result.status == ControlStatus.failing


@pytest.mark.asyncio
async def test_iso_a8_logging_none(test_db: AsyncIOMotorDatabase) -> None:
    result = await iso_a8_logging(test_db)
    assert result.status == ControlStatus.failing
