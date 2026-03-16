"""Demo data seeder — populates the database with realistic sample data.

Creates fake sites, groups, agents, installed apps, fingerprints, and
classification results so the UI can be demonstrated without a live
SentinelOne connection.

This module is idempotent: if demo data already exists (checked via
a marker document), the seed is skipped.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now

_DEMO_MARKER = {"_id": "demo_seed", "seeded": True}


async def is_demo_seeded(db: AsyncIOMotorDatabase) -> bool:  # type: ignore[type-arg]
    """Check whether demo data has already been seeded."""
    return bool(await db["_meta"].find_one({"_id": "demo_seed"}))


async def seed_demo_data(db: AsyncIOMotorDatabase) -> dict[str, Any]:  # type: ignore[type-arg]
    """Populate the database with realistic demo data.

    Returns:
        Dict with counts of created documents by collection.
    """
    if await is_demo_seeded(db):
        logger.info("Demo data already seeded — skipping")
        return {"status": "already_seeded"}

    now = utc_now().isoformat()
    counts: dict[str, int] = {}

    # ── Sites ────────────────────────────────────────────────────────────────
    sites = [
        {
            "s1_site_id": "site-hq",
            "name": "HQ — San Francisco",
            "account_id": "acct-1",
            "account_name": "Acme Corp",
            "state": "active",
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_site_id": "site-eu",
            "name": "EU — Frankfurt",
            "account_id": "acct-1",
            "account_name": "Acme Corp",
            "state": "active",
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_site_id": "site-asia",
            "name": "APAC — Singapore",
            "account_id": "acct-1",
            "account_name": "Acme Corp",
            "state": "active",
            "created_at": now,
            "_demo": True,
        },
    ]
    await db["s1_sites"].insert_many(sites)
    counts["sites"] = len(sites)

    # ── Groups ───────────────────────────────────────────────────────────────
    groups = [
        {
            "s1_group_id": "grp-eng",
            "name": "Engineering",
            "site_id": "site-hq",
            "site_name": "HQ — San Francisco",
            "agent_count": 45,
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_group_id": "grp-finance",
            "name": "Finance",
            "site_id": "site-hq",
            "site_name": "HQ — San Francisco",
            "agent_count": 22,
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_group_id": "grp-scada",
            "name": "SCADA / OT",
            "site_id": "site-eu",
            "site_name": "EU — Frankfurt",
            "agent_count": 18,
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_group_id": "grp-lab",
            "name": "QA Lab",
            "site_id": "site-eu",
            "site_name": "EU — Frankfurt",
            "agent_count": 12,
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_group_id": "grp-sales",
            "name": "Sales",
            "site_id": "site-asia",
            "site_name": "APAC — Singapore",
            "agent_count": 30,
            "created_at": now,
            "_demo": True,
        },
        {
            "s1_group_id": "grp-exec",
            "name": "Executive",
            "site_id": "site-hq",
            "site_name": "HQ — San Francisco",
            "agent_count": 8,
            "created_at": now,
            "_demo": True,
        },
    ]
    await db["s1_groups"].insert_many(groups)
    counts["groups"] = len(groups)

    # ── Agents ───────────────────────────────────────────────────────────────
    agents: list[dict[str, Any]] = []
    agent_app_map: dict[str, list[str]] = {}

    # Engineering agents
    eng_apps_base = [
        "visual_studio_code",
        "docker_desktop",
        "git",
        "nodejs",
        "python3",
        "postman",
        "slack",
        "google_chrome",
        "microsoft_teams",
    ]
    for i in range(1, 46):
        aid = f"agent-eng-{i:03d}"
        agents.append(
            {
                "s1_agent_id": aid,
                "hostname": f"eng-ws-{i:03d}",
                "os_type": "windows",
                "os_name": "Windows 11 Pro",
                "domain": "acme.local",
                "group_id": "grp-eng",
                "group_name": "Engineering",
                "site_id": "site-hq",
                "site_name": "HQ — San Francisco",
                "account_id": "acct-1",
                "account_name": "Acme Corp",
                "agent_version": "23.4.2.15",
                "is_active": True,
                "last_active_date": now,
                "created_at": now,
                "network_status": "connected",
                "machine_type": "desktop",
                "_demo": True,
            }
        )
        apps = list(eng_apps_base)
        if i <= 20:
            apps.extend(["intellij_idea", "java_jdk"])
        if i <= 10:
            apps.append("kubernetes_cli")
        agent_app_map[aid] = apps

    # Finance agents
    fin_apps = [
        "microsoft_excel",
        "microsoft_word",
        "microsoft_outlook",
        "sap_gui",
        "bloomberg_terminal",
        "adobe_acrobat_reader",
        "google_chrome",
        "microsoft_teams",
    ]
    for i in range(1, 23):
        aid = f"agent-fin-{i:03d}"
        agents.append(
            {
                "s1_agent_id": aid,
                "hostname": f"fin-ws-{i:03d}",
                "os_type": "windows",
                "os_name": "Windows 11 Enterprise",
                "domain": "acme.local",
                "group_id": "grp-finance",
                "group_name": "Finance",
                "site_id": "site-hq",
                "site_name": "HQ — San Francisco",
                "account_id": "acct-1",
                "account_name": "Acme Corp",
                "agent_version": "23.4.2.15",
                "is_active": True,
                "last_active_date": now,
                "created_at": now,
                "network_status": "connected",
                "machine_type": "desktop",
                "_demo": True,
            }
        )
        apps = list(fin_apps)
        if i <= 5:
            apps.append("quickbooks")
        agent_app_map[aid] = apps

    # SCADA agents
    scada_apps = [
        "siemens_step7",
        "rockwell_rslogix",
        "wonderware_intouch",
        "wireshark",
        "microsoft_edge",
    ]
    for i in range(1, 19):
        aid = f"agent-scada-{i:03d}"
        agents.append(
            {
                "s1_agent_id": aid,
                "hostname": f"scada-hmi-{i:03d}",
                "os_type": "windows",
                "os_name": "Windows 10 LTSC",
                "domain": "ot.acme.local",
                "group_id": "grp-scada",
                "group_name": "SCADA / OT",
                "site_id": "site-eu",
                "site_name": "EU — Frankfurt",
                "account_id": "acct-1",
                "account_name": "Acme Corp",
                "agent_version": "23.4.1.8",
                "is_active": True,
                "last_active_date": now,
                "created_at": now,
                "network_status": "connected",
                "machine_type": "desktop",
                "_demo": True,
            }
        )
        agent_app_map[aid] = list(scada_apps)

    # Lab agents
    lab_apps = [
        "selenium_webdriver",
        "jmeter",
        "postman",
        "visual_studio_code",
        "python3",
        "docker_desktop",
        "google_chrome",
    ]
    for i in range(1, 13):
        aid = f"agent-lab-{i:03d}"
        agents.append(
            {
                "s1_agent_id": aid,
                "hostname": f"qa-vm-{i:03d}",
                "os_type": "linux",
                "os_name": "Ubuntu 22.04 LTS",
                "domain": "",
                "group_id": "grp-lab",
                "group_name": "QA Lab",
                "site_id": "site-eu",
                "site_name": "EU — Frankfurt",
                "account_id": "acct-1",
                "account_name": "Acme Corp",
                "agent_version": "23.4.2.15",
                "is_active": True,
                "last_active_date": now,
                "created_at": now,
                "network_status": "connected",
                "machine_type": "server",
                "_demo": True,
            }
        )
        agent_app_map[aid] = list(lab_apps)

    # Sales agents
    sales_apps = [
        "salesforce",
        "hubspot",
        "zoom",
        "slack",
        "microsoft_outlook",
        "google_chrome",
        "microsoft_teams",
        "adobe_acrobat_reader",
    ]
    for i in range(1, 31):
        aid = f"agent-sales-{i:03d}"
        agents.append(
            {
                "s1_agent_id": aid,
                "hostname": f"sales-nb-{i:03d}",
                "os_type": "macos",
                "os_name": "macOS Sonoma 14.4",
                "domain": "",
                "group_id": "grp-sales",
                "group_name": "Sales",
                "site_id": "site-asia",
                "site_name": "APAC — Singapore",
                "account_id": "acct-1",
                "account_name": "Acme Corp",
                "agent_version": "23.4.2.15",
                "is_active": True,
                "last_active_date": now,
                "created_at": now,
                "network_status": "connected",
                "machine_type": "laptop",
                "_demo": True,
            }
        )
        agent_app_map[aid] = list(sales_apps)

    # Executive agents
    exec_apps = [
        "microsoft_outlook",
        "microsoft_teams",
        "zoom",
        "slack",
        "adobe_acrobat_reader",
        "1password",
        "google_chrome",
    ]
    for i in range(1, 9):
        aid = f"agent-exec-{i:03d}"
        agents.append(
            {
                "s1_agent_id": aid,
                "hostname": f"exec-mb-{i:03d}",
                "os_type": "macos",
                "os_name": "macOS Sonoma 14.4",
                "domain": "",
                "group_id": "grp-exec",
                "group_name": "Executive",
                "site_id": "site-hq",
                "site_name": "HQ — San Francisco",
                "account_id": "acct-1",
                "account_name": "Acme Corp",
                "agent_version": "23.4.2.15",
                "is_active": True,
                "last_active_date": now,
                "created_at": now,
                "network_status": "connected",
                "machine_type": "laptop",
                "_demo": True,
            }
        )
        agent_app_map[aid] = list(exec_apps)

    await db["s1_agents"].insert_many(agents)
    counts["agents"] = len(agents)

    # ── Installed Apps ───────────────────────────────────────────────────────
    app_display = {
        "visual_studio_code": ("Visual Studio Code", "Microsoft"),
        "docker_desktop": ("Docker Desktop", "Docker Inc"),
        "git": ("Git", "Software Freedom Conservancy"),
        "nodejs": ("Node.js", "OpenJS Foundation"),
        "python3": ("Python 3.12", "Python Software Foundation"),
        "postman": ("Postman", "Postman Inc"),
        "slack": ("Slack", "Salesforce"),
        "google_chrome": ("Google Chrome", "Google LLC"),
        "microsoft_teams": ("Microsoft Teams", "Microsoft"),
        "intellij_idea": ("IntelliJ IDEA", "JetBrains"),
        "java_jdk": ("Java JDK 21", "Oracle"),
        "kubernetes_cli": ("kubectl", "CNCF"),
        "microsoft_excel": ("Microsoft Excel", "Microsoft"),
        "microsoft_word": ("Microsoft Word", "Microsoft"),
        "microsoft_outlook": ("Microsoft Outlook", "Microsoft"),
        "sap_gui": ("SAP GUI for Windows", "SAP SE"),
        "bloomberg_terminal": ("Bloomberg Terminal", "Bloomberg LP"),
        "adobe_acrobat_reader": ("Adobe Acrobat Reader", "Adobe Inc"),
        "quickbooks": ("QuickBooks Desktop", "Intuit"),
        "siemens_step7": ("SIMATIC STEP 7", "Siemens AG"),
        "rockwell_rslogix": ("RSLogix 5000", "Rockwell Automation"),
        "wonderware_intouch": ("Wonderware InTouch", "AVEVA"),
        "wireshark": ("Wireshark", "Wireshark Foundation"),
        "microsoft_edge": ("Microsoft Edge", "Microsoft"),
        "selenium_webdriver": ("Selenium WebDriver", "Selenium Project"),
        "jmeter": ("Apache JMeter", "Apache Software Foundation"),
        "salesforce": ("Salesforce", "Salesforce Inc"),
        "hubspot": ("HubSpot", "HubSpot Inc"),
        "zoom": ("Zoom", "Zoom Video Communications"),
        "1password": ("1Password", "AgileBits Inc"),
    }

    installed_apps = []
    for agent_id, app_keys in agent_app_map.items():
        for app_key in app_keys:
            display, publisher = app_display.get(app_key, (app_key, "Unknown"))
            installed_apps.append(
                {
                    "agent_id": agent_id,
                    "normalized_name": app_key,
                    "name": display,
                    "publisher": publisher,
                    "version": "1.0.0",
                    "size": 0,
                    "installed_date": now,
                    "_demo": True,
                }
            )

    if installed_apps:
        await db["s1_installed_apps"].insert_many(installed_apps)
    counts["installed_apps"] = len(installed_apps)

    # ── Fingerprints ─────────────────────────────────────────────────────────
    fingerprints = [
        {
            "group_id": "grp-eng",
            "group_name": "Engineering",
            "site_name": "HQ — San Francisco",
            "account_name": "Acme Corp",
            "markers": [
                {
                    "id": "m1",
                    "pattern": "visual_studio_code",
                    "display_name": "Visual Studio Code",
                    "category": "name_pattern",
                    "weight": 1.2,
                    "source": "manual",
                    "confidence": 0.95,
                    "added_at": now,
                    "added_by": "admin",
                },
                {
                    "id": "m2",
                    "pattern": "docker_desktop",
                    "display_name": "Docker Desktop",
                    "category": "name_pattern",
                    "weight": 1.5,
                    "source": "statistical",
                    "confidence": 0.88,
                    "added_at": now,
                    "added_by": "system",
                },
                {
                    "id": "m3",
                    "pattern": "git",
                    "display_name": "Git",
                    "category": "name_pattern",
                    "weight": 0.8,
                    "source": "manual",
                    "confidence": 0.72,
                    "added_at": now,
                    "added_by": "admin",
                },
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "admin",
            "_demo": True,
        },
        {
            "group_id": "grp-finance",
            "group_name": "Finance",
            "site_name": "HQ — San Francisco",
            "account_name": "Acme Corp",
            "markers": [
                {
                    "id": "m4",
                    "pattern": "sap_gui*",
                    "display_name": "SAP GUI",
                    "category": "name_pattern",
                    "weight": 1.8,
                    "source": "manual",
                    "confidence": 0.97,
                    "added_at": now,
                    "added_by": "admin",
                },
                {
                    "id": "m5",
                    "pattern": "bloomberg*",
                    "display_name": "Bloomberg Terminal",
                    "category": "name_pattern",
                    "weight": 1.5,
                    "source": "statistical",
                    "confidence": 0.91,
                    "added_at": now,
                    "added_by": "system",
                },
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "admin",
            "_demo": True,
        },
        {
            "group_id": "grp-scada",
            "group_name": "SCADA / OT",
            "site_name": "EU — Frankfurt",
            "account_name": "Acme Corp",
            "markers": [
                {
                    "id": "m6",
                    "pattern": "siemens*",
                    "display_name": "Siemens STEP 7",
                    "category": "name_pattern",
                    "weight": 1.8,
                    "source": "manual",
                    "confidence": 0.99,
                    "added_at": now,
                    "added_by": "admin",
                },
                {
                    "id": "m7",
                    "pattern": "rockwell*",
                    "display_name": "RSLogix 5000",
                    "category": "name_pattern",
                    "weight": 1.5,
                    "source": "manual",
                    "confidence": 0.95,
                    "added_at": now,
                    "added_by": "admin",
                },
                {
                    "id": "m8",
                    "pattern": "wonderware*",
                    "display_name": "Wonderware InTouch",
                    "category": "name_pattern",
                    "weight": 1.2,
                    "source": "statistical",
                    "confidence": 0.87,
                    "added_at": now,
                    "added_by": "system",
                },
            ],
            "created_at": now,
            "updated_at": now,
            "created_by": "admin",
            "_demo": True,
        },
    ]
    await db["fingerprints"].insert_many(fingerprints)
    counts["fingerprints"] = len(fingerprints)

    # ── Classification results ───────────────────────────────────────────────
    results = []
    for agent in agents:
        gid = agent["group_id"]
        gname = agent["group_name"]
        # Most agents classified correctly
        classification = "correct"
        score = 0.85
        if agent["s1_agent_id"].endswith("-003"):
            classification = "ambiguous"
            score = 0.55
        if agent["s1_agent_id"].endswith("-007"):
            classification = "misclassified"
            score = 0.25
        results.append(
            {
                "agent_id": agent["s1_agent_id"],
                "hostname": agent["hostname"],
                "current_group_id": gid,
                "current_group_name": gname,
                "classification": classification,
                "match_scores": [
                    {"group_id": gid, "group_name": gname, "score": score},
                ],
                "computed_at": now,
                "run_id": "demo",
                "acknowledged": False,
                "anomaly_reasons": [],
                "_demo": True,
            }
        )
    await db["classification_results"].insert_many(results)
    counts["classification_results"] = len(results)

    # ── Sync metadata ────────────────────────────────────────────────────────
    await db["s1_sync_meta"].update_one(
        {"_id": "global"},
        {
            "$set": {
                "sites_synced_at": now,
                "groups_synced_at": now,
                "agents_synced_at": now,
                "apps_synced_at": now,
                "tags_synced_at": now,
                "_demo": True,
            }
        },
        upsert=True,
    )

    # ── Mark as seeded ───────────────────────────────────────────────────────
    await db["_meta"].insert_one(_DEMO_MARKER)
    logger.info("Demo data seeded: {}", counts)
    return counts


async def clear_demo_data(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Remove all demo data by deleting documents tagged with ``_demo: True``.

    Only removes documents that were inserted by the demo seeder, leaving
    any real (synced) data intact.
    """
    if not await is_demo_seeded(db):
        logger.info("No demo data to clear — skipping")
        return
    collections = [
        "s1_sites",
        "s1_groups",
        "s1_agents",
        "s1_installed_apps",
        "fingerprints",
        "classification_results",
        "s1_sync_meta",
    ]
    for col in collections:
        result = await db[col].delete_many({"_demo": True})
        logger.debug("Cleared {} demo docs from {}", result.deleted_count, col)
    await db["_meta"].delete_one({"_id": "demo_seed"})
    logger.info("Demo data cleared")
