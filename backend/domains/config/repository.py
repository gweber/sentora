"""Config repository.

Reads and writes the single global config document from MongoDB.
The document always has ``_id="global"`` — upsert guarantees idempotency.

The ``nvd_api_key`` field is encrypted at rest using ``utils.crypto``
so that API keys are never stored as plaintext in the database.
"""

from __future__ import annotations

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from utils.crypto import decrypt_field, encrypt_field
from utils.dt import utc_now

from .entities import AppConfig

_COLLECTION = "app_config"
_ID = "global"


async def get(db: AsyncIOMotorDatabase) -> AppConfig:  # type: ignore[type-arg]
    """Return the current config, falling back to defaults if none is stored.

    Decrypts the ``nvd_api_key`` field on read so callers receive plaintext.
    """
    doc = await db[_COLLECTION].find_one({"_id": _ID})
    if doc is None:
        return AppConfig()
    doc.pop("_id", None)

    # Decrypt nvd_api_key if stored encrypted (handles legacy plaintext too).
    raw_key = doc.get("nvd_api_key")
    if raw_key:
        try:
            doc["nvd_api_key"] = decrypt_field(raw_key) or ""
        except ValueError:
            logger.warning("Failed to decrypt nvd_api_key — returning empty")
            doc["nvd_api_key"] = ""

    return AppConfig(**doc)


async def save(db: AsyncIOMotorDatabase, config: AppConfig) -> AppConfig:  # type: ignore[type-arg]
    """Persist the config document, replacing any existing one.

    Encrypts the ``nvd_api_key`` field before writing so it is never
    stored as plaintext in the database.
    """
    config.updated_at = utc_now().isoformat()
    doc = config.model_dump()
    doc["_id"] = _ID

    # Encrypt nvd_api_key before persisting.
    if doc.get("nvd_api_key"):
        doc["nvd_api_key"] = encrypt_field(doc["nvd_api_key"])

    await db[_COLLECTION].replace_one({"_id": _ID}, doc, upsert=True)
    return config
