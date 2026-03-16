"""Taxonomy seed loader.

Reads the bundled ``seed_data/taxonomy.yaml`` file and populates the
``taxonomy_entries`` and ``taxonomy_categories`` collections on first startup. The operation is
idempotent: if any documents already exist the seed is skipped entirely.

No cross-domain imports — only the taxonomy repository is used here.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.taxonomy import repository
from domains.taxonomy.entities import SoftwareEntry
from utils.dt import utc_now

_SEED_FILE = Path(__file__).parent.parent.parent / "seed_data" / "taxonomy.yaml"

# Default universal exclusion patterns — these are seeded as ``is_universal=True``
_UNIVERSAL_NAMES = frozenset(
    {
        "microsoft edge",
        "google chrome",
        "mozilla firefox",
        "microsoft .net",
        "microsoft visual c++ runtime",
        "windows sdk",
        "microsoft office",
        "microsoft 365",
        "microsoft teams",
        "adobe acrobat",
        "adobe reader",
        "7-zip",
        "notepad++",
        "vlc media player",
        "sentinelone",
    }
)


async def seed_taxonomy_if_empty(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Populate the taxonomy collection with seed data if it is empty.

    This is called once during application startup. If the collection already
    contains documents the seed is skipped to avoid overwriting user edits.

    Args:
        db: Motor database handle.
    """
    existing = await repository.count(db)
    if existing > 0:
        logger.info("Taxonomy already seeded (%d entries) — skipping", existing)
        # Ensure categories collection is populated (migration for existing installs)
        await _ensure_categories_seeded(db)
        return

    await repository.ensure_indexes(db)

    entries, categories = _load_seed_entries()
    inserted = await repository.bulk_insert(db, entries, ordered=False)
    logger.info("Taxonomy seeded with %d entries", inserted)

    # Seed the taxonomy_categories collection
    if categories:
        try:
            cat_count = await repository.bulk_insert_categories(db, categories)
            logger.info("Taxonomy categories seeded with %d categories", cat_count)
        except Exception as exc:
            logger.warning("Could not seed taxonomy categories: {}", exc)


async def _ensure_categories_seeded(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Ensure taxonomy_categories is populated (migration path for existing installs).

    If the taxonomy_categories collection is empty but taxonomy_entries has entries,
    derive categories from the existing entries and populate the categories collection.
    """
    from bson import ObjectId

    cat_count = await db[repository.CATEGORIES_COLLECTION].count_documents({})
    if cat_count > 0:
        return

    # Derive categories from existing entries
    pipeline = [
        {"$group": {"_id": "$category", "display": {"$first": "$category_display"}}},
    ]
    now = utc_now()
    categories = []
    async for doc in db[repository.COLLECTION].aggregate(pipeline):
        categories.append(
            {
                "_id": str(ObjectId()),
                "key": doc["_id"],
                "display": doc.get("display") or doc["_id"],
                "created_at": now,
                "updated_at": now,
            }
        )

    if categories:
        try:
            count = await repository.bulk_insert_categories(db, categories)
            logger.info("Migrated %d categories from existing taxonomy entries", count)
        except Exception as exc:
            logger.warning("Could not migrate taxonomy categories: {}", exc)


def _load_seed_entries() -> tuple[list[SoftwareEntry], list[dict]]:
    """Load and parse the taxonomy YAML seed file into SoftwareEntry objects and categories.

    Returns:
        Tuple of (entries, categories) ready for bulk insertion.

    Raises:
        FileNotFoundError: If the taxonomy.yaml seed file is missing.
        ValueError: If the YAML structure is invalid.
    """
    from bson import ObjectId

    if not _SEED_FILE.exists():
        raise FileNotFoundError(f"Taxonomy seed file not found: {_SEED_FILE}")

    with _SEED_FILE.open() as fh:
        data: dict = yaml.safe_load(fh)

    entries: list[SoftwareEntry] = []
    categories: list[dict] = []
    now = utc_now()

    for category_key, category_data in data.items():
        display = category_data.get("display", category_key)

        # Build category document
        categories.append(
            {
                "_id": str(ObjectId()),
                "key": category_key,
                "display": display,
                "created_at": now,
                "updated_at": now,
            }
        )

        for raw in category_data.get("entries", []):
            name: str = raw["name"]
            patterns: list[str] = raw.get("patterns", [])
            industry: list[str] = raw.get("industry", [])
            name_lower = name.lower()
            is_universal = any(
                name_lower == u or name_lower.startswith(u + " ") for u in _UNIVERSAL_NAMES
            )

            entries.append(
                SoftwareEntry(
                    name=name,
                    patterns=patterns,
                    publisher=raw.get("publisher"),
                    category=category_key,
                    category_display=display,
                    subcategory=raw.get("subcategory"),
                    industry=industry,
                    description=raw.get("description"),
                    is_universal=is_universal,
                    user_added=False,
                    created_at=now,
                    updated_at=now,
                )
            )

    return entries, categories
