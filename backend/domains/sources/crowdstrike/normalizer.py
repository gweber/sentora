"""Normalise CrowdStrike Falcon API data to the canonical Sentora schema.

Every normalisation function produces a document conforming to the canonical
data model.  All documents include ``source`` and ``source_id`` for multi-EDR
support.
"""

from __future__ import annotations

from typing import Any

from domains.sources.identity import canonical_id
from domains.sync.normalizer import normalize_app_name

_SOURCE = "crowdstrike"


def normalize_host(
    cs_host: dict[str, Any],
    group_name_map: dict[str, str],
) -> dict[str, Any]:
    """Map a CrowdStrike host object to the canonical ``agents`` collection schema.

    Args:
        cs_host: Raw host detail from the CrowdStrike Hosts API.
        group_name_map: Mapping of CS group_id → group_name for denormalization.

    Returns:
        Canonical agent document with ``source``, ``source_id``, and normalised
        ``agent_status`` / ``os_type``.
    """
    device_id = cs_host.get("device_id", "")

    # Collect IP addresses
    ip_addresses: list[str] = []
    local_ip = cs_host.get("local_ip", "")
    if local_ip:
        ip_addresses.append(local_ip)
    external_ip = cs_host.get("external_ip", "")
    if external_ip and external_ip != local_ip:
        ip_addresses.append(external_ip)

    # Collect MAC addresses
    mac_addresses: list[str] = []
    mac = cs_host.get("mac_address", "")
    if mac:
        mac_addresses.append(mac)

    # Resolve group names
    raw_groups = cs_host.get("groups", []) or []
    group_names: list[str] = [group_name_map.get(gid, gid) for gid in raw_groups]

    # Tags (sensor grouping tags)
    tags = cs_host.get("tags", []) or []

    # Determine primary group (first in list)
    first_group_id = raw_groups[0] if raw_groups else ""
    first_group_name = group_name_map.get(first_group_id, "") if first_group_id else ""

    return {
        "_id": canonical_id(_SOURCE, f"agent:{device_id}"),
        "source": _SOURCE,
        "source_id": device_id,
        "hostname": cs_host.get("hostname", device_id),
        "os_type": _normalize_os_type(cs_host.get("platform_name", "")),
        "os_version": cs_host.get("os_version", ""),
        "group_id": first_group_id,
        "group_name": first_group_name,
        "site_id": "",  # CrowdStrike does not have S1-style sites
        "site_name": cs_host.get("site_name") or "",
        "agent_status": _normalize_status(cs_host.get("status", "")),
        "agent_version": cs_host.get("agent_version", ""),
        "last_active": cs_host.get("last_seen") or cs_host.get("modified_timestamp") or "",
        "first_seen": cs_host.get("first_seen_timestamp") or "",
        "machine_type": _normalize_machine_type(cs_host.get("product_type_desc", "")),
        "domain": cs_host.get("machine_domain") or None,
        "ip_addresses": ip_addresses,
        "mac_addresses": mac_addresses,
        "groups": group_names,
        "tags": tags if isinstance(tags, list) else [],
        "source_metadata": {
            "ou": cs_host.get("ou") or None,
            "system_manufacturer": cs_host.get("system_manufacturer") or None,
            "system_product_name": cs_host.get("system_product_name") or None,
            "platform_id": cs_host.get("platform_id") or None,
            "provision_status": cs_host.get("provision_status") or None,
            "external_ip": external_ip or None,
        },
    }


def _normalize_os_type(cs_platform: str) -> str:
    """Normalise CrowdStrike ``platform_name`` to canonical ``os_type``.

    CrowdStrike uses title-case: ``"Windows"``, ``"Linux"``, ``"Mac"``.

    Args:
        cs_platform: Raw platform_name from the CrowdStrike API.

    Returns:
        Canonical os_type: ``"windows"``, ``"linux"``, ``"macos"``, or lowercased input.
    """
    mapping = {"windows": "windows", "linux": "linux", "mac": "macos"}
    return mapping.get(cs_platform.lower(), cs_platform.lower() or "unknown")


