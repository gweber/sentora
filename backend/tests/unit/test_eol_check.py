"""Unit tests for the eol_software_check compliance check type.

Uses a real MongoDB test database per TESTING.md requirements.
The check evaluates versions per-agent at runtime using EOL product
cycle data, not pre-computed is_eol flags on app_summaries.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.checks.eol_software import execute
from domains.compliance.entities import CheckStatus
from utils.dt import utc_now


@pytest_asyncio.fixture(scope="function")
async def eol_seeded_db(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Seed test database with agents, apps, EOL products, and product mappings.

    eol_match on app_summaries stores only the product mapping.
    eol_products stores the lifecycle cycles with EOL dates.
    The compliance check evaluates versions at runtime.

    Returns:
        The seeded test database.
    """
    now = utc_now()

    agents = [
        {
            "source": "sentinelone",
            "source_id": "agent-1",
            "hostname": "host-1",
            "agent_version": "23.3.1",
            "last_active": now - timedelta(hours=1),
            "group_name": "Default",
            "tags": [],
            "installed_app_names": ["Python 3.8", "Chrome 123"],
        },
        {
            "source": "sentinelone",
            "source_id": "agent-2",
            "hostname": "host-2",
            "agent_version": "23.3.1",
            "last_active": now - timedelta(hours=2),
            "group_name": "Default",
            "tags": [],
            "installed_app_names": ["Python 3.12", "Chrome 123"],
        },
        {
            "source": "sentinelone",
            "source_id": "agent-3",
            "hostname": "host-3",
            "agent_version": "23.3.1",
            "last_active": now - timedelta(hours=1),
            "group_name": "Default",
            "tags": [],
            "installed_app_names": ["Firefox 125"],
        },
    ]
    await test_db["agents"].insert_many(agents)

    # App summaries — eol_match stores ONLY product mapping (no version fields)
    app_summaries = [
        {
            "normalized_name": "python 3.8",
            "display_name": "Python 3.8",
            "agent_count": 1,
            "category": "runtimes",
            "eol_match": {
                "eol_product_id": "python",
                "match_source": "cpe",
                "match_confidence": 0.9,
            },
        },
        {
            "normalized_name": "python 3.12",
            "display_name": "Python 3.12",
            "agent_count": 1,
            "category": "runtimes",
            "eol_match": {
                "eol_product_id": "python",
                "match_source": "cpe",
                "match_confidence": 0.9,
            },
        },
        {
            "normalized_name": "chrome 123",
            "display_name": "Chrome 123",
            "agent_count": 2,
            "category": "browsers",
            # No EOL match — not tracked
        },
        {
            "normalized_name": "firefox 125",
            "display_name": "Firefox 125",
            "agent_count": 1,
            "category": "browsers",
            "eol_match": {
                "eol_product_id": "firefox",
                "match_source": "fuzzy",
                "match_confidence": 0.5,
            },
        },
    ]
    await test_db["app_summaries"].insert_many(app_summaries)

    # EOL products with cycle data (used by compliance check at runtime)
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
                    "is_security_only": True,
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
            "product_id": "firefox",
            "name": "Mozilla Firefox",
            "last_synced": now,
            "cycles": [
                {
                    "cycle": "125",
                    "eol_date": "2024-05-01",
                    "is_eol": True,
                    "is_security_only": False,
                },
            ],
        },
    ]
    await test_db["eol_products"].insert_many(eol_products)

    # Installed apps on agents (version evaluated at runtime)
    installed_apps = [
        {
            "agent_id": "agent-1",
            "normalized_name": "python 3.8",
            "version": "3.8.19",
            "name": "Python 3.8",
        },
        {
            "agent_id": "agent-1",
            "normalized_name": "chrome 123",
            "version": "123.0.6312.86",
            "name": "Chrome 123",
        },
        {
            "agent_id": "agent-2",
            "normalized_name": "python 3.12",
            "version": "3.12.3",
            "name": "Python 3.12",
        },
        {
            "agent_id": "agent-2",
            "normalized_name": "chrome 123",
            "version": "123.0.6312.86",
            "name": "Chrome 123",
        },
        {
            "agent_id": "agent-3",
            "normalized_name": "firefox 125",
            "version": "125.0.1",
            "name": "Firefox 125",
        },
    ]
    await test_db["installed_apps"].insert_many(installed_apps)

    return test_db


