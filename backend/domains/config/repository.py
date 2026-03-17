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

    # Decrypt sensitive fields stored encrypted (handles legacy plaintext too).
    for field_name in (
        "nvd_api_key",
        "oidc_client_secret",
        "backup_s3_access_key",
        "backup_s3_secret_key",
    ):
        raw = doc.get(field_name)
        if raw:
            try:
                doc[field_name] = decrypt_field(raw) or ""
            except ValueError:
                logger.warning("Failed to decrypt {} — returning empty", field_name)
                doc[field_name] = ""

    return AppConfig(**doc)


async def save(db: AsyncIOMotorDatabase, config: AppConfig) -> AppConfig:  # type: ignore[type-arg]
    """Persist the config document, replacing any existing one.

    Encrypts the ``nvd_api_key`` field before writing so it is never
    stored as plaintext in the database.
    """
    config.updated_at = utc_now().isoformat()
    doc = config.model_dump()
    doc["_id"] = _ID

    # Encrypt sensitive fields before persisting.
    for field_name in (
        "nvd_api_key",
        "oidc_client_secret",
        "backup_s3_access_key",
        "backup_s3_secret_key",
    ):
        if doc.get(field_name):
            doc[field_name] = encrypt_field(doc[field_name])

    await db[_COLLECTION].replace_one({"_id": _ID}, doc, upsert=True)
    return config
