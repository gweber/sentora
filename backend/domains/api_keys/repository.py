"""API Keys domain repository — all MongoDB access for api_keys collection."""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.api_keys.entities import APIKey
from utils.dt import utc_now

_COLLECTION = "api_keys"


# ── Document converters ──────────────────────────────────────────────────────


def _doc_to_entity(doc: dict[str, Any]) -> APIKey:
    """Convert a MongoDB document to an APIKey entity."""
    return APIKey(
        id=str(doc["_id"]),
        tenant_id=doc["tenant_id"],
        name=doc["name"],
        description=doc.get("description"),
        key_prefix=doc["key_prefix"],
        key_hash=doc["key_hash"],
        scopes=doc.get("scopes", []),
        rate_limit_per_minute=doc.get("rate_limit_per_minute", 60),
        rate_limit_per_hour=doc.get("rate_limit_per_hour", 1000),
        created_at=doc["created_at"],
        created_by=doc["created_by"],
        expires_at=doc.get("expires_at"),
        last_used_at=doc.get("last_used_at"),
        last_used_ip=doc.get("last_used_ip"),
        is_active=doc.get("is_active", True),
        revoked_at=doc.get("revoked_at"),
        revoked_by=doc.get("revoked_by"),
        grace_expires_at=doc.get("grace_expires_at"),
        rotated_from_id=doc.get("rotated_from_id"),
    )


def _entity_to_doc(entity: APIKey) -> dict[str, Any]:
    """Convert an APIKey entity to a MongoDB document."""
    doc: dict[str, Any] = {
        "_id": entity.id,
        "tenant_id": entity.tenant_id,
        "name": entity.name,
        "description": entity.description,
        "key_prefix": entity.key_prefix,
        "key_hash": entity.key_hash,
        "scopes": entity.scopes,
        "rate_limit_per_minute": entity.rate_limit_per_minute,
        "rate_limit_per_hour": entity.rate_limit_per_hour,
        "created_at": entity.created_at,
        "created_by": entity.created_by,
        "expires_at": entity.expires_at,
        "last_used_at": entity.last_used_at,
        "last_used_ip": entity.last_used_ip,
        "is_active": entity.is_active,
        "revoked_at": entity.revoked_at,
        "revoked_by": entity.revoked_by,
        "grace_expires_at": entity.grace_expires_at,
        "rotated_from_id": entity.rotated_from_id,
    }
    return doc


# ── Queries ──────────────────────────────────────────────────────────────────


async def find_by_hash(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_hash: str,
) -> APIKey | None:
    """Look up an API key by its SHA-256 hash."""
    doc = await db[_COLLECTION].find_one({"key_hash": key_hash})
    return _doc_to_entity(doc) if doc else None


async def find_by_hash_including_grace(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_hash: str,
) -> APIKey | None:
    """Look up an API key by hash, including revoked keys still in grace period."""
    now = utc_now()
    doc = await db[_COLLECTION].find_one(
        {
            "key_hash": key_hash,
            "$or": [
                {"is_active": True},
                {"grace_expires_at": {"$gt": now}},
            ],
        }
    )
    return _doc_to_entity(doc) if doc else None


async def find_by_id(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
) -> APIKey | None:
    """Look up an API key by its internal ID."""
    doc = await db[_COLLECTION].find_one({"_id": key_id})
    return _doc_to_entity(doc) if doc else None


async def list_by_tenant(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_id: str,
) -> list[APIKey]:
    """List all API keys for a tenant, sorted by creation date descending."""
    cursor = db[_COLLECTION].find({"tenant_id": tenant_id}).sort("created_at", -1)
    return [_doc_to_entity(doc) async for doc in cursor]


# ── Commands ─────────────────────────────────────────────────────────────────


async def create(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    entity: APIKey,
) -> None:
    """Insert a new API key document."""
    await db[_COLLECTION].insert_one(_entity_to_doc(entity))


async def update(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
    updates: dict[str, Any],
) -> None:
    """Update specific fields of an API key document."""
    await db[_COLLECTION].update_one({"_id": key_id}, {"$set": updates})


async def touch(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
    ip: str,
) -> None:
    """Update last_used_at and last_used_ip for a key."""
    now = utc_now()
    await db[_COLLECTION].update_one(
        {"_id": key_id},
        {"$set": {"last_used_at": now, "last_used_ip": ip}},
    )


async def delete(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
) -> None:
    """Hard-delete an API key document."""
    await db[_COLLECTION].delete_one({"_id": key_id})
