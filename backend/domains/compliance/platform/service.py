"""Platform compliance service — evaluates Sentora's own security controls.

Provides live dashboard evaluation and point-in-time report generation
for SOC 2 Type II and ISO 27001 audits of the Sentora platform itself.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
from typing import Any

from bson import ObjectId
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.platform.controls import FRAMEWORK_CONTROLS
from domains.compliance.platform.entities import (
    ComplianceReport,
    ControlResult,
    ControlStatus,
    Framework,
)
from utils.dt import utc_now


async def evaluate_controls(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework: Framework,
) -> list[dict[str, Any]]:
    """Run all control evaluators for a framework and return results.

    Args:
        db: Motor database handle.
        framework: Which framework to evaluate.

    Returns:
        List of control result dicts.
    """
    evaluators = FRAMEWORK_CONTROLS.get(framework, [])
    results = await asyncio.gather(
        *(evaluator(db) for evaluator in evaluators),
        return_exceptions=True,
    )

    control_dicts: list[dict[str, Any]] = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("Platform compliance evaluator failed: {}", r)
            evaluator = evaluators[idx]
            error_result = ControlResult(
                control_id=getattr(evaluator, "__name__", f"unknown-{idx}"),
                framework=framework.value,
                reference="",
                title=getattr(evaluator, "__doc__", "Unknown control") or "Unknown control",
                category="",
                status=ControlStatus.failing,
                evidence_summary=f"Evaluator error: {r}",
            )
            control_dicts.append(asdict(error_result))
            continue
        control_dicts.append(asdict(r))  # type: ignore[arg-type]
    return control_dicts


def compute_score(controls: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate compliance score from control results.

    Args:
        controls: List of control result dicts.

    Returns:
        Dict with total_controls, passing, warning, failing, not_applicable, score_percent.
    """
    total = len(controls)
    passing = sum(1 for c in controls if c["status"] == ControlStatus.passing.value)
    warning = sum(1 for c in controls if c["status"] == ControlStatus.warning.value)
    failing = sum(1 for c in controls if c["status"] == ControlStatus.failing.value)
    na = sum(1 for c in controls if c["status"] == ControlStatus.not_applicable.value)

    applicable = total - na
    score = (passing / applicable * 100) if applicable > 0 else 0.0

    return {
        "total_controls": total,
        "passing": passing,
        "warning": warning,
        "failing": failing,
        "not_applicable": na,
        "score_percent": round(score, 1),
    }


async def get_dashboard(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework: Framework,
) -> dict[str, Any]:
    """Evaluate all controls and return dashboard data.

    Args:
        db: Motor database handle.
        framework: Which framework to evaluate.

    Returns:
        Dict with framework, score, and control results.
    """
    controls = await evaluate_controls(db, framework)
    score = compute_score(controls)
    return {
        "framework": framework.value,
        **score,
        "controls": controls,
    }


async def generate_report(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework: Framework,
    period_days: int,
    generated_by: str,
) -> ComplianceReport:
    """Generate a point-in-time platform compliance report and persist it.

    Args:
        db: Motor database handle.
        framework: Which framework to evaluate.
        period_days: Evidence period in days.
        generated_by: Username who triggered the report.

    Returns:
        The generated ComplianceReport.
    """
    now = utc_now()
    period_start = (now - timedelta(days=period_days)).isoformat()
    period_end = now.isoformat()

    report_id = str(ObjectId())
    report_doc: dict[str, Any] = {
        "_id": ObjectId(report_id),
        "framework": framework.value,
        "generated_at": now.isoformat(),
        "generated_by": generated_by,
        "period_start": period_start,
        "period_end": period_end,
        "status": "generating",
        "total_controls": 0,
        "passing_controls": 0,
        "warning_controls": 0,
        "failing_controls": 0,
        "controls": [],
    }
    await db["compliance_reports"].insert_one(report_doc)

    try:
        controls = await evaluate_controls(db, framework)
        score = compute_score(controls)

        for ctrl in controls:
            ctrl["period_start"] = period_start
            ctrl["period_end"] = period_end

        await db["compliance_reports"].update_one(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": "completed",
                    "total_controls": score["total_controls"],
                    "passing_controls": score["passing"],
                    "warning_controls": score["warning"],
                    "failing_controls": score["failing"],
                    "controls": controls,
                }
            },
        )

        return ComplianceReport(
            id=report_id,
            framework=framework.value,
            generated_at=now.isoformat(),
            generated_by=generated_by,
            period_start=period_start,
            period_end=period_end,
            status="completed",
            total_controls=score["total_controls"],
            passing_controls=score["passing"],
            warning_controls=score["warning"],
            failing_controls=score["failing"],
            controls=controls,
        )
    except Exception as exc:
        await db["compliance_reports"].update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"status": "failed", "error": str(exc)}},
        )
        raise


async def list_reports(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    framework: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List generated platform compliance reports (metadata only).

    Args:
        db: Motor database handle.
        framework: Optional framework filter.
        limit: Maximum number of reports.

    Returns:
        List of report metadata dicts.
    """
    query: dict[str, Any] = {}
    if framework:
        query["framework"] = framework
    cursor = (
        db["compliance_reports"].find(query, {"controls": 0}).sort("generated_at", -1).limit(limit)
    )
    reports: list[dict[str, Any]] = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        reports.append(doc)
    return reports


async def get_report(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    report_id: str,
) -> dict[str, Any] | None:
    """Get a single platform report with full control details.

    Args:
        db: Motor database handle.
        report_id: Report ObjectId string.

    Returns:
        Report dict, or None if not found.
    """
    from bson.errors import InvalidId

    try:
        oid = ObjectId(report_id)
    except (InvalidId, TypeError):
        return None
    doc = await db["compliance_reports"].find_one({"_id": oid})
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


async def delete_report(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    report_id: str,
) -> bool:
    """Delete a generated platform report.

    Args:
        db: Motor database handle.
        report_id: Report ObjectId string.

    Returns:
        True if the report was found and deleted.
    """
    from bson.errors import InvalidId

    try:
        oid = ObjectId(report_id)
    except (InvalidId, TypeError):
        return False
    result = await db["compliance_reports"].delete_one({"_id": oid})
    return result.deleted_count > 0
