"""Unit tests for taxonomy seed loader — category migration path.

Covers:
- _ensure_categories_seeded: migrates categories from existing entries
- seed_taxonomy_if_empty: skips seed when data exists
- _load_seed_entries: loads entries and categories from YAML
"""

from __future__ import annotations

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase


@pytest_asyncio.fixture
async def seeded_entries_no_categories(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:
    """Insert taxonomy entries but no categories — simulates pre-migration state."""
    from bson import ObjectId

    entries = [
        {
            "_id": str(ObjectId()),
            "name": "Test App 1",
            "patterns": ["test*"],
            "publisher": "TestCo",
            "category": "test_cat",
            "category_display": "Test Category",
            "subcategory": None,
            "industry": ["testing"],
            "description": "A test app",
            "is_universal": False,
            "user_added": False,
        },
        {
            "_id": str(ObjectId()),
            "name": "Test App 2",
            "patterns": ["other*"],
            "publisher": "OtherCo",
            "category": "other_cat",
            "category_display": "Other Category",
            "subcategory": None,
            "industry": [],
            "description": "Another app",
            "is_universal": False,
            "user_added": False,
        },
    ]
    await test_db["taxonomy_entries"].insert_many(entries)
    return test_db


class TestEnsureCategoriesSeeded:
    """Tests for _ensure_categories_seeded migration path."""

    async def test_migrates_categories_from_entries(
        self, seeded_entries_no_categories: AsyncIOMotorDatabase
    ) -> None:
        """Categories are derived from existing entries when categories collection is empty."""
        from domains.taxonomy.seed import _ensure_categories_seeded

        db = seeded_entries_no_categories
        # Verify no categories exist yet
        assert await db["taxonomy_categories"].count_documents({}) == 0

        await _ensure_categories_seeded(db)

        # Now categories should exist
        cat_count = await db["taxonomy_categories"].count_documents({})
        assert cat_count == 2  # test_cat and other_cat

        cats = await db["taxonomy_categories"].find({}).to_list(length=None)
        keys = {c["key"] for c in cats}
        assert "test_cat" in keys
        assert "other_cat" in keys

    async def test_skips_if_categories_exist(
        self, seeded_entries_no_categories: AsyncIOMotorDatabase
    ) -> None:
        """If categories already exist, migration is skipped."""
        from domains.taxonomy.seed import _ensure_categories_seeded

        db = seeded_entries_no_categories
        # Pre-populate one category
        await db["taxonomy_categories"].insert_one(
            {
                "_id": "existing",
                "key": "existing_cat",
                "display": "Existing",
            }
        )

        await _ensure_categories_seeded(db)
        # Should still be just 1 (not migrated)
        assert await db["taxonomy_categories"].count_documents({}) == 1


class TestSeedTaxonomyIfEmpty:
    """Tests for seed_taxonomy_if_empty."""

    async def test_skips_when_entries_exist(
        self, seeded_entries_no_categories: AsyncIOMotorDatabase
    ) -> None:
        """If taxonomy entries already exist, seeding is skipped."""
        from domains.taxonomy.seed import seed_taxonomy_if_empty

        db = seeded_entries_no_categories
        count_before = await db["taxonomy_entries"].count_documents({})

        await seed_taxonomy_if_empty(db)

        count_after = await db["taxonomy_entries"].count_documents({})
        assert count_after == count_before


class TestLoadSeedEntries:
    """Tests for _load_seed_entries."""

    def test_loads_entries_and_categories(self) -> None:
        """The seed file produces both entries and categories."""
        from domains.taxonomy.seed import _load_seed_entries

        entries, categories = _load_seed_entries()
        assert len(entries) > 0
        assert len(categories) > 0
        # Categories should have keys and display names
        for cat in categories:
            assert "key" in cat
            assert "display" in cat
