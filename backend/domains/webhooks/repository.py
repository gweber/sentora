"""Webhooks domain repository — all MongoDB access for webhooks."""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.webhooks.entities import Webhook

# ── Document converters ───────────────────────────────────────────────────────


def _doc_to_webhook(doc: dict[str, Any]) -> Webhook:
    """Convert a MongoDB document to a Webhook entity.

    Decrypts the ``secret`` field if it was stored encrypted.
    """
    from utils.crypto import decrypt_field

    try:
        secret = decrypt_field(doc.get("secret", ""))
    except ValueError:
        secret = ""  # Key rotation — secret needs re-encryption

    return Webhook(
        id=str(doc["_id"]),
        name=doc.get("name", ""),
        url=doc.get("url", ""),
        events=doc.get("events", []),
        secret=secret,
        enabled=doc.get("enabled", True),
        created_at=doc.get("created_at", ""),
        last_triggered_at=doc.get("last_triggered_at"),
        failure_count=doc.get("failure_count", 0),
        last_error=doc.get("last_error"),
    )


def _webhook_to_doc(webhook: Webhook) -> dict[str, Any]:
    """Convert a Webhook entity to a MongoDB document.

    Encrypts the ``secret`` field before storage.
    """
    from utils.crypto import encrypt_field

    return {
        "_id": webhook.id,
        "name": webhook.name,
        "url": webhook.url,
        "events": webhook.events,
        "secret": encrypt_field(webhook.secret),
        "enabled": webhook.enabled,
        "created_at": webhook.created_at,
        "last_triggered_at": webhook.last_triggered_at,
        "failure_count": webhook.failure_count,
        "last_error": webhook.last_error,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────


async def list_all(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[Webhook]:
    cursor = db["webhooks"].find({}).sort("name", 1)
    return [_doc_to_webhook(doc) async for doc in cursor]


async def get_by_id(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
) -> Webhook | None:
    doc = await db["webhooks"].find_one({"_id": webhook_id})
    return _doc_to_webhook(doc) if doc else None


async def create(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook: Webhook,
) -> None:
    await db["webhooks"].insert_one(_webhook_to_doc(webhook))


async def update(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
    updates: dict[str, Any],
) -> None:
    await db["webhooks"].update_one(
        {"_id": webhook_id},
        {"$set": updates},
    )


async def delete(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    webhook_id: str,
) -> None:
    await db["webhooks"].delete_one({"_id": webhook_id})


async def get_by_event(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    event_name: str,
) -> list[Webhook]:
    """Find all enabled webhooks subscribed to a specific event."""
    cursor = db["webhooks"].find({"enabled": True, "events": event_name})
    return [_doc_to_webhook(doc) async for doc in cursor]
