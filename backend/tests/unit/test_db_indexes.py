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


async def test_oidc_pending_states_ttl(test_db: AsyncIOMotorDatabase) -> None:
    """oidc_pending_states TTL index should expire after 300 seconds (AUDIT-021)."""
    from db_indexes import ensure_all_indexes

    await ensure_all_indexes(test_db)
    indexes = await test_db["oidc_pending_states"].index_information()
    ttl_indexes = {name: info for name, info in indexes.items() if "expireAfterSeconds" in info}
    assert ttl_indexes, "No TTL index found on oidc_pending_states"
    ttl_values = [info["expireAfterSeconds"] for info in ttl_indexes.values()]
    assert 300 in ttl_values


async def test_saml_pending_requests_ttl(test_db: AsyncIOMotorDatabase) -> None:
    """saml_pending_requests TTL index should expire after 300 seconds (AUDIT-022)."""
    from db_indexes import ensure_all_indexes

    await ensure_all_indexes(test_db)
    indexes = await test_db["saml_pending_requests"].index_information()
    ttl_indexes = {name: info for name, info in indexes.items() if "expireAfterSeconds" in info}
    assert ttl_indexes, "No TTL index found on saml_pending_requests"
    ttl_values = [info["expireAfterSeconds"] for info in ttl_indexes.values()]
    assert 300 in ttl_values


async def test_saml_token_exchange_ttl(test_db: AsyncIOMotorDatabase) -> None:
    """saml_token_exchange TTL index should expire after 120 seconds (AUDIT-023)."""
    from db_indexes import ensure_all_indexes

    await ensure_all_indexes(test_db)
    indexes = await test_db["saml_token_exchange"].index_information()
    ttl_indexes = {name: info for name, info in indexes.items() if "expireAfterSeconds" in info}
    assert ttl_indexes, "No TTL index found on saml_token_exchange"
    ttl_values = [info["expireAfterSeconds"] for info in ttl_indexes.values()]
    assert 120 in ttl_values
