"""Tests for the atomic first-user claim logic."""

from __future__ import annotations

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from domains.auth.entities import UserRole
from domains.auth.first_user import claim_first_user

_MONGO_URI = "mongodb://localhost:27017"
_TEST_DB = "sentora_test_first_user"


@pytest_asyncio.fixture(scope="function")
async def db():  # noqa: ANN201
    """Provide a clean test database for each test."""
    client = AsyncIOMotorClient(_MONGO_URI)
    _db = client[_TEST_DB]
    await client.drop_database(_TEST_DB)
    yield _db
    await client.drop_database(_TEST_DB)
    client.close()


@pytest.mark.asyncio
async def test_first_user_gets_elevated_role(db: AsyncIOMotorDatabase) -> None:
    """The very first user to register should be promoted (not viewer)."""
    role = await claim_first_user(db, "alice")
    # In on-prem mode (default), first user gets admin
    assert role in (UserRole.admin, UserRole.super_admin)


@pytest.mark.asyncio
async def test_second_user_gets_viewer(db: AsyncIOMotorDatabase) -> None:
    """The second registration should get viewer role."""
    await claim_first_user(db, "first_user")
    role = await claim_first_user(db, "second_user")
    assert role == UserRole.viewer


@pytest.mark.asyncio
async def test_claim_is_idempotent(db: AsyncIOMotorDatabase) -> None:
    """Multiple claims after the first should all return viewer."""
    await claim_first_user(db, "user1")
    for i in range(5):
        role = await claim_first_user(db, f"user{i + 2}")
        assert role == UserRole.viewer
