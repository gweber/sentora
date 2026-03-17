"""EOL domain repository.

MongoDB operations for the ``eol_products`` collection and EOL match
persistence on ``app_summaries``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.eol.entities import EOLCycle
from utils.dt import utc_now

# ---------------------------------------------------------------------------
# Collection name
# ---------------------------------------------------------------------------

COLLECTION = "eol_products"


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------


async def upsert_product(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    product_id: str,
    name: str,
    cycles: list[dict[str, Any]],
) -> bool:
    """Upsert an EOL product with its lifecycle cycles.

    Args:
        db: Motor database handle.
        product_id: endoflife.date product slug.
        name: Human-readable product name.
        cycles: Raw cycle dicts from the API.

    Returns:
        True if the document was created (not just updated).
    """
    now = utc_now()
    result = await db[COLLECTION].update_one(
        {"product_id": product_id},
        {
            "$set": {
                "product_id": product_id,
                "name": name,
                "cycles": cycles,
                "last_synced": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return bool(result.upserted_id)


async def get_product(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    product_id: str,
) -> dict[str, Any] | None:
    """Fetch a single EOL product by ID.

    Args:
        db: Motor database handle.
        product_id: endoflife.date product slug.

    Returns:
        The product document, or ``None``.
    """
    return await db[COLLECTION].find_one({"product_id": product_id})


async def list_products(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """List EOL products with optional search and pagination.

    Args:
        db: Motor database handle.
        search: Optional search term for product name/ID.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Tuple of (product documents, total count).
    """
    query: dict[str, Any] = {}
    if search:
        query["$or"] = [
            {"product_id": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]

    total = await db[COLLECTION].count_documents(query)
    skip = (page - 1) * page_size

    docs = []
    async for doc in db[COLLECTION].find(query).sort("product_id", 1).skip(skip).limit(page_size):
        docs.append(doc)

    return docs, total


async def get_all_products_with_cycles(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, list[EOLCycle]]:
    """Load all EOL products with parsed cycle entities.

    Used by the matching engine to compare app versions against cycles.

    Args:
        db: Motor database handle.

    Returns:
        Mapping of product_id → list of EOLCycle entities.
    """
    result: dict[str, list[EOLCycle]] = {}
    async for doc in db[COLLECTION].find({}, {"product_id": 1, "cycles": 1}):
        product_id = doc["product_id"]
        cycles = []
        today = date.today()
        for c in doc.get("cycles", []):
            eol_date = _parse_date(c.get("eol_date"))
            support_end = _parse_date(c.get("support_end"))
            is_eol = bool(eol_date and eol_date < today)
            is_security_only = bool(
                support_end and support_end < today and (not eol_date or eol_date >= today)
            )
            cycles.append(
                EOLCycle(
                    cycle=str(c.get("cycle", "")),
                    release_date=_parse_date(c.get("release_date")),
                    support_end=support_end,
                    eol_date=eol_date,
                    lts=bool(c.get("lts", False)),
                    latest_version=c.get("latest_version"),
                    latest_version_date=_parse_date(c.get("latest_version_date")),
                    is_eol=is_eol,
                    is_security_only=is_security_only,
                )
            )
        result[product_id] = cycles
    return result


async def get_product_count(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> int:
    """Return the total number of synced EOL products.

    Args:
        db: Motor database handle.

    Returns:
        Product count.
    """
    return await db[COLLECTION].count_documents({})


async def get_last_sync_time(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> datetime | None:
    """Return the most recent sync timestamp across all products.

    Args:
        db: Motor database handle.

    Returns:
        The latest ``last_synced`` value, or ``None`` if no products exist.
    """
    doc = await db[COLLECTION].find_one(
        {},
        {"last_synced": 1},
        sort=[("last_synced", -1)],
    )
    return doc["last_synced"] if doc else None


async def get_matched_app_count(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> int:
    """Count app summaries that have an EOL match.

    Args:
        db: Motor database handle.

    Returns:
        Number of matched apps.
    """
    return await db["app_summaries"].count_documents({"eol_match": {"$exists": True}})


async def get_fuzzy_matches_for_review(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """List app summaries with fuzzy EOL matches pending review.

    Args:
        db: Motor database handle.
        page: Page number.
        page_size: Items per page.

    Returns:
        Tuple of (match documents, total count).
    """
    query = {"eol_match.match_source": "fuzzy"}
    total = await db["app_summaries"].count_documents(query)
    skip = (page - 1) * page_size

    docs = []
    async for doc in (
        db["app_summaries"]
        .find(query)
        .sort("eol_match.match_confidence", -1)
        .skip(skip)
        .limit(page_size)
    ):
        docs.append(doc)

    return docs, total


async def confirm_match(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    normalized_name: str,
    eol_product_id: str,
) -> bool:
    """Confirm a fuzzy match, promoting it to manual.

    Args:
        db: Motor database handle.
        normalized_name: The app's normalized name.
        eol_product_id: The confirmed EOL product ID.

    Returns:
        True if the document was updated.
    """
    result = await db["app_summaries"].update_one(
        {
            "normalized_name": normalized_name,
            "eol_match.eol_product_id": eol_product_id,
        },
        {
            "$set": {
                "eol_match.match_source": "manual",
                "eol_match.match_confidence": 1.0,
            }
        },
    )
    return result.modified_count > 0


async def dismiss_match(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    normalized_name: str,
) -> bool:
    """Dismiss a fuzzy match, removing the EOL match data.

    Args:
        db: Motor database handle.
        normalized_name: The app's normalized name.

    Returns:
        True if the document was updated.
    """
    result = await db["app_summaries"].update_one(
        {"normalized_name": normalized_name},
        {"$unset": {"eol_match": ""}},
    )
    return result.modified_count > 0


# ---------------------------------------------------------------------------
# Name → EOL product mappings (user-configurable)
# ---------------------------------------------------------------------------

MAPPINGS_COLLECTION = "eol_name_mappings"


async def list_name_mappings(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> list[dict[str, Any]]:
    """Return all user-configured name → EOL product mappings.

    Args:
        db: Motor database handle.

    Returns:
        List of mapping documents.
    """
    docs = []
    async for doc in db[MAPPINGS_COLLECTION].find().sort("app_name_prefix", 1):
        doc.pop("_id", None)
        docs.append(doc)
    return docs


async def upsert_name_mapping(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    app_name_prefix: str,
    eol_product_id: str,
) -> bool:
    """Create or update a name → EOL product mapping.

    Args:
        db: Motor database handle.
        app_name_prefix: Lowercase normalized app name prefix.
        eol_product_id: endoflife.date product slug.

    Returns:
        True if the document was created (not just updated).
    """
    result = await db[MAPPINGS_COLLECTION].update_one(
        {"app_name_prefix": app_name_prefix},
        {
            "$set": {
                "app_name_prefix": app_name_prefix,
                "eol_product_id": eol_product_id,
                "updated_at": utc_now(),
            },
            "$setOnInsert": {"created_at": utc_now()},
        },
        upsert=True,
    )
    return bool(result.upserted_id)


async def delete_name_mapping(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    app_name_prefix: str,
) -> bool:
    """Delete a name → EOL product mapping.

    Args:
        db: Motor database handle.
        app_name_prefix: The mapping key to delete.

    Returns:
        True if a document was deleted.
    """
    result = await db[MAPPINGS_COLLECTION].delete_one({"app_name_prefix": app_name_prefix})
    return result.deleted_count > 0


async def get_all_name_mappings_dict(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, str]:
    """Load all user mappings as a dict for use by the matching engine.

    Args:
        db: Motor database handle.

    Returns:
        Mapping of app_name_prefix → eol_product_id.
    """
    result: dict[str, str] = {}
    async for doc in db[MAPPINGS_COLLECTION].find({}, {"app_name_prefix": 1, "eol_product_id": 1}):
        result[doc["app_name_prefix"]] = doc["eol_product_id"]
    return result


async def ensure_indexes(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> None:
    """Create indexes for the EOL collections.

    Args:
        db: Motor database handle.
    """
    await db[COLLECTION].create_index("product_id", unique=True, background=True)
    await db[COLLECTION].create_index("last_synced", background=True)
    await db[MAPPINGS_COLLECTION].create_index("app_name_prefix", unique=True, background=True)
    logger.debug("EOL indexes ensured")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_date(value: str | date | datetime | bool | None) -> date | None:
    """Parse a date from various formats (string, date, datetime, bool).

    endoflife.date returns ``false`` for unknown dates and ISO date strings
    for known dates.

    Args:
        value: The raw date value from the API.

    Returns:
        Parsed date or ``None``.
    """
    if value is None or value is False:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None
