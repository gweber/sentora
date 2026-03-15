"""Config repository.

Reads and writes the single global config document from MongoDB.
The document always has ``_id="global"`` — upsert guarantees idempotency.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.dt import utc_now

from .entities import AppConfig

_COLLECTION = "app_config"
_ID = "global"


async def get(db: AsyncIOMotorDatabase) -> AppConfig:  # type: ignore[type-arg]
    """Return the current config, falling back to defaults if none is stored."""
    doc = await db[_COLLECTION].find_one({"_id": _ID})
    if doc is None:
        return AppConfig()
    doc.pop("_id", None)
    return AppConfig(**doc)


async def save(db: AsyncIOMotorDatabase, config: AppConfig) -> AppConfig:  # type: ignore[type-arg]
    """Persist the config document, replacing any existing one."""
    config.updated_at = utc_now().isoformat()
    doc = config.model_dump()
    doc["_id"] = _ID
    await db[_COLLECTION].replace_one({"_id": _ID}, doc, upsert=True)
    return config
