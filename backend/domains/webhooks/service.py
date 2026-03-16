"""Webhooks domain service — business logic and event dispatch."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import httpx
from bson import ObjectId
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from domains.webhooks import repository
from domains.webhooks.dto import (
    WebhookCreateRequest,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdateRequest,
)
from domains.webhooks.entities import VALID_EVENTS, Webhook
from errors import WebhookError, WebhookNotFoundError
from utils.dt import utc_now

#: Auto-disable threshold — webhooks are disabled after this many consecutive failures.
_MAX_FAILURES = 10

#: HTTP timeout for webhook delivery (seconds).
_DELIVERY_TIMEOUT = 5.0


# ── Converters ────────────────────────────────────────────────────────────────


def _webhook_to_response(webhook: Webhook) -> WebhookResponse:
    """Convert a Webhook entity to its API response DTO."""
    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        events=webhook.events,
        enabled=webhook.enabled,
        created_at=webhook.created_at,
        last_triggered_at=webhook.last_triggered_at,
        failure_count=webhook.failure_count,
        last_error=webhook.last_error,
    )


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for the payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


# ── CRUD ──────────────────────────────────────────────────────────────────────


async def list_webhooks(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[WebhookResponse]:
    webhooks = await repository.list_all(db)
    return [_webhook_to_response(w) for w in webhooks]


async def get_webhook(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
) -> WebhookResponse:
    webhook = await repository.get_by_id(db, webhook_id)
    if webhook is None:
        raise WebhookNotFoundError(f"Webhook '{webhook_id}' not found")
    return _webhook_to_response(webhook)


async def create_webhook(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    req: WebhookCreateRequest,
    actor: str = "system",
) -> WebhookResponse:
    # Validate events
    invalid = set(req.events) - VALID_EVENTS
    if invalid:
        raise WebhookError(
            f"Invalid event(s): {', '.join(sorted(invalid))}. "
            f"Valid events: {', '.join(sorted(VALID_EVENTS))}",
        )

    secret = req.secret if req.secret else secrets.token_hex(32)
    webhook = Webhook(
        id=str(ObjectId()),
        name=req.name,
        url=req.url,
        events=req.events,
        secret=secret,
        created_at=utc_now().isoformat(),
    )
    await repository.create(db, webhook)

    await audit(
        db,
        domain="webhooks",
        action="webhooks.created",
        actor=actor,
        summary=f"Webhook '{req.name}' created",
        details={"webhook_id": webhook.id, "url": req.url, "events": req.events},
    )
    return _webhook_to_response(webhook)


async def update_webhook(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
    req: WebhookUpdateRequest,
    actor: str = "system",
) -> WebhookResponse:
    webhook = await repository.get_by_id(db, webhook_id)
    if webhook is None:
        raise WebhookNotFoundError(f"Webhook '{webhook_id}' not found")

    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.url is not None:
        updates["url"] = req.url
    if req.events is not None:
        invalid = set(req.events) - VALID_EVENTS
        if invalid:
            raise WebhookError(
                f"Invalid event(s): {', '.join(sorted(invalid))}. "
                f"Valid events: {', '.join(sorted(VALID_EVENTS))}",
            )
        updates["events"] = req.events
    if req.enabled is not None:
        updates["enabled"] = req.enabled
        # Reset failure count when re-enabling
        if req.enabled and webhook.failure_count > 0:
            updates["failure_count"] = 0

    if updates:
        await repository.update(db, webhook_id, updates)
        await audit(
            db,
            domain="webhooks",
            action="webhooks.updated",
            actor=actor,
            summary=f"Webhook '{webhook.name}' updated",
            details={"webhook_id": webhook_id, "fields": list(updates.keys())},
        )

    updated = await repository.get_by_id(db, webhook_id)
    if updated is None:
        raise WebhookNotFoundError(f"Webhook '{webhook_id}' not found")
    return _webhook_to_response(updated)


async def delete_webhook(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
    actor: str = "system",
) -> None:
    webhook = await repository.get_by_id(db, webhook_id)
    if webhook is None:
        raise WebhookNotFoundError(f"Webhook '{webhook_id}' not found")
    await repository.delete(db, webhook_id)
    await audit(
        db,
        domain="webhooks",
        action="webhooks.deleted",
        actor=actor,
        summary=f"Webhook '{webhook.name}' deleted",
        details={"webhook_id": webhook_id, "name": webhook.name},
    )


# ── Test delivery ─────────────────────────────────────────────────────────────


async def test_webhook(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
) -> WebhookTestResponse:
    """Send a test event to a webhook and return the result."""
    webhook = await repository.get_by_id(db, webhook_id)
    if webhook is None:
        raise WebhookNotFoundError(f"Webhook '{webhook_id}' not found")

    try:
        from utils.ssrf import resolve_and_validate

        await resolve_and_validate(webhook.url)
    except Exception as exc:
        logger.warning("Webhook test blocked for {}: {}", webhook_id, exc)
        return WebhookTestResponse(
            success=False,
            status_code=None,
            response_time_ms=0.0,
        )

    payload = {
        "event": "webhook.test",
        "timestamp": utc_now().isoformat(),
        "data": {"message": "This is a test event from Sentora"},
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = _sign_payload(payload_bytes, webhook.secret)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
            resp = await client.post(
                webhook.url,
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": "webhook.test",
                },
            )
        elapsed_ms = (time.monotonic() - start) * 1000
        return WebhookTestResponse(
            success=resp.status_code < 400,
            status_code=resp.status_code,
            response_time_ms=round(elapsed_ms, 2),
        )
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning("Webhook test delivery failed for {}: {}", webhook_id, exc)
        return WebhookTestResponse(
            success=False,
            status_code=None,
            response_time_ms=round(elapsed_ms, 2),
        )


# ── Event dispatch (fire-and-forget) ─────────────────────────────────────────


def _log_task_exception(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Log unhandled exceptions from fire-and-forget webhook delivery tasks."""
    if not task.cancelled() and task.exception():
        logger.error("Webhook delivery task failed: {}", task.exception())


