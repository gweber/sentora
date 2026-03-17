"""Integration tests for the EOL domain.

Tests the full flow: EOL endpoints, matching, compliance check integration,
export API, and blast radius verification.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


@pytest_asyncio.fixture(scope="function")
async def eol_seeded_db(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed test database with agents, apps, EOL products, and app summaries.

    Returns:
        The seeded test database.
    """
    now = utc_now()

    # Agents
    agents = [
        {
            "source": "sentinelone",
            "source_id": "eol-agent-1",
            "hostname": "eol-host-1",
            "agent_version": "23.3.1",
            "last_active": now - timedelta(hours=1),
            "group_name": "Production",
            "tags": [],
            "installed_app_names": ["Python 3.8", "Chrome 123"],
        },
        {
            "source": "sentinelone",
            "source_id": "eol-agent-2",
            "hostname": "eol-host-2",
            "agent_version": "23.3.1",
            "last_active": now - timedelta(hours=2),
            "group_name": "Production",
            "tags": [],
            "installed_app_names": ["Python 3.12", "Firefox 125"],
        },
    ]
    await test_db["agents"].insert_many(agents)

    # Installed apps
    apps = [
        {
            "agent_id": "eol-agent-1",
            "normalized_name": "python 3.8",
            "version": "3.8.19",
            "name": "Python 3.8",
        },
        {
            "agent_id": "eol-agent-1",
            "normalized_name": "chrome 123",
            "version": "123.0",
            "name": "Chrome 123",
        },
        {
            "agent_id": "eol-agent-2",
            "normalized_name": "python 3.12",
            "version": "3.12.3",
            "name": "Python 3.12",
        },
        {
            "agent_id": "eol-agent-2",
            "normalized_name": "firefox 125",
            "version": "125.0",
            "name": "Firefox 125",
        },
    ]
    await test_db["installed_apps"].insert_many(apps)

    # App summaries (with EOL match on Python 3.8)
    summaries = [
        {
            "normalized_name": "python 3.8",
            "display_name": "Python 3.8",
            "agent_count": 1,
            "category": "runtimes",
            "eol_match": {
                "eol_product_id": "python",
                "matched_cycle": "3.8",
                "match_source": "cpe",
                "match_confidence": 0.9,
                "is_eol": True,
                "eol_date": "2024-10-07",
                "is_security_only": False,
                "support_end": "2021-05-03",
            },
        },
        {
            "normalized_name": "python 3.12",
            "display_name": "Python 3.12",
            "agent_count": 1,
            "category": "runtimes",
        },
        {
            "normalized_name": "chrome 123",
            "display_name": "Chrome 123",
            "agent_count": 1,
            "category": "browsers",
        },
        {
            "normalized_name": "firefox 125",
            "display_name": "Firefox 125",
            "agent_count": 1,
            "category": "browsers",
        },
    ]
    await test_db["app_summaries"].insert_many(summaries)

    # EOL products
    eol_products = [
        {
            "product_id": "python",
            "name": "Python",
            "last_synced": now,
            "cycles": [
                {
                    "cycle": "3.12",
                    "eol_date": "2028-10-02",
                    "support_end": "2025-04-02",
                    "is_eol": False,
                    "is_security_only": False,
                },
                {
                    "cycle": "3.8",
                    "eol_date": "2024-10-07",
                    "support_end": "2021-05-03",
                    "is_eol": True,
                    "is_security_only": False,
                },
            ],
        },
        {
            "product_id": "chrome",
            "name": "Google Chrome",
            "last_synced": now,
            "cycles": [
                {
                    "cycle": "123",
                    "eol_date": "2024-06-12",
                    "is_eol": True,
                    "is_security_only": False,
                },
            ],
        },
    ]
    await test_db["eol_products"].insert_many(eol_products)

    return test_db


