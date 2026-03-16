"""Compliance repository — MongoDB data access layer.

All reads and writes to compliance-related collections go through
this module.  Collections used:

- ``compliance_framework_config`` — per-tenant framework enable/disable
- ``compliance_control_config`` — per-tenant control overrides
- ``compliance_custom_controls`` — tenant-created custom controls
- ``compliance_results`` — historical check result snapshots
- ``compliance_schedule`` — schedule configuration
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.entities import (
    CheckResult,
    ComplianceSchedule,
    ControlConfiguration,
    ControlSeverity,
    CustomControlDefinition,
)
from utils.dt import utc_now

# ---------------------------------------------------------------------------
# Framework configuration
# ---------------------------------------------------------------------------


async def is_framework_enabled(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str,
) -> bool:
    """Check whether a framework is enabled for the tenant.

    Args:
        db: Motor database handle.
        framework_id: Framework identifier.

    Returns:
        True if the framework is explicitly enabled.

    Reads from the ``compliance_framework_config`` collection.
    """
    doc = await db["compliance_framework_config"].find_one(
        {"framework_id": framework_id},
        {"enabled": 1},
    )
    return doc["enabled"] if doc else False


async def set_framework_enabled(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str,
    *,
    enabled: bool,
    actor: str,
) -> None:
    """Enable or disable a framework for the tenant.

    Args:
        db: Motor database handle.
        framework_id: Framework identifier.
        enabled: Whether to enable or disable.
        actor: Username performing the action.

    Writes to the ``compliance_framework_config`` collection.
    """
    now = utc_now()
    await db["compliance_framework_config"].update_one(
        {"framework_id": framework_id},
        {
            "$set": {
                "framework_id": framework_id,
                "enabled": enabled,
                "updated_at": now,
                "updated_by": actor,
            }
        },
        upsert=True,
    )


async def get_all_framework_configs(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, bool]:
    """Return the enabled state for all configured frameworks.

    Args:
        db: Motor database handle.

    Returns:
        Dict mapping framework_id → enabled boolean.

    Reads from the ``compliance_framework_config`` collection.
    """
    result: dict[str, bool] = {}
    async for doc in db["compliance_framework_config"].find({}, {"framework_id": 1, "enabled": 1}):
        result[doc["framework_id"]] = doc["enabled"]
    return result


# ---------------------------------------------------------------------------
# Control configuration
# ---------------------------------------------------------------------------


async def get_control_config(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    control_id: str,
    framework_id: str,
) -> ControlConfiguration | None:
    """Get the tenant-specific override for a control.

    Args:
        db: Motor database handle.
        control_id: Control identifier.
        framework_id: Parent framework identifier.

    Returns:
        The configuration override, or None if no override exists.

    Reads from the ``compliance_control_config`` collection.
    """
    doc = await db["compliance_control_config"].find_one(
        {"control_id": control_id, "framework_id": framework_id}
    )
    if doc is None:
        return None
    return ControlConfiguration(
        control_id=doc["control_id"],
        framework_id=doc["framework_id"],
        enabled=doc.get("enabled", True),
        severity_override=(
            ControlSeverity(doc["severity_override"]) if doc.get("severity_override") else None
        ),
        parameters_override=doc.get("parameters_override", {}),
        scope_tags_override=doc.get("scope_tags_override"),
        scope_groups_override=doc.get("scope_groups_override"),
        updated_at=doc.get("updated_at"),
        updated_by=doc.get("updated_by"),
    )


async def get_all_control_configs(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> list[ControlConfiguration]:
    """Get all tenant-specific control overrides.

    Args:
        db: Motor database handle.
        framework_id: Optional filter by framework.

    Returns:
        List of control configurations.

    Reads from the ``compliance_control_config`` collection.
    """
    query: dict[str, Any] = {}
    if framework_id:
        query["framework_id"] = framework_id
    configs: list[ControlConfiguration] = []
    async for doc in db["compliance_control_config"].find(query):
        configs.append(
            ControlConfiguration(
                control_id=doc["control_id"],
                framework_id=doc["framework_id"],
                enabled=doc.get("enabled", True),
                severity_override=(
                    ControlSeverity(doc["severity_override"])
                    if doc.get("severity_override")
                    else None
                ),
                parameters_override=doc.get("parameters_override", {}),
                scope_tags_override=doc.get("scope_tags_override"),
                scope_groups_override=doc.get("scope_groups_override"),
                updated_at=doc.get("updated_at"),
                updated_by=doc.get("updated_by"),
            )
        )
    return configs


async def upsert_control_config(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    config: ControlConfiguration,
) -> None:
    """Create or update a control override.

    Args:
        db: Motor database handle.
        config: The control configuration to persist.

    Writes to the ``compliance_control_config`` collection.
    """
    set_fields: dict[str, Any] = {
        "control_id": config.control_id,
        "framework_id": config.framework_id,
        "enabled": config.enabled,
        "updated_at": config.updated_at,
        "updated_by": config.updated_by,
    }
    unset_fields: dict[str, str] = {}

    # For each optional override, use $set when a value is provided and
    # $unset when the value is explicitly None (to clear the override).
    if config.severity_override is not None:
        set_fields["severity_override"] = config.severity_override.value
    else:
        unset_fields["severity_override"] = ""

    if config.parameters_override:
        set_fields["parameters_override"] = config.parameters_override
    elif config.parameters_override is not None:
        # Explicitly set to empty dict — clear it
        unset_fields["parameters_override"] = ""

    if config.scope_tags_override is not None:
        set_fields["scope_tags_override"] = config.scope_tags_override
    else:
        unset_fields["scope_tags_override"] = ""

    if config.scope_groups_override is not None:
        set_fields["scope_groups_override"] = config.scope_groups_override
    else:
        unset_fields["scope_groups_override"] = ""

    update_doc: dict[str, Any] = {"$set": set_fields}
    if unset_fields:
        update_doc["$unset"] = unset_fields

    await db["compliance_control_config"].update_one(
        {"control_id": config.control_id, "framework_id": config.framework_id},
        update_doc,
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Custom controls
# ---------------------------------------------------------------------------


async def get_custom_control(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    control_id: str,
) -> CustomControlDefinition | None:
    """Get a custom control by ID.

    Args:
        db: Motor database handle.
        control_id: The custom control identifier.

    Returns:
        The custom control, or None if not found.

    Reads from the ``compliance_custom_controls`` collection.
    """
    doc = await db["compliance_custom_controls"].find_one({"control_id": control_id})
    if doc is None:
        return None
    return _doc_to_custom_control(doc)


async def list_custom_controls(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> list[CustomControlDefinition]:
    """List all custom controls, optionally filtered by framework.

    Args:
        db: Motor database handle.
        framework_id: Optional framework filter.

    Returns:
        List of custom control definitions.

    Reads from the ``compliance_custom_controls`` collection.
    """
    query: dict[str, Any] = {}
    if framework_id:
        query["framework_id"] = framework_id
    controls: list[CustomControlDefinition] = []
    async for doc in db["compliance_custom_controls"].find(query):
        controls.append(_doc_to_custom_control(doc))
    return controls


async def insert_custom_control(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    control: CustomControlDefinition,
) -> None:
    """Insert a new custom control.

    Args:
        db: Motor database handle.
        control: The custom control to insert.

    Writes to the ``compliance_custom_controls`` collection.
    """
    doc: dict[str, Any] = {
        "control_id": control.id,
        "framework_id": control.framework_id,
        "name": control.name,
        "description": control.description,
        "category": control.category,
        "severity": control.severity.value,
        "check_type": control.check_type.value,
        "parameters": control.parameters,
        "scope_tags": control.scope_tags,
        "scope_groups": control.scope_groups,
        "remediation": control.remediation,
        "created_at": control.created_at,
        "created_by": control.created_by,
    }
    await db["compliance_custom_controls"].insert_one(doc)


def _doc_to_custom_control(doc: dict[str, Any]) -> CustomControlDefinition:
    """Convert a MongoDB document to a CustomControlDefinition."""
    return CustomControlDefinition(
        id=doc["control_id"],
        framework_id=doc["framework_id"],
        name=doc["name"],
        description=doc["description"],
        category=doc["category"],
        severity=ControlSeverity(doc["severity"]),
        check_type=doc["check_type"],
        parameters=doc.get("parameters", {}),
        scope_tags=doc.get("scope_tags", []),
        scope_groups=doc.get("scope_groups", []),
        remediation=doc.get("remediation", ""),
        created_at=doc.get("created_at"),
        created_by=doc.get("created_by"),
    )


# ---------------------------------------------------------------------------
# Check results
# ---------------------------------------------------------------------------


async def store_check_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    run_id: str,
    results: list[CheckResult],
) -> None:
    """Persist a batch of check results from a compliance run.

    Args:
        db: Motor database handle.
        run_id: Unique identifier for this compliance run.
        results: List of check results to store.

    Writes to the ``compliance_results`` collection.
    """
    if not results:
        return

    docs = []
    for r in results:
        doc: dict[str, Any] = {
            "run_id": run_id,
            "control_id": r.control_id,
            "framework_id": r.framework_id,
            "control_name": r.control_name,
            "category": r.category,
            "severity": r.severity.value,
            "status": r.status.value,
            "checked_at": r.checked_at,
            "total_endpoints": r.total_endpoints,
            "compliant_endpoints": r.compliant_endpoints,
            "non_compliant_endpoints": r.non_compliant_endpoints,
            "evidence_summary": r.evidence_summary,
            "violations": [asdict(v) for v in r.violations],
        }
        docs.append(doc)

    await db["compliance_results"].insert_many(docs)


async def get_latest_results(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get the most recent check result for each control.

    Uses aggregation to find the latest result per control_id.

    Args:
        db: Motor database handle.
        framework_id: Optional framework filter.

    Returns:
        List of result documents, one per control.

    Reads from the ``compliance_results`` collection.
    """
    pipeline: list[dict[str, Any]] = []
    if framework_id:
        pipeline.append({"$match": {"framework_id": framework_id}})

    pipeline.extend(
        [
            {"$sort": {"checked_at": -1}},
            {
                "$group": {
                    "_id": "$control_id",
                    "doc": {"$first": "$$ROOT"},
                }
            },
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"framework_id": 1, "category": 1, "control_id": 1}},
        ]
    )

    results: list[dict[str, Any]] = []
    async for doc in db["compliance_results"].aggregate(pipeline):
        doc.pop("_id", None)
        results.append(doc)
    return results


