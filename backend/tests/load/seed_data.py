#!/usr/bin/env python3
"""Load-test seed script — populates MongoDB with realistic volumes.

Idempotent: checks collection counts before inserting, skips if already
seeded.  Uses bulk inserts for performance.

Usage:
    python tests/load/seed_data.py

Environment:
    MONGO_URI  — MongoDB connection string (default: mongodb://localhost:27017)
    MONGO_DB   — Database name             (default: sentora)
"""

from __future__ import annotations

import os
import random
import string
import time
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from pymongo import InsertOne, MongoClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "sentora")

NUM_SITES = 5
NUM_GROUPS = 50
NUM_AGENTS = 10_000
NUM_APPS = 100_000
NUM_TAXONOMY = 200
NUM_TAXONOMY_CATEGORIES = 10
NUM_FINGERPRINTS = 20
NUM_CLASSIFICATION_RESULTS = 500
NUM_AUDIT_ENTRIES = 100

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OS_TYPES = ["windows", "linux", "macos"]
OS_VERSIONS = {
    "windows": [
        "Windows 10 Enterprise 10.0.19045",
        "Windows 11 Enterprise 10.0.22631",
        "Windows Server 2019 10.0.17763",
        "Windows Server 2022 10.0.20348",
    ],
    "linux": [
        "Ubuntu 22.04.3 LTS 5.15.0",
        "Ubuntu 20.04.6 LTS 5.4.0",
        "Red Hat Enterprise Linux 9.3 5.14.0",
        "CentOS Stream 9 5.14.0",
        "SUSE Linux Enterprise Server 15 SP5 5.14.21",
    ],
    "macos": [
        "macOS 14.2.1 Sonoma",
        "macOS 13.6.3 Ventura",
        "macOS 12.7.2 Monterey",
    ],
}

NETWORK_STATUSES = ["connected", "disconnected", "connecting"]
MACHINE_TYPES = ["desktop", "laptop", "server", "kubernetes node"]

HOSTNAME_PREFIXES = [
    "WKS",
    "SRV",
    "LAP",
    "DC",
    "DB",
    "WEB",
    "APP",
    "MFG",
    "OT",
    "ENG",
    "DEV",
    "QA",
    "PRD",
    "STG",
    "HMI",
    "PLC",
    "RTU",
    "SCADA",
    "DCS",
    "IOT",
]

SITE_NAMES = [
    "North America — Austin HQ",
    "Europe — Frankfurt DC",
    "Asia-Pacific — Singapore",
    "South America — São Paulo",
    "EMEA — London Office",
]

GROUP_NAME_TEMPLATES = [
    "Engineering — {dept}",
    "Production Floor — Line {n}",
    "Corporate IT — {dept}",
    "OT Network — Zone {n}",
    "Dev/Test — {dept}",
    "DMZ — Segment {n}",
    "Remote Workers — {dept}",
]

DEPARTMENTS = [
    "Finance",
    "HR",
    "Sales",
    "Marketing",
    "R&D",
    "QA",
    "Operations",
    "Facilities",
    "Security",
    "Compliance",
    "Manufacturing",
    "Logistics",
    "Support",
    "Executive",
]

SOFTWARE_PUBLISHERS = [
    "Microsoft Corporation",
    "Google LLC",
    "Adobe Inc.",
    "Oracle Corporation",
    "Siemens AG",
    "Rockwell Automation",
    "Schneider Electric",
    "ABB Ltd.",
    "VMware Inc.",
    "Cisco Systems",
    "Palo Alto Networks",
    "CrowdStrike Inc.",
    "Autodesk Inc.",
    "SAP SE",
    "Splunk Inc.",
    "Elastic N.V.",
    "JetBrains s.r.o.",
    "Mozilla Foundation",
    "Apple Inc.",
    "Red Hat Inc.",
]

