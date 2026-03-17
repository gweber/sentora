"""Auto-fingerprint proposer — Lift-based cross-group marker proposals.

For each group, computes a ranked set of discriminative application
markers using the Lift statistic:

    lift = P(app | group) / P(app)

A lift of 12 means "agents in this group are 12× more likely to have
this app than any random agent in the fleet."  This is directly human-
readable and maps naturally to the "X×" badge in the UI.

Three MongoDB aggregates over the ``agents`` collection are used
(no cross-collection joins):
1. Group sizes and names.
2. Per-(group, app) agent counts.
3. Global per-app agent counts.

All scoring happens in Python after the aggregates complete.
"""

from __future__ import annotations

import re

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.fingerprint.entities import AutoFingerprintProposal, ProposedMarker
from domains.sources.collections import AGENTS
from utils.dt import utc_now

# Strips trailing version suffix like " - 14.36.32543" from app names.
# Only matches pure numeric versions after " - " to avoid stripping product
# year tokens like "Visual Studio 2019" or ".NET Framework 4.7.1".
_VERSION_SUFFIX_RE = re.compile(r"\s+(?:-\s*)?\d+\.\d+\.\d[\d.]*\s*$")

# ── Default thresholds ─────────────────────────────────────────────────────────

_COVERAGE_MIN: float = 0.60  # ≥60 % of group agents must have the app
_OUTSIDE_MAX: float = 0.25  # <25 % of non-group agents can have it
_LIFT_MIN: float = 2.0  # at least 2× more common in group than fleet-wide
_TOP_K: int = 10  # max markers proposed per group
_LIFT_CAP: float = 99.0  # cap displayed lift (prevents N/group_size artifacts)


# ── Public entry point ────────────────────────────────────────────────────────


