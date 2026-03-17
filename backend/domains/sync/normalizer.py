"""Normalise raw S1 API response documents to canonical MongoDB schemas.

All normalisation functions produce documents conforming to the canonical
data model defined in ``domains.sources``.  Every document includes
``source`` and ``source_id`` fields for multi-EDR support.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from domains.sources.identity import canonical_id

_SOURCE = "sentinelone"


def normalize_site(s1_site: dict[str, Any]) -> dict[str, Any]:
    """Map a S1 site object to the canonical ``sites`` collection schema.

    Args:
        s1_site: Raw site object from the SentinelOne API.

    Returns:
        Canonical site document with ``source`` and ``source_id``.
    """
    sid = s1_site.get("id", "")
    return {
        "_id": canonical_id(_SOURCE, f"site:{sid}"),
        "source": _SOURCE,
        "source_id": sid,
        "name": s1_site.get("name", ""),
        "state": s1_site.get("state", ""),
        "site_type": s1_site.get("siteType", ""),
        "account_id": s1_site.get("accountId", ""),
        "account_name": s1_site.get("accountName", ""),
    }


def normalize_group(
    s1_group: dict[str, Any],
    site_name_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Map a S1 group object to the canonical ``groups`` collection schema.

    Args:
        s1_group: Raw group object from the SentinelOne API.
        site_name_map: Mapping of site source_id → site name for denormalization.

    Returns:
        Canonical group document with ``source`` and ``source_id``.
    """
    gid = s1_group.get("id", "")
    site_id = s1_group.get("siteId", "")
    return {
        "_id": canonical_id(_SOURCE, f"group:{gid}"),
        "source": _SOURCE,
        "source_id": gid,
        "name": s1_group.get("name", ""),
        "description": s1_group.get("description") or None,
        "type": s1_group.get("type", ""),
        "is_default": s1_group.get("isDefault", False),
        "filter_name": s1_group.get("filterName") or None,
        "agent_count": s1_group.get("totalAgents", 0),
        "site_id": site_id,
        "site_name": (site_name_map or {}).get(site_id, ""),
        "created_at": s1_group.get("createdAt") or None,
        "updated_at": s1_group.get("updatedAt") or None,
    }


def normalize_agent(
    s1_agent: dict[str, Any],
    group_name_map: dict[str, str],
) -> dict[str, Any]:
    """Map a S1 agent object to the canonical ``agents`` collection schema.

    Args:
        s1_agent: Raw agent object from the SentinelOne API.
        group_name_map: Mapping of group source_id → group name.

    Returns:
        Canonical agent document with ``source``, ``source_id``,
        and normalised ``agent_status`` / ``os_type``.
    """
    agent_id = s1_agent.get("id", "")
    group_id = s1_agent.get("groupId", "")
    os_name = s1_agent.get("osName", "")
    os_revision = s1_agent.get("osRevision", "")
    os_version = f"{os_name} {os_revision}".strip() if os_revision else os_name

    # Extract IP addresses from networkInterfaces
    ip_addresses: list[str] = []
    for iface in s1_agent.get("networkInterfaces", []):
        inet = iface.get("inet")
        if inet:
            ip_addresses.append(inet)
        for ip in iface.get("inet6", []):
            if ip:
                ip_addresses.append(ip)

    # Extract tags — S1 returns tags as {"sentinelone": [...], ...} keyed by source
    raw_tags = s1_agent.get("tags") or {}
    tags: list[str] = []
    if isinstance(raw_tags, dict):
        for tag_list in raw_tags.values():
            if isinstance(tag_list, list):
                tags.extend(str(t) for t in tag_list if t)
    elif isinstance(raw_tags, list):
        tags = [t.get("key", "") if isinstance(t, dict) else str(t) for t in raw_tags if t]

    return {
        "_id": canonical_id(_SOURCE, f"agent:{agent_id}"),
        "source": _SOURCE,
        "source_id": agent_id,
        "hostname": s1_agent.get("computerName", agent_id),
        "os_type": (s1_agent.get("osType") or "unknown").lower(),
        "os_version": os_version,
        "group_id": group_id,
        "group_name": group_name_map.get(group_id, s1_agent.get("groupName", "")),
        "site_id": s1_agent.get("siteId", ""),
        "site_name": s1_agent.get("siteName", ""),
        "agent_status": _normalize_status(s1_agent.get("networkStatus")),
        "last_active": s1_agent.get("lastActiveDate") or s1_agent.get("updatedAt") or "",
        "machine_type": (s1_agent.get("machineType") or "unknown").lower(),
        "domain": s1_agent.get("domain"),
        "ip_addresses": ip_addresses,
        "tags": tags,
    }