@pytest.mark.asyncio()
async def test_eol_app_creates_violation(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """EOL app (Python 3.8, CPE match) creates a violation — version evaluated at runtime."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-1",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        scope_filter={},
    )
    assert result.status == CheckStatus.failed
    assert result.non_compliant_endpoints >= 1
    eol_violations = [v for v in result.violations if "Python 3.8" in v.violation_detail]
    assert len(eol_violations) >= 1
    assert "End-of-Life" in eol_violations[0].violation_detail


@pytest.mark.asyncio()
async def test_security_only_flagged_when_enabled(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Security-only apps flagged when flag_security_only=True (version evaluated per-agent)."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-2",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        scope_filter={},
    )
    all_details = " ".join(v.violation_detail for v in result.violations)
    assert "Python 3.8" in all_details  # EOL
    assert "Python 3.12" in all_details  # Security-only


@pytest.mark.asyncio()
async def test_security_only_not_flagged_when_disabled(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Security-only apps skipped when flag_security_only=False."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-3",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        scope_filter={},
    )
    all_details = " ".join(v.violation_detail for v in result.violations)
    assert "Python 3.8" in all_details
    assert "Python 3.12" not in all_details


@pytest.mark.asyncio()
async def test_fuzzy_match_excluded(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Fuzzy matches excluded from compliance results (only cpe+manual)."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-4",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        scope_filter={},
    )
    all_details = " ".join(v.violation_detail for v in result.violations)
    assert "Firefox" not in all_details


@pytest.mark.asyncio()
async def test_no_eol_match_skipped(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Apps without EOL product mappings do not generate violations."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-5",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        scope_filter={},
    )
    all_details = " ".join(v.violation_detail for v in result.violations)
    assert "Chrome" not in all_details


@pytest.mark.asyncio()
async def test_no_agents_returns_not_applicable(
    test_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Empty scope returns not_applicable status."""
    result = await execute(
        test_db,
        control_id="TEST-EOL-6",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={},
        scope_filter={},
    )
    assert result.status == CheckStatus.not_applicable
    assert result.total_endpoints == 0


@pytest.mark.asyncio()
async def test_exclude_products_parameter(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Excluded products are not checked."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-7",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={
            "flag_security_only": True,
            "min_match_confidence": 0.8,
            "exclude_products": ["python"],
        },
        scope_filter={},
    )
    all_details = " ".join(v.violation_detail for v in result.violations)
    assert "Python" not in all_details


@pytest.mark.asyncio()
async def test_no_eol_apps_passes(
    test_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Fleet with no EOL software passes the check."""
    now = utc_now()
    await test_db["agents"].insert_one(
        {
            "source": "sentinelone",
            "source_id": "clean-agent",
            "hostname": "clean-host",
            "agent_version": "23.3.1",
            "last_active": now,
            "group_name": "Default",
            "tags": [],
        }
    )
    await test_db["app_summaries"].insert_one(
        {
            "normalized_name": "safe app",
            "display_name": "Safe App",
            "agent_count": 1,
            "category": "approved",
        }
    )

    result = await execute(
        test_db,
        control_id="TEST-EOL-8",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        scope_filter={},
    )
    assert result.status == CheckStatus.passed
    assert result.violations == []


@pytest.mark.asyncio()
async def test_violation_includes_remediation(
    eol_seeded_db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Violations include remediation text with endoflife.date link."""
    result = await execute(
        eol_seeded_db,
        control_id="TEST-EOL-9",
        framework_id="test",
        control_name="EOL Check",
        category="Test",
        severity="high",
        parameters={"flag_security_only": False, "min_match_confidence": 0.8},
        scope_filter={},
    )
    eol_violations = [v for v in result.violations if "Python 3.8" in v.violation_detail]
    assert len(eol_violations) >= 1
    assert "endoflife.date/python" in eol_violations[0].remediation