async def get_control_history(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    control_id: str,
    limit: int = 90,
) -> list[dict[str, Any]]:
    """Get historical check results for a specific control.

    Args:
        db: Motor database handle.
        control_id: The control to query history for.
        limit: Maximum number of entries (default 90 for 90-day trend).

    Returns:
        List of result documents, newest first.

    Reads from the ``compliance_results`` collection.
    """
    cursor = (
        db["compliance_results"]
        .find(
            {"control_id": control_id},
            {
                "status": 1,
                "checked_at": 1,
                "total_endpoints": 1,
                "compliant_endpoints": 1,
                "non_compliant_endpoints": 1,
                "evidence_summary": 1,
            },
        )
        .sort("checked_at", -1)
        .limit(limit)
    )
    results: list[dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        results.append(doc)
    return results


async def get_all_current_violations(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework_id: str | None = None,
    severity: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Get all current violations with pagination.

    Returns violations from the latest check result for each control
    that has a ``fail`` status.

    Args:
        db: Motor database handle.
        framework_id: Optional framework filter.
        severity: Optional severity filter.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Tuple of (violation list, total count).

    Reads from the ``compliance_results`` collection.
    """
    # First get latest results with violations
    pipeline: list[dict[str, Any]] = []
    if framework_id:
        pipeline.append({"$match": {"framework_id": framework_id}})

    pipeline.extend(
        [
            {"$sort": {"checked_at": -1}},
            {"$group": {"_id": "$control_id", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$match": {"status": {"$in": ["fail", "warning"]}}},
        ]
    )

    if severity:
        pipeline.append({"$match": {"severity": severity}})

    # Unwind violations for pagination
    pipeline.extend(
        [
            {"$unwind": "$violations"},
            {
                "$project": {
                    "control_id": 1,
                    "framework_id": 1,
                    "control_name": 1,
                    "severity": 1,
                    "checked_at": 1,
                    "violation": "$violations",
                }
            },
        ]
    )

    # Count total
    count_pipeline = pipeline + [{"$count": "total"}]
    count_result = await db["compliance_results"].aggregate(count_pipeline).to_list(1)
    total = count_result[0]["total"] if count_result else 0

    # Paginate
    skip = (page - 1) * page_size
    pipeline.extend(
        [
            {"$sort": {"severity": 1, "checked_at": -1}},
            {"$skip": skip},
            {"$limit": page_size},
        ]
    )

    violations: list[dict[str, Any]] = []
    async for doc in db["compliance_results"].aggregate(pipeline):
        v = doc["violation"]
        violations.append(
            {
                "control_id": doc["control_id"],
                "framework_id": doc["framework_id"],
                "control_name": doc["control_name"],
                "severity": doc["severity"],
                "checked_at": doc["checked_at"].isoformat() if doc.get("checked_at") else "",
                "agent_id": v.get("agent_id", ""),
                "agent_hostname": v.get("agent_hostname", ""),
                "violation_detail": v.get("violation_detail", ""),
                "app_name": v.get("app_name"),
                "app_version": v.get("app_version"),
                "remediation": v.get("remediation", ""),
            }
        )

    return violations, total


# ---------------------------------------------------------------------------
# Schedule configuration
# ---------------------------------------------------------------------------


async def get_schedule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> ComplianceSchedule:
    """Get the current compliance check schedule.

    Args:
        db: Motor database handle.

    Returns:
        The schedule configuration, or defaults if not configured.

    Reads from the ``compliance_schedule`` collection.
    """
    doc = await db["compliance_schedule"].find_one({"_id": "schedule"})
    if doc is None:
        return ComplianceSchedule()
    return ComplianceSchedule(
        run_after_sync=doc.get("run_after_sync", True),
        cron_expression=doc.get("cron_expression"),
        enabled=doc.get("enabled", True),
        updated_at=doc.get("updated_at"),
        updated_by=doc.get("updated_by"),
    )


async def upsert_schedule(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    schedule: ComplianceSchedule,
) -> None:
    """Create or update the compliance check schedule.

    Args:
        db: Motor database handle.
        schedule: The schedule configuration to persist.

    Writes to the ``compliance_schedule`` collection.
    """
    await db["compliance_schedule"].update_one(
        {"_id": "schedule"},
        {
            "$set": {
                "run_after_sync": schedule.run_after_sync,
                "cron_expression": schedule.cron_expression,
                "enabled": schedule.enabled,
                "updated_at": schedule.updated_at,
                "updated_by": schedule.updated_by,
            }
        },
        upsert=True,
    )