async def dispatch_event(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    event_name: str,
    payload: dict[str, Any],
) -> None:
    """Fire webhook notifications for an event.

    This is called from other domains (e.g. sync, classification) and creates
    background tasks so it never blocks the caller.

    Args:
        db: Motor database handle.
        event_name: The event that occurred (e.g. "sync.completed").
        payload: Event-specific data to include in the POST body.
    """
    webhooks = await repository.get_by_event(db, event_name)
    if not webhooks:
        return

    for webhook in webhooks:
        task = asyncio.create_task(_deliver(db, webhook, event_name, payload))
        task.add_done_callback(_log_task_exception)


async def _deliver(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook: Webhook,
    event_name: str,
    payload: dict[str, Any],
) -> None:
    """Deliver a single webhook notification.

    On success, resets failure_count to 0 and updates last_triggered_at.
    On failure, increments failure_count and auto-disables the webhook
    after ``_MAX_FAILURES`` consecutive failures.
    """
    try:
        from utils.ssrf import resolve_and_validate

        await resolve_and_validate(webhook.url)
    except Exception as exc:
        logger.warning(
            "Webhook '{}' delivery blocked (SSRF check): {}",
            webhook.name,
            exc,
        )
        await db["webhooks"].update_one(
            {"_id": webhook.id},
            {
                "$inc": {"failure_count": 1},
                "$set": {"last_error": f"Blocked: {exc}"},
            },
        )
        updated = await repository.get_by_id(db, webhook.id)
        if updated and updated.failure_count >= _MAX_FAILURES:
            await repository.update(
                db,
                webhook.id,
                {
                    "enabled": False,
                    "last_error": f"Auto-disabled after {_MAX_FAILURES} failures: {exc}",
                },
            )
        return

    body = {
        "event": event_name,
        "timestamp": utc_now().isoformat(),
        "data": payload,
    }
    body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
    signature = _sign_payload(body_bytes, webhook.secret)

    try:
        async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
            resp = await client.post(
                webhook.url,
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": event_name,
                },
            )

        if resp.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Webhook returned {resp.status_code}",
                request=resp.request,
                response=resp,
            )

        # Success — reset failure counter and clear any previous error
        await repository.update(
            db,
            webhook.id,
            {
                "failure_count": 0,
                "last_triggered_at": utc_now().isoformat(),
                "last_error": None,
            },
        )
        logger.debug(
            "Webhook '{}' delivered event '{}' to {} (status={})",
            webhook.name,
            event_name,
            webhook.url,
            resp.status_code,
        )

    except Exception as exc:
        await db["webhooks"].update_one(
            {"_id": webhook.id},
            {
                "$inc": {"failure_count": 1},
                "$set": {"last_error": str(exc)[:500]},
            },
        )
        updated_wh = await repository.get_by_id(db, webhook.id)
        new_count = updated_wh.failure_count if updated_wh else webhook.failure_count + 1

        if new_count >= _MAX_FAILURES:
            await repository.update(db, webhook.id, {"enabled": False})
            logger.warning(
                "Webhook '{}' auto-disabled after {} consecutive failures (last: {})",
                webhook.name,
                new_count,
                exc,
            )
            await audit(
                db,
                domain="webhooks",
                action="webhooks.auto_disabled",
                status="failure",
                summary=f"Webhook '{webhook.name}' auto-disabled after {new_count} failures",
                details={"webhook_id": webhook.id, "last_error": str(exc)},
            )
        else:
            logger.warning(
                "Webhook '{}' delivery failed ({}/{}): {}",
                webhook.name,
                new_count,
                _MAX_FAILURES,
                exc,
            )
