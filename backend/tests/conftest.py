"""Shared test fixtures for the Sentora backend test suite.

All tests use an isolated in-process MongoDB (via mongomock-motor or a
dedicated test database). Fixtures are function-scoped by default to ensure
test isolation.

Conventions (per TESTING.md):
- No module-scoped mutable state.
- Fixtures must be idempotent — re-seeding always produces the same state.
- Never import cross-domain modules in test fixtures.
- Use ``utils.dt.utc_now()`` for all datetime needs — never patch it directly.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure

# Use a separate test database to avoid polluting the development database
_TEST_DB_NAME = "sentora_test"
_MONGO_URI = os.environ.get("TEST_MONGO_URI", "mongodb://localhost:27017")


async def _safe_drop_database(client: AsyncIOMotorClient, db_name: str, retries: int = 3) -> None:  # type: ignore[type-arg]
    """Drop a database with retries to handle IndexBuildAborted races.

    When text indexes are being built (e.g. from taxonomy seeding) and a
    ``dropDatabase`` command arrives concurrently, MongoDB raises an
    ``OperationFailure`` with ``IndexBuildAborted``. Retrying after a brief
    pause lets the index build finish or abort cleanly.
    """
    for attempt in range(retries):
        try:
            await client.drop_database(db_name)
            return
        except OperationFailure:
            if attempt < retries - 1:
                await asyncio.sleep(0.5)
            else:
                raise


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    """Use the default asyncio event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()


_indexes_created = False


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:  # type: ignore[type-arg]
    """Provide a clean, isolated test MongoDB database for each test.

    On first call, drops the database and creates all indexes.
    On subsequent calls, clears all documents (preserving indexes for speed).

    Yields:
        AsyncIOMotorDatabase pointing at ``sentora_test``.
    """
    global _indexes_created

    client: AsyncIOMotorClient = AsyncIOMotorClient(_MONGO_URI)  # type: ignore[type-arg]
    db = client[_TEST_DB_NAME]

    if not _indexes_created:
        # Full drop once to remove stale data from prior runs, then create indexes
        await _safe_drop_database(client, _TEST_DB_NAME)
        from db_indexes import ensure_all_indexes

        await ensure_all_indexes(db)
        _indexes_created = True
    else:
        # Fast path: clear all documents but preserve indexes
        for coll_name in await db.list_collection_names():
            await db[coll_name].delete_many({})

    yield db
    client.close()


@pytest_asyncio.fixture(scope="function")
async def seeded_db(test_db: AsyncIOMotorDatabase) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Provide a test database pre-seeded with the taxonomy seed data.

    Runs the taxonomy seed loader so integration tests have realistic data.

    Args:
        test_db: Clean test database (injected).

    Returns:
        AsyncIOMotorDatabase with taxonomy seed data loaded.
    """
    from domains.taxonomy.seed import seed_taxonomy_if_empty

    await seed_taxonomy_if_empty(test_db)
    return test_db


@pytest_asyncio.fixture(scope="function")
async def client(seeded_db: AsyncIOMotorDatabase) -> AsyncGenerator[AsyncClient, None]:  # type: ignore[type-arg]
    """Provide an HTTPX async test client against the FastAPI app.

    Patches the database dependency so all routes use the isolated test
    database instead of the development database.

    Args:
        seeded_db: Pre-seeded test database (injected).

    Yields:
        An HTTPX AsyncClient configured to talk to the test app.
    """
    import database
    from main import app

    # Patch the global DB reference so the app uses the test database
    original_db = database._client
    # We set the test client directly on the module so get_db() returns it
    database._client = seeded_db.client  # type: ignore[assignment]

    # Override settings so tests always use the test DB and never hit a real S1 tenant.
    # Blanking the token triggers the fail-fast path in SyncManager._run_sync().
    from config import get_settings

    settings = get_settings()
    original_mongo_db = settings.__dict__.get("mongo_db")
    original_s1_token = settings.__dict__.get("s1_api_token")
    object.__setattr__(settings, "mongo_db", _TEST_DB_NAME)
    object.__setattr__(settings, "s1_api_token", "")
    # Disable external API calls in tests (HaveIBeenPwned breach check).
    # The auth router reads from the persisted config (app_config collection),
    # so we seed it with breach checking disabled.
    original_breach_check = settings.__dict__.get("password_check_breached")
    object.__setattr__(settings, "password_check_breached", False)
    await seeded_db["app_config"].update_one(
        {"_id": "global"},
        {"$set": {"password_check_breached": False}},
        upsert=True,
    )

    # Reset rate limiters so tests don't interfere with each other
    from domains.auth.router import (
        _password_change_limiter,
        _refresh_limiter,
        _register_limiter,
        _totp_limiter,
    )

    _register_limiter.reset()
    _refresh_limiter.reset()
    _totp_limiter.reset()
    _password_change_limiter.reset()

    # Reset the global RateLimitMiddleware state (walks the ASGI middleware stack)
    from middleware.rate_limit import RateLimitMiddleware

    _mw_app = app.middleware_stack
    while _mw_app is not None:
        if isinstance(_mw_app, RateLimitMiddleware):
            _mw_app._global_limiter.reset()
            for _limiter in _mw_app._strict_limiters.values():
                _limiter.reset()
            break
        _mw_app = getattr(_mw_app, "app", None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Restore
    database._client = original_db
    if original_mongo_db is not None:
        object.__setattr__(settings, "mongo_db", original_mongo_db)
    if original_s1_token is not None:
        object.__setattr__(settings, "s1_api_token", original_s1_token)
    if original_breach_check is not None:
        object.__setattr__(settings, "password_check_breached", original_breach_check)


@pytest.fixture(scope="function")
def admin_headers() -> dict[str, str]:
    """Provide Authorization headers with an admin JWT for protected routes.

    Returns:
        Dict with ``Authorization: Bearer <token>`` header.
    """
    from domains.auth.service import create_access_token

    token = create_access_token({"sub": "testadmin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def super_admin_headers() -> dict[str, str]:
    """Provide Authorization headers with a super_admin JWT for platform-level routes.

    Returns:
        Dict with ``Authorization: Bearer <token>`` header.
    """
    from domains.auth.service import create_access_token

    token = create_access_token({"sub": "testplatformadmin", "role": "super_admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def analyst_headers() -> dict[str, str]:
    """Provide Authorization headers with an analyst JWT for protected routes.

    Returns:
        Dict with ``Authorization: Bearer <token>`` header.
    """
    from domains.auth.service import create_access_token

    token = create_access_token({"sub": "testanalyst", "role": "analyst"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def viewer_headers() -> dict[str, str]:
    """Provide Authorization headers with a viewer JWT for protected routes.

    Returns:
        Dict with ``Authorization: Bearer <token>`` header.
    """
    from domains.auth.service import create_access_token

    token = create_access_token({"sub": "testviewer", "role": "viewer"})
    return {"Authorization": f"Bearer {token}"}


def make_software_entry(**overrides: object) -> dict[str, object]:
    """Build a minimal valid SoftwareEntry dict for use in tests.

    Args:
        **overrides: Field values to override on the default entry.

    Returns:
        Dict matching the SoftwareEntry schema with sensible defaults.
    """
    defaults: dict[str, Any] = {
        "name": "Test Software",
        "patterns": ["test*software*"],
        "publisher": "Test Publisher",
        "category": "test_category",
        "category_display": "Test Category",
        "subcategory": None,
        "industry": ["testing"],
        "description": "A software entry used in tests",
        "is_universal": False,
        "user_added": True,
    }
    defaults.update(overrides)
    return defaults