APP_NAMES = [
    "Microsoft Office 365 ProPlus",
    "Google Chrome",
    "Mozilla Firefox",
    "Adobe Acrobat Reader DC",
    "Visual Studio Code",
    "Python 3.12",
    "Node.js 20 LTS",
    "Git for Windows",
    "7-Zip",
    "Notepad++",
    "VLC Media Player",
    "Wireshark",
    "PuTTY",
    "WinSCP",
    "Siemens WinCC OA",
    "Siemens TIA Portal",
    "Siemens STEP 7",
    "Rockwell RSLogix 5000",
    "Rockwell FactoryTalk View",
    "Schneider Electric EcoStruxure",
    "ABB Ability Symphony Plus",
    "Honeywell Experion PKS",
    "Emerson DeltaV",
    "VMware Workstation Pro",
    "VMware Tools",
    "Cisco AnyConnect Secure Mobility Client",
    "Cisco Webex",
    "Palo Alto Networks GlobalProtect",
    "CrowdStrike Falcon Sensor",
    "SentinelOne Agent",
    "Symantec Endpoint Protection",
    "Microsoft SQL Server 2019",
    "Oracle Database 19c",
    "PostgreSQL 16",
    "MongoDB 7.0",
    "Redis 7.2",
    "Apache HTTP Server",
    "nginx",
    "Tomcat 10",
    "SAP GUI for Windows",
    "SAP Business Client",
    "Splunk Universal Forwarder",
    "Elastic Agent",
    "Autodesk AutoCAD 2024",
    "MATLAB R2024a",
    "TeamViewer",
    "AnyDesk",
    "Zoom Workplace",
    "Microsoft Teams",
    "Slack",
    "Docker Desktop",
    "Kubernetes CLI (kubectl)",
    ".NET Framework 4.8.1",
    ".NET 8.0 Runtime",
    "Java Runtime Environment 21",
    "OpenSSL 3.2",
    "CODESYS Development System V3",
    "Beckhoff TwinCAT 3",
    "Ignition by Inductive Automation",
    "Kepware KEPServerEX",
    "OSIsoft PI System",
    "Aveva System Platform",
    "Fortinet FortiClient",
    "Ivanti Endpoint Manager",
    "ESET Endpoint Security",
    "Trend Micro Apex One",
]

TAXONOMY_CATEGORIES = [
    ("scada_hmi", "SCADA / HMI / Process Control"),
    ("plc_dcs", "PLC / DCS / Controller Software"),
    ("engineering_tools", "Engineering & Design Tools"),
    ("databases", "Databases & Data Platforms"),
    ("security_edr", "Security / EDR / Antivirus"),
    ("remote_access", "Remote Access & VPN"),
    ("office_productivity", "Office & Productivity"),
    ("development_tools", "Development Tools & IDEs"),
    ("networking", "Networking & Communication"),
    ("operating_systems", "OS Components & Runtimes"),
]

AUDIT_DOMAINS = ["sync", "fingerprint", "classification", "taxonomy", "config", "ml"]
AUDIT_ACTIONS = [
    "sync.completed",
    "sync.failed",
    "sync.started",
    "fingerprint.created",
    "fingerprint.updated",
    "fingerprint.deleted",
    "classification.completed",
    "classification.started",
    "taxonomy.entry_created",
    "taxonomy.entry_updated",
    "config.updated",
    "ml.training_completed",
]


def _rand_ip() -> str:
    return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _rand_hostname() -> str:
    prefix = random.choice(HOSTNAME_PREFIXES)
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}-{suffix}"


def _rand_dt(days_back: int = 90) -> str:
    """ISO datetime string within the last N days."""
    dt = datetime.now(UTC) - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return dt.isoformat()


def _rand_version() -> str:
    return f"{random.randint(1, 30)}.{random.randint(0, 99)}.{random.randint(0, 9999)}"


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_sites() -> list[dict]:
    sites = []
    for i in range(NUM_SITES):
        sites.append(
            {
                "s1_site_id": str(1000 + i),
                "name": SITE_NAMES[i],
                "state": "active",
                "site_type": "Paid",
                "account_id": "900000000000000001",
                "account_name": "Sentora Corp",
            }
        )
    return sites


def generate_groups(sites: list[dict]) -> list[dict]:
    groups = []
    for i in range(NUM_GROUPS):
        site = sites[i % NUM_SITES]
        template = random.choice(GROUP_NAME_TEMPLATES)
        name = template.format(dept=random.choice(DEPARTMENTS), n=random.randint(1, 20))
        # Ensure unique names by appending index
        name = f"{name} [{i}]"
        groups.append(
            {
                "s1_group_id": str(2000 + i),
                "name": name,
                "description": f"Auto-generated load test group {i}",
                "type": random.choice(["static", "dynamic"]),
                "is_default": i == 0,
                "filter_name": None,
                "agent_count": 0,  # updated after agents are assigned
                "site_id": site["s1_site_id"],
                "site_name": site["name"],
                "created_at": _rand_dt(180),
                "updated_at": _rand_dt(30),
            }
        )
    return groups


