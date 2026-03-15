"""Unit test for db_indexes.ensure_all_indexes.

Verifies the function runs without error against a test database.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase


async def test_ensure_all_indexes_runs_without_error(test_db: AsyncIOMotorDatabase) -> None:
    """ensure_all_indexes should complete without raising on a clean database."""
    from db_indexes import ensure_all_indexes

    # Must not raise; MongoDB's create_index is idempotent
    await ensure_all_indexes(test_db)


async def test_ensure_all_indexes_idempotent(test_db: AsyncIOMotorDatabase) -> None:
    """Calling ensure_all_indexes twice should still succeed (idempotent)."""
    from db_indexes import ensure_all_indexes

    await ensure_all_indexes(test_db)
    await ensure_all_indexes(test_db)  # second call must also succeed