async def generate_proposals(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    coverage_min: float = _COVERAGE_MIN,
    outside_max: float = _OUTSIDE_MAX,
    lift_min: float = _LIFT_MIN,
    top_k: int = _TOP_K,
) -> list[AutoFingerprintProposal]:
    """Compute discriminative marker proposals for every group.

    Args:
        db: Motor database handle.
        coverage_min: Minimum fraction of group agents that must have an app.
        outside_max: Maximum fraction of non-group agents that may have an app.
        lift_min: Minimum lift required for a marker to pass the quality gate.
        top_k: Maximum number of markers per group proposal.

    Returns:
        List of AutoFingerprintProposal, one per group, sorted by quality
        (mean lift) descending.
    """
    # ── Step 1: group sizes + names ───────────────────────────────────────────
    group_docs = (
        await db[AGENTS]
        .aggregate(
            [
                {
                    "$group": {
                        "_id": "$group_id",
                        "count": {"$sum": 1},
                        "group_name": {"$first": "$group_name"},
                    }
                },
            ]
        )
        .to_list(length=None)
    )

    groups: dict[str, dict] = {}
    N: int = 0
    for doc in group_docs:
        gid = doc["_id"]
        if not gid:
            continue
        groups[gid] = {"count": doc["count"], "name": doc.get("group_name") or gid}
        N += doc["count"]

    if N == 0 or not groups:
        return []

    total_groups = len(groups)

    # ── Steps 2+3: stream agents → build global_df + in_group in one pass ──
    # Each agent has ``installed_app_names`` (denormalized by sync) — a compact
    # list of distinct normalised app names. Reading 150k agent docs (~12 MB)
    # is orders of magnitude faster than aggregating 9M installed_apps docs.
    global_df: dict[str, int] = {}
    in_group: dict[str, dict[str, int]] = {}

    async for agent in db[AGENTS].find(
        {"group_id": {"$ne": None}, "installed_app_names": {"$exists": True, "$ne": []}},
        {"group_id": 1, "installed_app_names": 1, "_id": 0},
    ):
        gid = agent["group_id"]
        grp = in_group.setdefault(gid, {})
        for raw_name in agent.get("installed_app_names", []):
            name = _normalize_app_name(raw_name)
            if not name:
                continue
            global_df[name] = global_df.get(name, 0) + 1
            grp[name] = grp.get(name, 0) + 1

    # ── Steps 4–6: score, quality gate, rank ──────────────────────────────────
    # Track which groups each app ends up in (for conflict detection)
    app_to_groups: dict[str, list[str]] = {}
    group_candidates: dict[str, list[dict]] = {}

    for gid, ginfo in groups.items():
        group_size: int = ginfo["count"]
        outside_agents = N - group_size
        apps_in_group = in_group.get(gid, {})

        passing: list[dict] = []
        for app, in_count in apps_in_group.items():
            df = global_df.get(app, in_count)
            group_coverage = in_count / group_size
            base_rate = df / N
            lift = min(group_coverage / base_rate, _LIFT_CAP) if base_rate > 0 else 0.0
            outside_count = df - in_count
            outside_coverage = outside_count / outside_agents if outside_agents > 0 else 0.0

            if group_coverage < coverage_min:
                continue
            if outside_coverage > outside_max:
                continue
            if lift < lift_min:
                continue

            passing.append(
                {
                    "app": app,
                    "lift": lift,
                    "group_coverage": group_coverage,
                    "outside_coverage": outside_coverage,
                    "agent_count_in_group": in_count,
                    "agent_count_outside": outside_count,
                }
            )

        passing.sort(key=lambda x: x["lift"], reverse=True)
        top = passing[:top_k]
        group_candidates[gid] = top

        for c in top:
            app_to_groups.setdefault(c["app"], []).append(gid)

    # ── Step 7: build proposal objects with conflict info ─────────────────────
    computed_at = utc_now()
    proposals: list[AutoFingerprintProposal] = []

    for gid, ginfo in groups.items():
        candidates = group_candidates.get(gid, [])

        markers: list[ProposedMarker] = []
        for c in candidates:
            competing = [g for g in app_to_groups.get(c["app"], []) if g != gid]
            markers.append(
                ProposedMarker(
                    normalized_name=c["app"],
                    display_name=_to_display_name(c["app"]),
                    lift=round(c["lift"], 2),
                    group_coverage=round(c["group_coverage"], 4),
                    outside_coverage=round(c["outside_coverage"], 4),
                    agent_count_in_group=c["agent_count_in_group"],
                    agent_count_outside=c["agent_count_outside"],
                    shared_with_groups=competing,
                )
            )

        quality_score = sum(m.lift for m in markers) / len(markers) if markers else 0.0

        proposals.append(
            AutoFingerprintProposal(
                _id=str(ObjectId()),
                group_id=gid,
                group_name=ginfo["name"],
                group_size=ginfo["count"],
                proposed_markers=markers,
                quality_score=round(quality_score, 2),
                total_groups=total_groups,
                coverage_min=coverage_min,
                outside_max=outside_max,
                lift_min=lift_min,
                top_k=top_k,
                status="pending",
                computed_at=computed_at,
            )
        )

    proposals.sort(key=lambda p: p.quality_score, reverse=True)
    return proposals


# ── Helpers ───────────────────────────────────────────────────────────────────


def _normalize_app_name(name: str) -> str:
    """Strip trailing ` - X.Y.Z` version suffixes so all versions of an app
    aggregate together.  Only strips pure-numeric suffixes to avoid removing
    meaningful tokens like 'Visual Studio 2019' or '.NET Framework 4.7.1'.
    """
    return _VERSION_SUFFIX_RE.sub("", name).strip()


def _to_display_name(normalized_name: str) -> str:
    """Convert a normalised app name to a human-readable display name.

    Args:
        normalized_name: Lowercase, hyphen/underscore-separated name.

    Returns:
        Title-cased display name.
    """
    return normalized_name.replace("-", " ").replace("_", " ").title()