def generate_agents(groups: list[dict]) -> list[dict]:
    agents = []
    group_agent_counts: dict[str, int] = {g["s1_group_id"]: 0 for g in groups}

    for i in range(NUM_AGENTS):
        group = random.choice(groups)
        os_type = random.choice(OS_TYPES)
        group_agent_counts[group["s1_group_id"]] += 1
        agents.append(
            {
                "s1_agent_id": str(3000000 + i),
                "hostname": _rand_hostname(),
                "os_type": os_type,
                "os_version": random.choice(OS_VERSIONS[os_type]),
                "group_id": group["s1_group_id"],
                "group_name": group["name"],
                "site_id": group["site_id"],
                "site_name": group["site_name"],
                "network_status": random.choices(NETWORK_STATUSES, weights=[85, 10, 5], k=1)[0],
                "last_active": _rand_dt(7),
                "machine_type": random.choice(MACHINE_TYPES),
                "domain": random.choice(["corp.local", "ot.local", "plant.local", None]),
                "ip_addresses": [_rand_ip() for _ in range(random.randint(1, 3))],
                "tags": random.sample(
                    ["production", "critical", "maintenance", "monitored", "legacy", "new"],
                    k=random.randint(0, 3),
                ),
            }
        )

    # Back-fill accurate agent_count on groups
    for group in groups:
        group["agent_count"] = group_agent_counts[group["s1_group_id"]]

    return agents


def generate_apps(agents: list[dict]) -> list[dict]:
    """Generate 100k installed-app records distributed across agents."""
    apps = []
    synced_at = _rand_dt(1)
    agent_ids = [a["s1_agent_id"] for a in agents]
    agent_os = {a["s1_agent_id"]: a["os_type"] for a in agents}

    # Each agent gets ~10 apps on average (100k / 10k)
    app_id_counter = 5000000
    remaining = NUM_APPS

    # First pass: give every agent at least 3 apps
    for agent_id in agent_ids:
        n = min(3, remaining)
        if n <= 0:
            break
        for _ in range(n):
            app_name = random.choice(APP_NAMES)
            version = _rand_version()
            normalized = app_name.lower().split(" - ")[0].strip()
            # Simplistic normalization for seed data
            normalized = normalized.rstrip("0123456789. ").strip()
            apps.append(
                {
                    "id": str(app_id_counter),
                    "agent_id": agent_id,
                    "name": app_name,
                    "normalized_name": normalized,
                    "version": version,
                    "publisher": random.choice(SOFTWARE_PUBLISHERS),
                    "size": random.randint(1024, 500_000_000),
                    "installed_at": _rand_dt(180),
                    "os_type": agent_os[agent_id],
                    "app_type": None,
                    "risk_level": random.choice(["none", "low", "medium", "high", None]),
                    "s1_updated_at": _rand_dt(30),
                    "s1_created_at": _rand_dt(180),
                    "synced_at": synced_at,
                    "last_synced_at": synced_at,
                    "active": True,
                }
            )
            app_id_counter += 1
            remaining -= 1

    # Second pass: distribute remaining apps randomly
    while remaining > 0:
        agent_id = random.choice(agent_ids)
        app_name = random.choice(APP_NAMES)
        version = _rand_version()
        normalized = app_name.lower().split(" - ")[0].strip()
        normalized = normalized.rstrip("0123456789. ").strip()
        apps.append(
            {
                "id": str(app_id_counter),
                "agent_id": agent_id,
                "name": app_name,
                "normalized_name": normalized,
                "version": version,
                "publisher": random.choice(SOFTWARE_PUBLISHERS),
                "size": random.randint(1024, 500_000_000),
                "installed_at": _rand_dt(180),
                "os_type": agent_os[agent_id],
                "app_type": None,
                "risk_level": random.choice(["none", "low", "medium", "high", None]),
                "s1_updated_at": _rand_dt(30),
                "s1_created_at": _rand_dt(180),
                "synced_at": synced_at,
                "last_synced_at": synced_at,
                "active": True,
            }
        )
        app_id_counter += 1
        remaining -= 1

    return apps


