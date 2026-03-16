"""Tags domain router — CRUD for tag rules plus preview and apply actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.entities import UserRole
from domains.tags import service
from domains.tags.dto import (
    TagApplyResponse,
    TagPatternCreateRequest,
    TagPreviewResponse,
    TagRuleCreateRequest,
    TagRulePatternResponse,
    TagRuleResponse,
    TagRuleUpdateRequest,
)
from middleware.auth import get_current_user, require_role

router = APIRouter()


@router.get("/", response_model=list[TagRuleResponse], dependencies=[Depends(get_current_user)])
async def list_rules(db: AsyncIOMotorDatabase = Depends(get_tenant_db)) -> list[TagRuleResponse]:  # type: ignore[type-arg]
    return await service.list_rules(db)


@router.post(
    "/",
    response_model=TagRuleResponse,
    status_code=201,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def create_rule(
    req: TagRuleCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TagRuleResponse:
    return await service.create_rule(db, req)


@router.get("/{rule_id}", response_model=TagRuleResponse, dependencies=[Depends(get_current_user)])
async def get_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TagRuleResponse:
    return await service.get_rule(db, rule_id)


@router.patch(
    "/{rule_id}",
    response_model=TagRuleResponse,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def update_rule(
    rule_id: str,
    req: TagRuleUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TagRuleResponse:
    return await service.update_rule(db, rule_id, req)


@router.delete(
    "/{rule_id}",
    status_code=204,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def delete_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    await service.delete_rule(db, rule_id)
    return Response(status_code=204)


@router.post(
    "/{rule_id}/patterns",
    response_model=TagRulePatternResponse,
    status_code=201,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def add_pattern(
    rule_id: str,
    req: TagPatternCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TagRulePatternResponse:
    return await service.add_pattern(db, rule_id, req)


@router.delete(
    "/{rule_id}/patterns/{pattern_id}",
    status_code=204,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def remove_pattern(
    rule_id: str,
    pattern_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    await service.remove_pattern(db, rule_id, pattern_id)
    return Response(status_code=204)


@router.post(
    "/{rule_id}/preview",
    response_model=TagPreviewResponse,
    dependencies=[Depends(get_current_user)],
)
async def preview_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TagPreviewResponse:
    return await service.preview_rule(db, rule_id)


@router.post(
    "/{rule_id}/apply",
    response_model=TagApplyResponse,
    dependencies=[Depends(require_role(UserRole.analyst, UserRole.admin))],
)
async def apply_rule(
    rule_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TagApplyResponse:
    return await service.apply_rule(db, rule_id)