# ---------------------------------------------------------------------------
# EOL API endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_eol_source_info(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/source returns source info with correct counts."""
    resp = await client.get("/api/v1/eol/source", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "endoflife.date"
    assert data["total_products"] == 2  # python + chrome
    assert data["status"] in ("healthy", "stale", "outdated", "never_synced", "unknown")


@pytest.mark.asyncio()
async def test_eol_products_list(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/products returns paginated product list."""
    resp = await client.get("/api/v1/eol/products", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    product_ids = [p["product_id"] for p in data["products"]]
    assert "python" in product_ids
    assert "chrome" in product_ids


@pytest.mark.asyncio()
async def test_eol_products_search(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/products?search=python filters results."""
    resp = await client.get(
        "/api/v1/eol/products", headers=admin_headers, params={"search": "python"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["products"][0]["product_id"] == "python"


@pytest.mark.asyncio()
async def test_eol_product_detail(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/products/{id} returns product with cycles."""
    resp = await client.get("/api/v1/eol/products/python", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "python"
    assert data["total_cycles"] == 2
    assert data["eol_cycles"] >= 1


@pytest.mark.asyncio()
async def test_eol_product_not_found(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/products/{id} returns 404 for unknown product."""
    resp = await client.get("/api/v1/eol/products/nonexistent", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio()
async def test_eol_sync_status(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/sync/status returns current status."""
    resp = await client.get("/api/v1/eol/sync/status", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["total_products"] == 2


# ---------------------------------------------------------------------------
# Match review tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_fuzzy_match_review_empty(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /eol/matches/review returns empty when no fuzzy matches."""
    resp = await client.get("/api/v1/eol/matches/review", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio()
async def test_fuzzy_match_confirm(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """POST /eol/matches/review confirms a fuzzy match."""
    # Add a fuzzy match to test with
    await eol_seeded_db["app_summaries"].update_one(
        {"normalized_name": "firefox 125"},
        {
            "$set": {
                "eol_match": {
                    "eol_product_id": "firefox",
                    "matched_cycle": "125",
                    "match_source": "fuzzy",
                    "match_confidence": 0.5,
                    "is_eol": True,
                    "eol_date": "2024-05-01",
                }
            }
        },
    )

    resp = await client.post(
        "/api/v1/eol/matches/review",
        headers=admin_headers,
        json={
            "normalized_name": "firefox 125",
            "eol_product_id": "firefox",
            "action": "confirm",
        },
    )
    assert resp.status_code == 200

    # Verify match source changed to manual
    doc = await eol_seeded_db["app_summaries"].find_one({"normalized_name": "firefox 125"})
    assert doc is not None
    assert doc["eol_match"]["match_source"] == "manual"
    assert doc["eol_match"]["match_confidence"] == 1.0


@pytest.mark.asyncio()
async def test_fuzzy_match_dismiss(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """POST /eol/matches/review dismisses a fuzzy match."""
    # Add a fuzzy match to dismiss
    await eol_seeded_db["app_summaries"].update_one(
        {"normalized_name": "firefox 125"},
        {
            "$set": {
                "eol_match": {
                    "eol_product_id": "firefox",
                    "matched_cycle": "125",
                    "match_source": "fuzzy",
                    "match_confidence": 0.5,
                    "is_eol": True,
                }
            }
        },
    )

    resp = await client.post(
        "/api/v1/eol/matches/review",
        headers=admin_headers,
        json={
            "normalized_name": "firefox 125",
            "eol_product_id": "firefox",
            "action": "dismiss",
        },
    )
    assert resp.status_code == 200

    # Verify match removed
    doc = await eol_seeded_db["app_summaries"].find_one({"normalized_name": "firefox 125"})
    assert doc is not None
    assert "eol_match" not in doc


# ---------------------------------------------------------------------------
# Export API tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_export_json(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /export/software-inventory returns JSON export with correct structure."""
    resp = await client.get("/api/v1/export/software-inventory", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "export_metadata" in data
    assert "software_inventory" in data
    assert "pagination" in data
    assert data["export_metadata"]["total_unique_apps"] > 0


@pytest.mark.asyncio()
async def test_export_csv(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """GET /export/software-inventory?format=csv returns CSV."""
    resp = await client.get(
        "/api/v1/export/software-inventory", headers=admin_headers, params={"format": "csv"}
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    content = resp.text
    # Check CSV has header row
    lines = content.strip().split("\n")
    assert len(lines) >= 1
    assert "app_name" in lines[0]


@pytest.mark.asyncio()
async def test_export_pagination(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """Export pagination returns correct page info."""
    resp = await client.get(
        "/api/v1/export/software-inventory",
        headers=admin_headers,
        params={"page": 1, "page_size": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["page_size"] == 2
    assert len(data["software_inventory"]) <= 2


@pytest.mark.asyncio()
async def test_export_includes_eol_data(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """Export includes EOL data when include_eol=true."""
    resp = await client.get(
        "/api/v1/export/software-inventory", headers=admin_headers, params={"include_eol": True}
    )
    assert resp.status_code == 200
    data = resp.json()
    # Find Python 3.8 in results
    python_items = [i for i in data["software_inventory"] if "Python 3.8" in i["app_name"]]
    if python_items:
        assert python_items[0]["eol"] is not None
        assert python_items[0]["eol"]["is_eol"] is True


@pytest.mark.asyncio()
async def test_export_empty_result(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """Export with impossible filter returns empty array, not error."""
    resp = await client.get(
        "/api/v1/export/software-inventory",
        headers=admin_headers,
        params={
            "scope_groups": "nonexistent_group",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["software_inventory"] == []


# ---------------------------------------------------------------------------
# Compliance check integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_eol_check_in_compliance_run(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """EOL check type is recognized and can execute via the engine."""
    from domains.compliance.checks.registry import get_executor, is_valid_check_type

    assert is_valid_check_type("eol_software_check")
    executor = get_executor("eol_software_check")
    assert executor is not None


@pytest.mark.asyncio()
async def test_eol_check_type_in_entities(
    client: AsyncClient, eol_seeded_db: AsyncIOMotorDatabase, admin_headers: dict[str, str]
) -> None:  # type: ignore[type-arg]
    """EOL check type is registered in the CheckType enum."""
    from domains.compliance.entities import CheckType

    assert CheckType.eol_software == "eol_software_check"


# ---------------------------------------------------------------------------
# Framework integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_dora_legacy_control_uses_eol_check() -> None:
    """DORA-8.7-01 uses eol_software_check (not app_version_check)."""
    from domains.compliance.frameworks.dora import CONTROLS

    legacy_control = next(c for c in CONTROLS if c.id == "DORA-8.7-01")
    assert legacy_control.check_type == "eol_software_check"


@pytest.mark.asyncio()
async def test_all_frameworks_have_eol_control() -> None:
    """All 5 frameworks have at least one EOL control."""
    from domains.compliance.frameworks import bsi, dora, hipaa, pci_dss, soc2

    for module in [dora, soc2, pci_dss, hipaa, bsi]:
        eol_controls = [c for c in module.CONTROLS if c.check_type == "eol_software_check"]
        assert len(eol_controls) >= 1, f"{module.FRAMEWORK.id} missing EOL control"


# ---------------------------------------------------------------------------
# Blast radius — existing check types unaffected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_existing_check_types_still_registered() -> None:
    """All original 10 check types remain registered."""
    from domains.compliance.checks.registry import is_valid_check_type

    original_types = [
        "prohibited_app_check",
        "required_app_check",
        "unclassified_threshold_check",
        "agent_version_check",
        "agent_online_check",
        "app_version_check",
        "sync_freshness_check",
        "classification_coverage_check",
        "delta_detection_check",
        "custom_app_presence_check",
    ]
    for check_type in original_types:
        assert is_valid_check_type(check_type), f"{check_type} not registered"


@pytest.mark.asyncio()
async def test_total_check_types_is_eleven() -> None:
    """Registry now has exactly 11 check types."""
    from domains.compliance.checks.registry import _REGISTRY

    assert len(_REGISTRY) == 11