def generate_taxonomy() -> list[dict]:
    entries = []
    per_category = NUM_TAXONOMY // NUM_TAXONOMY_CATEGORIES

    software_templates = [
        "{vendor} {product}",
        "{vendor} {product} Suite",
        "{vendor} {product} Professional",
        "{vendor} {product} Enterprise",
    ]
    product_words = [
        "Manager",
        "Monitor",
        "Viewer",
        "Studio",
        "Platform",
        "Server",
        "Client",
        "Agent",
        "Gateway",
        "Controller",
        "Designer",
        "Runtime",
        "Explorer",
        "Analyzer",
        "Connector",
        "Bridge",
        "Engine",
        "Core",
        "Toolkit",
        "Framework",
    ]

    for cat_idx, (cat_key, cat_display) in enumerate(TAXONOMY_CATEGORIES):
        for j in range(per_category):
            vendor = random.choice(SOFTWARE_PUBLISHERS)
            product = random.choice(product_words)
            template = random.choice(software_templates)
            name = template.format(vendor=vendor.split()[0], product=product)
            # Ensure uniqueness
            name = f"{name} {cat_idx * per_category + j}"
            pattern = name.lower().replace(" ", "*")

            entries.append(
                {
                    "_id": str(ObjectId()),
                    "name": name,
                    "patterns": [f"*{pattern}*"],
                    "publisher": vendor,
                    "category": cat_key,
                    "category_display": cat_display,
                    "subcategory": None,
                    "industry": random.sample(
                        [
                            "manufacturing",
                            "energy",
                            "water_treatment",
                            "pharma",
                            "oil_gas",
                            "automotive",
                            "food_beverage",
                            "general",
                        ],
                        k=random.randint(0, 3),
                    ),
                    "description": f"Load test entry for {name}",
                    "is_universal": random.random() < 0.1,
                    "user_added": False,
                    "created_at": _rand_dt(365),
                    "updated_at": _rand_dt(30),
                }
            )
    return entries


def generate_fingerprints(groups: list[dict]) -> list[dict]:
    fingerprints = []
    selected_groups = random.sample(groups, min(NUM_FINGERPRINTS, len(groups)))

    marker_patterns = [
        "siemens*wincc*",
        "rockwell*rslogix*",
        "schneider*ecostruxure*",
        "abb*symphony*",
        "honeywell*experion*",
        "emerson*deltav*",
        "codesys*",
        "beckhoff*twincat*",
        "ignition*",
        "kepware*",
        "osisoft*pi*",
        "aveva*system*",
        "microsoft*sql*server*",
        "oracle*database*",
        "vmware*",
        "crowdstrike*falcon*",
        "sentinelone*agent*",
        "cisco*anyconnect*",
        "palo*globalprotect*",
        "splunk*forwarder*",
    ]

    for _i, group in enumerate(selected_groups):
        num_markers = random.randint(3, 8)
        markers = []
        for _m in range(num_markers):
            pattern = random.choice(marker_patterns)
            markers.append(
                {
                    "_id": str(ObjectId()),
                    "pattern": pattern,
                    "display_name": pattern.replace("*", " ").strip().title(),
                    "category": "name_pattern",
                    "weight": round(random.uniform(0.3, 2.0), 2),
                    "source": random.choice(["manual", "statistical", "seed"]),
                    "confidence": round(random.uniform(0.5, 1.0), 3),
                    "added_at": _rand_dt(60),
                    "added_by": random.choice(["system", "user"]),
                }
            )
        fingerprints.append(
            {
                "_id": str(ObjectId()),
                "group_id": group["s1_group_id"],
                "group_name": group["name"],
                "site_name": group["site_name"],
                "account_name": "Sentora Corp",
                "markers": markers,
                "created_at": _rand_dt(90),
                "updated_at": _rand_dt(14),
                "created_by": random.choice(["system", "user"]),
            }
        )
    return fingerprints