def _normalize_status(network_status: str | None) -> str:
    """Normalise S1 network_status to canonical agent_status.

    Args:
        network_status: Raw S1 ``networkStatus`` value.

    Returns:
        Canonical status: ``"online"``, ``"offline"``, or ``"degraded"``.
    """
    mapping = {"connected": "online", "disconnected": "offline"}
    return mapping.get((network_status or "unknown").lower(), "offline")


def normalize_tag(s1_tag: dict[str, Any], synced_at: str) -> dict[str, Any]:
    """Map a S1 agent tag to the canonical ``source_tags`` collection schema.

    Args:
        s1_tag: Raw tag object from the SentinelOne ``/agents/tags`` endpoint.
        synced_at: ISO timestamp of the current sync run.

    Returns:
        Canonical source tag document with ``source`` and ``source_id``.
    """
    tid = str(s1_tag.get("id", ""))
    return {
        "_id": canonical_id(_SOURCE, f"tag:{tid}"),
        "source": _SOURCE,
        "source_id": tid,
        "name": s1_tag.get("key", ""),
        "value": s1_tag.get("value") or None,
        "description": s1_tag.get("description") or None,
        "type": s1_tag.get("type", ""),
        "scope": s1_tag.get("scopeLevel", ""),
        "scope_id": s1_tag.get("scopeId") or None,
        "scope_path": s1_tag.get("scopePath") or None,
        "creator": s1_tag.get("createdBy") or None,
        "total_endpoints": s1_tag.get("totalEndpoints", 0),
        "created_at": s1_tag.get("createdAt") or None,
        "updated_at": s1_tag.get("updatedAt") or None,
        "synced_at": synced_at,
    }


def normalize_app(s1_app: dict[str, Any], synced_at: str) -> dict[str, Any]:
    """Map a S1 installed-application record to the canonical ``installed_apps`` schema.

    Args:
        s1_app: Raw app object from ``/installed-applications``.
        synced_at: ISO timestamp of the current sync run.

    Returns:
        Canonical installed app document with ``source`` and ``source_id``.
    """
    app_id = s1_app.get("id", "")
    name = s1_app.get("name") or ""
    version = s1_app.get("version") or ""
    return {
        "_id": canonical_id(_SOURCE, f"app:{app_id}"),
        "source": _SOURCE,
        "source_id": app_id,
        "agent_id": s1_app.get("agentId", ""),
        "name": name,
        "normalized_name": normalize_app_name(name, version=version),
        "version": s1_app.get("version"),
        "publisher": s1_app.get("publisher"),
        "size": s1_app.get("size"),
        "installed_at": s1_app.get("installedAt"),
        "os_type": s1_app.get("osType"),
        "app_type": s1_app.get("type"),
        "risk_level": s1_app.get("riskLevel"),
        "source_updated_at": s1_app.get("updatedAt"),
        "source_created_at": s1_app.get("createdAt"),
        "synced_at": synced_at,
        "last_synced_at": synced_at,
        "active": True,
    }


def normalize_app_name(name: str, version: str = "") -> str:
    """Produce a consistent lowercase name suitable for glob pattern matching.

    Steps:
    1. NFKD-normalise to decompose accented characters.
    2. Strip combining characters (diacritics).
    3. Lowercase.
    4. Remove trademark/copyright/registered symbols.
    5. Collapse repeated whitespace.
    6. Strip version suffix.  If the S1 ``version`` field is provided it is
       used for an exact match first (most precise).  Falls back to a regex
       that strips dash-separated (" - 14.36.32543") and plain three-part
       (" 4.1.1") suffixes while preserving product years ("Studio 2019")
       and two-part numbers (".NET Framework 4.7").

    Args:
        name: Raw application display name.
        version: Application version string for precise suffix stripping.

    Returns:
        Normalised lowercase app name.
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = re.sub(r"[™®©]", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    # Prefer exact version stripping using the S1 version field.
    if version:
        norm_ver = version.strip().lower()
        for sep in (f" - {norm_ver}", f" {norm_ver}"):
            if name.endswith(sep):
                name = name[: -len(sep)].rstrip(" -(").strip()
                break
        else:
            # Regex fallback for multi-part numeric suffixes (>= X.Y.Z)
            name = re.sub(r"\s+(?:-\s*)?\d+\.\d+\.\d[\d.]*\s*$", "", name).strip()
    else:
        name = re.sub(r"\s+(?:-\s*)?\d+\.\d+\.\d[\d.]*\s*$", "", name).strip()

    return name