def _normalize_status(cs_status: str) -> str:
    """Normalise CrowdStrike ``status`` to canonical ``agent_status``.

    CrowdStrike uses: ``"normal"``, ``"contained"``,
    ``"containment_pending"``, ``"lift_containment_pending"``.

    Args:
        cs_status: Raw status from the CrowdStrike API.

    Returns:
        Canonical status: ``"online"``, ``"contained"``, or ``"offline"``.
    """
    lower = cs_status.lower() if cs_status else ""
    if lower == "normal":
        return "online"
    if lower in ("contained", "containment_pending", "lift_containment_pending"):
        return "contained"
    return "offline"


def _normalize_machine_type(product_type_desc: str) -> str:
    """Normalise CrowdStrike ``product_type_desc`` to canonical ``machine_type``.

    Args:
        product_type_desc: Raw product_type_desc (e.g. ``"Workstation"``, ``"Server"``).

    Returns:
        Canonical machine_type: ``"desktop"``, ``"server"``, or ``"unknown"``.
    """
    lower = product_type_desc.lower() if product_type_desc else ""
    if "server" in lower:
        return "server"
    if "workstation" in lower or "desktop" in lower or "laptop" in lower:
        return "desktop"
    return "unknown"


def normalize_application(
    cs_app: dict[str, Any],
    synced_at: str,
) -> dict[str, Any]:
    """Map a CrowdStrike Discover application to the canonical ``installed_apps`` schema.

    Args:
        cs_app: Raw application dict from the CrowdStrike Discover API.
        synced_at: ISO timestamp of the current sync run.

    Returns:
        Canonical installed app document with ``source`` and ``source_id``.
    """
    app_id = cs_app.get("id", "")
    name = cs_app.get("name") or ""
    version = cs_app.get("version") or ""
    # CrowdStrike Discover nests host info under ``host``
    host_info = cs_app.get("host", {}) or {}
    agent_id = host_info.get("aid") or cs_app.get("aid", "")

    return {
        "_id": canonical_id(_SOURCE, f"app:{app_id}"),
        "source": _SOURCE,
        "source_id": app_id,
        "agent_id": agent_id,
        "name": name,
        "normalized_name": normalize_app_name(name, version=version),
        "version": version or None,
        "publisher": cs_app.get("vendor") or None,
        "size": None,  # CrowdStrike Discover does not report app size
        "installed_at": cs_app.get("installation_timestamp") or None,
        "os_type": _normalize_os_type(host_info.get("platform_name", "")),
        "app_type": cs_app.get("category") or None,
        "risk_level": None,  # Not provided by Discover
        "source_updated_at": cs_app.get("last_updated_timestamp") or None,
        "source_created_at": cs_app.get("installation_timestamp") or None,
        "synced_at": synced_at,
        "last_synced_at": synced_at,
        "active": True,
    }


def normalize_group(cs_group: dict[str, Any]) -> dict[str, Any]:
    """Map a CrowdStrike host group to the canonical ``groups`` collection schema.

    Args:
        cs_group: Raw host group dict from the CrowdStrike Host Groups API.

    Returns:
        Canonical group document with ``source`` and ``source_id``.
    """
    gid = cs_group.get("id", "")
    return {
        "_id": canonical_id(_SOURCE, f"group:{gid}"),
        "source": _SOURCE,
        "source_id": gid,
        "name": cs_group.get("name", ""),
        "description": cs_group.get("description") or None,
        "type": cs_group.get("group_type", ""),
        "is_default": False,  # CrowdStrike doesn't have a default group concept
        "filter_name": cs_group.get("assignment_rule") or None,
        "agent_count": 0,  # Not directly available from the groups API
        "site_id": "",  # CrowdStrike doesn't have sites
        "site_name": "",
        "created_at": cs_group.get("created_timestamp") or None,
        "updated_at": cs_group.get("modified_timestamp") or None,
    }