def generate_classification_results(
    agents: list[dict],
    groups: list[dict],
    fingerprints: list[dict],
) -> list[dict]:
    results = []
    run_id = str(ObjectId())
    fp_group_ids = {fp["group_id"] for fp in fingerprints}
    fp_groups = [g for g in groups if g["s1_group_id"] in fp_group_ids]

    # Classify a subset of agents
    sampled_agents = random.sample(agents, min(NUM_CLASSIFICATION_RESULTS, len(agents)))
    verdicts = ["correct", "misclassified", "ambiguous", "unclassifiable"]
    verdict_weights = [60, 15, 15, 10]

    for agent in sampled_agents:
        verdict = random.choices(verdicts, weights=verdict_weights, k=1)[0]

        # Build match scores against a few fingerprint groups
        num_scores = random.randint(1, min(5, len(fp_groups)))
        score_groups = random.sample(fp_groups, num_scores)
        match_scores = []
        for sg in score_groups:
            score = round(random.uniform(0.0, 1.0), 4)
            n_matched = random.randint(0, 5)
            n_missing = random.randint(0, 5)
            match_scores.append(
                {
                    "group_id": sg["s1_group_id"],
                    "group_name": sg["name"],
                    "score": score,
                    "matched_markers": [f"marker_{j}" for j in range(n_matched)],
                    "missing_markers": [f"marker_{j}" for j in range(n_missing)],
                }
            )
        match_scores.sort(key=lambda x: x["score"], reverse=True)

        suggested_group = None
        suggested_group_name = None
        if verdict == "misclassified" and match_scores:
            suggested_group = match_scores[0]["group_id"]
            suggested_group_name = match_scores[0]["group_name"]

        anomaly_reasons = []
        if verdict in ("misclassified", "ambiguous"):
            anomaly_reasons = random.sample(
                [
                    "Best match score below correct-threshold (0.7)",
                    "Top two groups within ambiguous-threshold (0.4)",
                    "Current group has no fingerprint",
                    "Agent has very few installed applications",
                    "Anomaly score exceeds isolation forest threshold",
                ],
                k=random.randint(1, 3),
            )

        results.append(
            {
                "_id": str(ObjectId()),
                "run_id": run_id,
                "agent_id": agent["s1_agent_id"],
                "hostname": agent["hostname"],
                "current_group_id": agent["group_id"],
                "current_group_name": agent["group_name"],
                "match_scores": match_scores,
                "classification": verdict,
                "suggested_group_id": suggested_group,
                "suggested_group_name": suggested_group_name,
                "anomaly_reasons": anomaly_reasons,
                "computed_at": _rand_dt(7),
                "acknowledged": random.random() < 0.2,
            }
        )
    return results


