"""Unit tests for SSO user provisioning.

Tests username derivation and uniqueness enforcement logic extracted
from the shared SSO provisioning module.
"""

from __future__ import annotations

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.auth.sso_provisioning import (
    _derive_username,
    _ensure_unique_username,
)

# ── _derive_username ────────────────────────────────────────────────────────


def test_derive_username_from_preferred_username() -> None:
    """Preferred username takes precedence, stripped of @domain."""
    claims = {"preferred_username": "jdoe@corp.example.com", "email": "john@corp.example.com"}
    assert _derive_username(claims) == "jdoe"


def test_derive_username_from_email_when_no_preferred() -> None:
    """Falls back to email local part when preferred_username is absent."""
    claims = {"email": "alice@example.com"}
    assert _derive_username(claims) == "alice"


def test_derive_username_from_display_name() -> None:
    """Falls back to lowercased, dotted display name when no email."""
    claims = {"name": "John Doe"}
    assert _derive_username(claims) == "john.doe"


def test_derive_username_from_subject_id() -> None:
    """Falls back to truncated subject ID as last resort."""
    claims = {"sub": "abc123def456xyz"}
    result = _derive_username(claims)
    assert result == "sso_abc123def456"


def test_derive_username_empty_claims() -> None:
    """Generates a random sso_ prefix when all claims are empty."""
    result = _derive_username({})
    assert result.startswith("sso_")


def test_derive_username_preferred_username_is_just_at() -> None:
    """Handles edge case where preferred_username is just '@domain'."""
    claims = {"preferred_username": "@example.com", "email": "fallback@example.com"}
    # local part is empty, falls through to email
    assert _derive_username(claims) == "fallback"


# ── _ensure_unique_username ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unique_username_no_conflict(test_db: AsyncIOMotorDatabase) -> None:
    """Returns the base username when no conflict exists."""
    result = await _ensure_unique_username(test_db, "alice")
    assert result == "alice"


@pytest.mark.asyncio
async def test_unique_username_with_conflict(test_db: AsyncIOMotorDatabase) -> None:
    """Appends numeric suffix when the base username is taken."""
    await test_db["users"].insert_one(
        {"username": "alice", "email": "alice@test.com", "role": "viewer"}
    )
    result = await _ensure_unique_username(test_db, "alice")
    assert result == "alice1"


@pytest.mark.asyncio
async def test_unique_username_multiple_conflicts(test_db: AsyncIOMotorDatabase) -> None:
    """Keeps incrementing suffix until unique."""
    await test_db["users"].insert_many(
        [
            {"username": "bob", "email": "bob@test.com", "role": "viewer"},
            {"username": "bob1", "email": "bob1@test.com", "role": "viewer"},
            {"username": "bob2", "email": "bob2@test.com", "role": "viewer"},
        ]
    )
    result = await _ensure_unique_username(test_db, "bob")
    assert result == "bob3"
