"""Pre-computed dashboard stats.

Expensive aggregations (especially on s1_installed_apps) run once after each
sync completes and are stored in the ``dashboard_stats`` collection.  Router
endpoints do a fast find_one instead of a live aggregation.

On first load (no cached data yet) the router calls ``refresh_all()`` on
demand so the dashboard is never blank.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, cast

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now


async def compute_fleet(db: AsyncIOMotorDatabase) -> dict[str, Any]:  # type: ignore[type-arg]
    now = utc_now()
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    cutoff_14d = (now - timedelta(days=14)).isoformat()
    cutoff_30d = (now - timedelta(days=30)).isoformat()

    gather_result = await asyncio.gather(
        db["s1_agents"].count_documents({}),
        db["s1_groups"].count_documents({}),
        db["s1_sites"].count_documents({}),
        db["s1_agents"]
        .aggregate(
            [
                {"$group": {"_id": "$network_status", "count": {"$sum": 1}}},
            ]
        )
        .to_list(None),
        db["s1_agents"]
        .aggregate(
            [
                {"$group": {"_id": "$os_type", "count": {"$sum": 1}}},
            ]
        )
        .to_list(None),
        db["s1_agents"]
        .aggregate(
            [
                {"$group": {"_id": "$machine_type", "count": {"$sum": 1}}},
            ]
        )
        .to_list(None),
        db["s1_agents"].count_documents({"last_active": {"$lt": cutoff_7d}}),
        db["s1_agents"].count_documents({"last_active": {"$lt": cutoff_14d}}),
        db["s1_agents"].count_documents({"last_active": {"$lt": cutoff_30d}}),
    )
    total_agents = gather_result[0]
    total_groups = gather_result[1]
    total_sites = gather_result[2]
    network_status_docs = cast(list[dict[str, Any]], gather_result[3])
    os_docs = cast(list[dict[str, Any]], gather_result[4])
    machine_type_docs = cast(list[dict[str, Any]], gather_result[5])
    stale_7d = gather_result[6]
    stale_14d = gather_result[7]
    stale_30d = gather_result[8]

    return {
        "total_agents": total_agents,
        "total_groups": total_groups,
        "total_sites": total_sites,
        "network_status": {d["_id"]: d["count"] for d in network_status_docs if d["_id"]},
        "os_distribution": {d["_id"]: d["count"] for d in os_docs if d["_id"]},
        "machine_type": {d["_id"]: d["count"] for d in machine_type_docs if d["_id"]},
        "stale_7d": stale_7d,
        "stale_14d": stale_14d,
        "stale_30d": stale_30d,
    }


async def compute_apps(db: AsyncIOMotorDatabase) -> dict[str, Any]:  # type: ignore[type-arg]
    from domains.sync.app_filters import active_filter

    # $facet branches after the expensive dedup pass — single scan of s1_installed_apps.
    # allowDiskUse=True prevents hitting MongoDB's 100 MB in-memory aggregation limit.
    total_agents, apps_facet, publisher_agg, risk_agg = await asyncio.gather(
        db["s1_agents"].count_documents({}),
        db["s1_installed_apps"]
        .aggregate(
            [
                {"$match": active_filter(normalized_name={"$ne": None}, agent_id={"$ne": None})},
                {"$group": {"_id": {"n": "$normalized_name", "a": "$agent_id"}}},
                {"$group": {"_id": "$_id.n", "agent_count": {"$sum": 1}}},
                {
                    "$facet": {
                        "summary": [
                            {
                                "$group": {
                                    "_id": None,
                                    "distinct_apps": {"$sum": 1},
                                    "unique_apps": {
                                        "$sum": {"$cond": [{"$eq": ["$agent_count", 1]}, 1, 0]}
                                    },
                                    "total_records": {"$sum": "$agent_count"},
                                }
                            },
                        ],
                        "top_apps": [
                            {"$sort": {"agent_count": -1}},
                            {"$limit": 10},
                        ],
                    }
                },
            ],
            allowDiskUse=True,
        )
        .to_list(1),
        db["s1_installed_apps"]
        .aggregate(
            [
                {"$match": active_filter(publisher={"$nin": [None, ""]})},
                {"$group": {"_id": "$publisher", "app_count": {"$addToSet": "$normalized_name"}}},
                {"$project": {"app_count": {"$size": "$app_count"}}},
                {"$sort": {"app_count": -1}},
                {"$limit": 10},
            ],
            allowDiskUse=True,
        )
        .to_list(None),
        db["s1_installed_apps"]
        .aggregate(
            [
                {"$match": active_filter(risk_level={"$nin": [None, ""]})},
                {"$group": {"_id": "$risk_level", "count": {"$sum": 1}}},
            ]
        )
        .to_list(None),
    )

    facet = apps_facet[0] if apps_facet else {}
    summary = (facet.get("summary") or [{}])[0]
    top_apps_docs = facet.get("top_apps") or []

    distinct_apps = summary.get("distinct_apps", 0)
    unique_apps = summary.get("unique_apps", 0)
    total_records = summary.get("total_records", 0)
    avg_apps_per_agent = round(total_records / total_agents, 1) if total_agents else 0

    return {
        "distinct_apps": distinct_apps,
        "avg_apps_per_agent": avg_apps_per_agent,
        "unique_apps": unique_apps,
        "top_apps": [
            {
                "normalized_name": d["_id"],
                "display_name": d["_id"].replace("-", " ").replace("_", " ").title(),
                "agent_count": d["agent_count"],
                "coverage": round(d["agent_count"] / total_agents, 4) if total_agents else 0,
            }
            for d in top_apps_docs
        ],
        "top_publishers": [
            {"publisher": d["_id"], "app_count": d["app_count"]} for d in publisher_agg
        ],
        "risk_distribution": {d["_id"]: d["count"] for d in risk_agg if d["_id"]},
    }


async def compute_fingerprinting(db: AsyncIOMotorDatabase) -> dict[str, Any]:  # type: ignore[type-arg]
    total_groups, fp_agg, pending_proposals = await asyncio.gather(
        db["s1_groups"].count_documents({}),
        db["fingerprints"]
        .aggregate(
            [
                {"$project": {"marker_count": {"$size": "$markers"}}},
            ]
        )
        .to_list(None),
        db["auto_fingerprint_proposals"].count_documents({"status": "pending"}),
    )

    groups_with_fingerprint = len(fp_agg)
    thin_fingerprints = sum(1 for d in fp_agg if d["marker_count"] < 3)
    avg_markers = round(sum(d["marker_count"] for d in fp_agg) / len(fp_agg), 1) if fp_agg else 0

    return {
        "total_groups": total_groups,
        "groups_with_fingerprint": groups_with_fingerprint,
        "groups_without_fingerprint": max(0, total_groups - groups_with_fingerprint),
        "thin_fingerprints": thin_fingerprints,
        "avg_markers_per_fingerprint": avg_markers,
        "pending_proposals": pending_proposals,
    }


async def refresh_all(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Recompute all three sections and upsert into dashboard_stats."""
    logger.info("Dashboard cache refresh started")
    try:
        fleet_data, apps_data, fp_data = await asyncio.gather(
            compute_fleet(db),
            compute_apps(db),
            compute_fingerprinting(db),
        )
        now = utc_now().isoformat()
        await asyncio.gather(
            db["dashboard_stats"].replace_one(
                {"_id": "fleet"},
                {"_id": "fleet", "data": fleet_data, "computed_at": now},
                upsert=True,
            ),
            db["dashboard_stats"].replace_one(
                {"_id": "apps"},
                {"_id": "apps", "data": apps_data, "computed_at": now},
                upsert=True,
            ),
            db["dashboard_stats"].replace_one(
                {"_id": "fingerprinting"},
                {"_id": "fingerprinting", "data": fp_data, "computed_at": now},
                upsert=True,
            ),
        )
        logger.info("Dashboard cache refreshed successfully")
    except Exception as exc:
        logger.warning("Dashboard cache refresh failed: {}", exc)
        raise