def generate_audit_log() -> list[dict]:
    entries = []
    for _ in range(NUM_AUDIT_ENTRIES):
        action = random.choice(AUDIT_ACTIONS)
        domain = action.split(".")[0]
        entries.append(
            {
                "timestamp": _rand_dt(30),
                "actor": random.choice(["system", "user", "scheduler"]),
                "domain": domain,
                "action": action,
                "status": random.choices(["success", "failure", "info"], weights=[80, 10, 10], k=1)[
                    0
                ],
                "summary": f"Load test audit entry: {action}",
                "details": {"seed": True, "iteration": _},
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Main — bulk insert with idempotency checks
# ---------------------------------------------------------------------------


def _bulk_insert(collection: object, docs: list[dict], label: str) -> None:
    """Insert docs in batches of 5000 using bulk_write for performance."""
    if not docs:
        return
    batch_size = 5000
    total = len(docs)
    inserted = 0
    for start in range(0, total, batch_size):
        batch = docs[start : start + batch_size]
        ops = [InsertOne(d) for d in batch]
        collection.bulk_write(ops, ordered=False)
        inserted += len(batch)
        print(f"  {label}: {inserted:,}/{total:,} inserted")


def main() -> None:
    print(f"Connecting to {MONGO_URI}, database: {MONGO_DB}")
    client: MongoClient = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    # ── Idempotency checks ────────────────────────────────────────────
    collections_targets = {
        "s1_sites": NUM_SITES,
        "s1_groups": NUM_GROUPS,
        "s1_agents": NUM_AGENTS,
        "s1_installed_apps": NUM_APPS,
        "software_taxonomy": NUM_TAXONOMY,
        "fingerprints": NUM_FINGERPRINTS,
        "classification_results": NUM_CLASSIFICATION_RESULTS,
        "audit_log": NUM_AUDIT_ENTRIES,
    }

    already_seeded = True
    for coll_name, target in collections_targets.items():
        count = db[coll_name].count_documents({})
        if count < target:
            already_seeded = False
            break

    if already_seeded:
        print("All collections already at target counts — skipping seed.")
        for coll_name, target in collections_targets.items():
            count = db[coll_name].count_documents({})
            print(f"  {coll_name}: {count:,} docs (target: {target:,})")
        return

    t0 = time.time()

    # ── Generate ──────────────────────────────────────────────────────
    print("\n[1/8] Generating sites...")
    sites = generate_sites()

    print("[2/8] Generating groups...")
    groups = generate_groups(sites)

    print("[3/8] Generating agents...")
    agents = generate_agents(groups)

    print("[4/8] Generating installed apps (this may take a moment)...")
    apps = generate_apps(agents)

    print("[5/8] Generating taxonomy entries...")
    taxonomy = generate_taxonomy()

    print("[6/8] Generating fingerprints...")
    fingerprints = generate_fingerprints(groups)

    print("[7/8] Generating classification results...")
    classification_results = generate_classification_results(agents, groups, fingerprints)

    print("[8/8] Generating audit log entries...")
    audit_entries = generate_audit_log()

    # ── Insert ────────────────────────────────────────────────────────
    print("\nInserting into MongoDB...\n")

    if db["s1_sites"].count_documents({}) < NUM_SITES:
        db["s1_sites"].delete_many({})
        _bulk_insert(db["s1_sites"], sites, "s1_sites")
    else:
        print(f"  s1_sites: already seeded ({db['s1_sites'].count_documents({}):,} docs)")

    if db["s1_groups"].count_documents({}) < NUM_GROUPS:
        db["s1_groups"].delete_many({})
        _bulk_insert(db["s1_groups"], groups, "s1_groups")
    else:
        print(f"  s1_groups: already seeded ({db['s1_groups'].count_documents({}):,} docs)")

    if db["s1_agents"].count_documents({}) < NUM_AGENTS:
        db["s1_agents"].delete_many({})
        _bulk_insert(db["s1_agents"], agents, "s1_agents")
    else:
        print(f"  s1_agents: already seeded ({db['s1_agents'].count_documents({}):,} docs)")

    if db["s1_installed_apps"].count_documents({}) < NUM_APPS:
        db["s1_installed_apps"].delete_many({})
        _bulk_insert(db["s1_installed_apps"], apps, "s1_installed_apps")
    else:
        print(
            "  s1_installed_apps: already seeded"
            f" ({db['s1_installed_apps'].count_documents({}):,} docs)"
        )

    if db["software_taxonomy"].count_documents({}) < NUM_TAXONOMY:
        db["software_taxonomy"].delete_many({})
        _bulk_insert(db["software_taxonomy"], taxonomy, "software_taxonomy")
    else:
        print(
            "  software_taxonomy: already seeded"
            f" ({db['software_taxonomy'].count_documents({}):,} docs)"
        )

    if db["fingerprints"].count_documents({}) < NUM_FINGERPRINTS:
        db["fingerprints"].delete_many({})
        _bulk_insert(db["fingerprints"], fingerprints, "fingerprints")
    else:
        print(f"  fingerprints: already seeded ({db['fingerprints'].count_documents({}):,} docs)")

    if db["classification_results"].count_documents({}) < NUM_CLASSIFICATION_RESULTS:
        db["classification_results"].delete_many({})
        _bulk_insert(db["classification_results"], classification_results, "classification_results")
    else:
        print(
            "  classification_results: already seeded"
            f" ({db['classification_results'].count_documents({}):,} docs)"
        )

    if db["audit_log"].count_documents({}) < NUM_AUDIT_ENTRIES:
        db["audit_log"].delete_many({})
        _bulk_insert(db["audit_log"], audit_entries, "audit_log")
    else:
        print(f"  audit_log: already seeded ({db['audit_log'].count_documents({}):,} docs)")

    elapsed = time.time() - t0
    print(f"\nSeed complete in {elapsed:.1f}s")

    # ── Summary ───────────────────────────────────────────────────────
    print("\nCollection counts:")
    for coll_name in collections_targets:
        count = db[coll_name].count_documents({})
        print(f"  {coll_name}: {count:,}")

    client.close()


if __name__ == "__main__":
    main()
