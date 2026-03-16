"""Tenant repository.

CRUD operations on the tenants collection in the master database.
"""

from __future__ import annotations

from bson import ObjectId
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now

from .entities import Tenant

_COLLECTION = "tenants"


def _doc_to_tenant(doc: dict) -> Tenant:
    """Convert a MongoDB document to a Tenant entity."""
    return Tenant(
        id=str(doc["_id"]),
        name=doc.get("name", ""),
        slug=doc.get("slug", ""),
        database_name=doc.get("database_name", ""),
        created_at=doc.get("created_at", ""),
        disabled=doc.get("disabled", False),
        plan=doc.get("plan", "standard"),
    )


async def get_by_slug(db: AsyncIOMotorDatabase, slug: str) -> Tenant | None:  # type: ignore[type-arg]
    """Find a tenant by slug. Returns None if not found."""
    doc = await db[_COLLECTION].find_one({"slug": slug})
    return _doc_to_tenant(doc) if doc else None


async def get_by_id(db: AsyncIOMotorDatabase, tenant_id: str) -> Tenant | None:  # type: ignore[type-arg]
    """Find a tenant by ID. Returns None if not found."""
    try:
        doc = await db[_COLLECTION].find_one({"_id": ObjectId(tenant_id)})
    except Exception:
        return None
    return _doc_to_tenant(doc) if doc else None


async def list_all(
    db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100
) -> tuple[list[Tenant], int]:  # type: ignore[type-arg]
    """List all tenants with pagination."""
    total = await db[_COLLECTION].count_documents({})
    cursor = db[_COLLECTION].find({}).sort("created_at", -1).skip(skip).limit(limit)
    tenants = [_doc_to_tenant(doc) async for doc in cursor]
    return tenants, total


async def create(db: AsyncIOMotorDatabase, tenant: Tenant) -> Tenant:  # type: ignore[type-arg]
    """Create a new tenant. Sets created_at and generates database_name."""
    doc = {
        "name": tenant.name,
        "slug": tenant.slug,
        "database_name": f"sentora_tenant_{tenant.slug}",
        "created_at": utc_now().isoformat(),
        "disabled": False,
        "plan": tenant.plan,
    }
    result = await db[_COLLECTION].insert_one(doc)
    tenant.id = str(result.inserted_id)
    tenant.database_name = str(doc["database_name"])
    tenant.created_at = str(doc["created_at"])
    logger.info(
        "Created tenant '{}' (slug={}, db={})", tenant.name, tenant.slug, tenant.database_name
    )
    return tenant


async def update(db: AsyncIOMotorDatabase, slug: str, updates: dict) -> Tenant | None:  # type: ignore[type-arg]
    """Update a tenant by slug. Returns updated tenant or None if not found."""
    updates = {**updates, "updated_at": utc_now().isoformat()}
    result = await db[_COLLECTION].find_one_and_update(
        {"slug": slug},
        {"$set": updates},
        return_document=True,
    )
    return _doc_to_tenant(result) if result else None


async def delete(db: AsyncIOMotorDatabase, slug: str) -> bool:  # type: ignore[type-arg]
    """Delete a tenant by slug. Returns True if deleted."""
    result = await db[_COLLECTION].delete_one({"slug": slug})
    if result.deleted_count:
        logger.info("Deleted tenant slug={}", slug)
    return result.deleted_count > 0
