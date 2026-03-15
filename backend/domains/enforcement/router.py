"""Enforcement domain router.

Endpoints:
    GET    /rules              — list all rules
    POST   /rules              — create rule
    GET    /rules/{id}         — rule detail
    PUT    /rules/{id}         — update rule
    DELETE /rules/{id}         — delete rule
    PUT    /rules/{id}/toggle  — enable/disable
    POST   /check              — run all active rules
    POST   /check/{rule_id}    — run single rule
    GET    /results/latest     — latest results
    GET    /results/{rule_id}  — rule history
    GET    /summary            — aggregated summary
    GET    /violations         — current violations (paginated)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.enforcement import service
from domains.enforcement.dto import (
    CheckRunResponse,
    CreateRuleRequest,
    EnforcementResultResponse,
    EnforcementRuleResponse,
    RuleListResponse,
    SummaryResponse,
    UpdateRuleRequest,
    ViolationListResponse,
)
from middleware.auth import get_current_user, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Rules CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/rules",
    response_model=RuleListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_rules(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> RuleListResponse:
    """List all enforcement rules."""
    return await service.list_all_rules(db)


@router.post(
    "/rules",
    response_model=EnforcementRuleResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
    status_code=201,
)
async def create_rule(
    payload: CreateRuleRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> EnforcementRuleResponse:
    """Create a new enforcement rule. Admin only."""
    return await service.create_rule(
        db,
        actor=user.sub,
        name=payload.name,
        taxonomy_category_id=payload.taxonomy_category_id,
        rule_type=payload.type,
        severity=payload.severity,
        description=payload.description,
        scope_groups=payload.scope_groups,
        scope_tags=payload.scope_tags,
        labels=payload.labels,
    )


@router.get(
    "/rules/{rule_id}",
    response_model=EnforcementRuleResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> EnforcementRuleResponse:
    """Get a single rule by ID."""
    result = await service.get_rule_detail(db, rule_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.put(
    "/rules/{rule_id}",
    response_model=EnforcementRuleResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def update_rule(
    rule_id: str,
    payload: UpdateRuleRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> EnforcementRuleResponse:
    """Update a rule. Admin only."""
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await service.update_rule_fields(db, rule_id, actor=user.sub, updates=updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete(
    "/rules/{rule_id}",
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def delete_rule(
    rule_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> dict[str, str]:
    """Delete a rule. Admin only."""
    deleted = await service.remove_rule(db, rule_id, actor=user.sub)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"detail": "Rule deleted"}


@router.put(
    "/rules/{rule_id}/toggle",
    response_model=EnforcementRuleResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def toggle_rule(
    rule_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> EnforcementRuleResponse:
    """Toggle a rule's enabled state. Admin only."""
    result = await service.toggle_rule(db, rule_id, actor=user.sub)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


# ---------------------------------------------------------------------------
# Check execution
# ---------------------------------------------------------------------------


@router.post(
    "/check",
    response_model=CheckRunResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def run_all_checks(
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> CheckRunResponse:
    """Run enforcement checks for all enabled rules. Admin only."""
    return await service.trigger_check(db, actor=user.sub)


@router.post(
    "/check/{rule_id}",
    response_model=CheckRunResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def run_single_check(
    rule_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> CheckRunResponse:
    """Run enforcement check for a single rule. Admin only."""
    return await service.trigger_check(db, actor=user.sub, rule_id=rule_id)


# ---------------------------------------------------------------------------
# Results & summary
# ---------------------------------------------------------------------------


@router.get(
    "/results/latest",
    response_model=list[EnforcementResultResponse],
    dependencies=[Depends(get_current_user)],
)
async def get_latest_results(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[EnforcementResultResponse]:
    """Get the latest result for each rule."""
    return await service.get_latest_rule_results(db)


@router.get(
    "/results/{rule_id}",
    response_model=list[EnforcementResultResponse],
    dependencies=[Depends(get_current_user)],
)
async def get_rule_history(
    rule_id: str,
    limit: int = Query(90, ge=1, le=365),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[EnforcementResultResponse]:
    """Get historical results for a specific rule."""
    return await service.get_rule_result_history(db, rule_id, limit)


@router.get(
    "/summary",
    response_model=SummaryResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_summary(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SummaryResponse:
    """Get aggregated enforcement summary."""
    return await service.get_summary(db)


@router.get(
    "/violations",
    response_model=ViolationListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_violations(
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> ViolationListResponse:
    """Get paginated list of current violations."""
    return await service.list_current_violations(db, severity, page, page_size)
