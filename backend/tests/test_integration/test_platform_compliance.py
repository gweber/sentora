"""Integration tests for the platform compliance sub-module.

Tests Sentora's own security posture evaluation (SOC 2 / ISO 27001)
via the /api/v1/compliance/platform/ endpoints.  These check RBAC,
audit logs, backups, MFA adoption — not the managed endpoint fleet.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


# ── Dashboard ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_soc2(client: AsyncClient, admin_headers: dict) -> None:
    """SOC 2 dashboard returns all 8 controls with aggregate scores."""
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/soc2", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["framework"] == "soc2"
    assert data["total_controls"] == 8
    assert (
        data["passing"] + data["warning"] + data["failing"] + data["not_applicable"]
        == data["total_controls"]
    )
    assert 0.0 <= data["score_percent"] <= 100.0
    assert len(data["controls"]) == 8


@pytest.mark.asyncio
async def test_dashboard_iso27001(client: AsyncClient, admin_headers: dict) -> None:
    """ISO 27001 dashboard returns all 6 controls."""
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/iso27001", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["framework"] == "iso27001"
    assert data["total_controls"] == 6
    assert len(data["controls"]) == 6


@pytest.mark.asyncio
async def test_dashboard_unknown_framework(client: AsyncClient, admin_headers: dict) -> None:
    """Unknown framework returns 400."""
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/pci-dss", headers=admin_headers
    )
    assert resp.status_code == 400
    assert "Unknown framework" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient) -> None:
    """Dashboard endpoint requires authentication."""
    resp = await client.get("/api/v1/compliance/platform/dashboard/soc2")
    assert resp.status_code == 401


# ── Controls with data ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soc2_cc6_1_multi_role(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """CC6.1 passes with role separation when multiple roles exist."""
    await seeded_db["users"].insert_many([
        {"username": "u1", "email": "u1@t.com", "role": "admin", "disabled": False, "hashed_password": ""},
        {"username": "u2", "email": "u2@t.com", "role": "viewer", "disabled": False, "hashed_password": ""},
    ])
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/soc2", headers=admin_headers
    )
    cc6_1 = next(c for c in resp.json()["controls"] if c["reference"] == "CC6.1")
    assert cc6_1["status"] == "passing"
    assert "Role separation" in cc6_1["evidence_summary"]


@pytest.mark.asyncio
async def test_soc2_cc6_1_all_admins_warning(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """CC6.1 warns when all users are admins."""
    await seeded_db["users"].insert_one(
        {"username": "solo_admin", "email": "a@t.com", "role": "admin", "disabled": False, "hashed_password": ""},
    )
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/soc2", headers=admin_headers
    )
    cc6_1 = next(c for c in resp.json()["controls"] if c["reference"] == "CC6.1")
    assert cc6_1["status"] == "warning"
    assert "consider role separation" in cc6_1["evidence_summary"]


@pytest.mark.asyncio
async def test_soc2_cc7_2_with_audit_logs(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """CC7.2 passes when recent audit log entries exist."""
    now = utc_now()
    await seeded_db["audit_log"].insert_one(
        {"timestamp": now, "created_at": now, "domain": "auth", "action": "login", "actor": "test"}
    )
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/soc2", headers=admin_headers
    )
    cc7_2 = next(c for c in resp.json()["controls"] if c["reference"] == "CC7.2")
    assert cc7_2["status"] == "passing"
    assert "audit events in last 24h" in cc7_2["evidence_summary"]


@pytest.mark.asyncio
async def test_soc2_a1_1_with_backups(
    client: AsyncClient, admin_headers: dict, seeded_db: AsyncIOMotorDatabase
) -> None:
    """A1.1 passes when successful backups exist."""
    await seeded_db["backup_history"].insert_one(
        {"status": "completed", "timestamp": utc_now().isoformat()}
    )
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/soc2", headers=admin_headers
    )
    a1_1 = next(c for c in resp.json()["controls"] if c["reference"] == "A1.1")
    assert a1_1["status"] == "passing"
    assert "successful backup" in a1_1["evidence_summary"]


@pytest.mark.asyncio
async def test_iso_a7_physical_is_na(
    client: AsyncClient, admin_headers: dict
) -> None:
    """ISO A.7 physical controls are always N/A for SaaS."""
    resp = await client.get(
        "/api/v1/compliance/platform/dashboard/iso27001", headers=admin_headers
    )
    a7 = next(c for c in resp.json()["controls"] if c["reference"] == "A.7")
    assert a7["status"] == "not_applicable"


# ── Report generation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_report(client: AsyncClient, admin_headers: dict) -> None:
    """Generate a SOC 2 platform compliance report."""
    resp = await client.post(
        "/api/v1/compliance/platform/reports",
        json={"framework": "soc2", "period_days": 30},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["framework"] == "soc2"
    assert report["status"] == "completed"
    assert report["total_controls"] == 8
    assert report["generated_by"] == "testadmin"


@pytest.mark.asyncio
async def test_list_reports_empty(client: AsyncClient, admin_headers: dict) -> None:
    """List reports returns empty when none exist."""
    resp = await client.get(
        "/api/v1/compliance/platform/reports", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["reports"] == []


@pytest.mark.asyncio
async def test_report_detail_and_delete(client: AsyncClient, admin_headers: dict) -> None:
    """Get report detail and then delete it."""
    create = await client.post(
        "/api/v1/compliance/platform/reports",
        json={"framework": "iso27001", "period_days": 90},
        headers=admin_headers,
    )
    report_id = create.json()["id"]

    detail = await client.get(
        f"/api/v1/compliance/platform/reports/{report_id}", headers=admin_headers
    )
    assert detail.status_code == 200
    assert len(detail.json()["controls"]) == 6

    delete = await client.delete(
        f"/api/v1/compliance/platform/reports/{report_id}", headers=admin_headers
    )
    assert delete.status_code == 200

    get_after = await client.get(
        f"/api/v1/compliance/platform/reports/{report_id}", headers=admin_headers
    )
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_report_csv_export(client: AsyncClient, admin_headers: dict) -> None:
    """Export a platform report as CSV."""
    create = await client.post(
        "/api/v1/compliance/platform/reports",
        json={"framework": "soc2", "period_days": 30},
        headers=admin_headers,
    )
    report_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/compliance/platform/reports/{report_id}/csv", headers=admin_headers
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 2  # header + data


@pytest.mark.asyncio
async def test_generate_report_requires_admin(
    client: AsyncClient, analyst_headers: dict
) -> None:
    """Non-admin roles cannot generate platform reports."""
    resp = await client.post(
        "/api/v1/compliance/platform/reports",
        json={"framework": "soc2", "period_days": 30},
        headers=analyst_headers,
    )
    assert resp.status_code == 403
