"""Webhooks domain router — CRUD and test endpoints for webhook management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from database import get_tenant_db
from domains.auth.dto import TokenPayload
from domains.auth.entities import UserRole
from domains.webhooks import service
from domains.webhooks.dto import (
    WebhookCreateRequest,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdateRequest,
)
from middleware.auth import get_current_user, require_role

router = APIRouter()


@router.get(
    "/",
    response_model=list[WebhookResponse],
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def list_webhooks(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> list[WebhookResponse]:
    return await service.list_webhooks(db)


@router.post(
    "/",
    response_model=WebhookResponse,
    status_code=201,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def create_webhook(
    req: WebhookCreateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> WebhookResponse:
    return await service.create_webhook(db, req, actor=user.sub)


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def get_webhook(
    webhook_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> WebhookResponse:
    return await service.get_webhook(db, webhook_id)


@router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def update_webhook(
    webhook_id: str,
    req: WebhookUpdateRequest,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> WebhookResponse:
    return await service.update_webhook(db, webhook_id, req, actor=user.sub)


@router.delete(
    "/{webhook_id}",
    status_code=204,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def delete_webhook(
    webhook_id: str,
    user: TokenPayload = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> Response:
    await service.delete_webhook(db, webhook_id, actor=user.sub)
    return Response(status_code=204)


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def test_webhook(
    webhook_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> WebhookTestResponse:
    return await service.test_webhook(db, webhook_id)
