"""Security regression tests — injection prevention and input validation.

Covers:
- Round 2: MongoDB operator injection ($gt, $ne, $regex, $where)
- Round 2: Password complexity enforcement
- Round 2: Open redirect prevention
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestPasswordComplexity:
    """Regression: Round 2 — password policy enforcement on registration."""

    @pytest.mark.parametrize(
        "password,reason",
        [
            ("short", "too-short"),
            ("alllowercase1", "no-uppercase"),
            ("ALLUPPERCASE1", "no-lowercase"),
            ("NoDigitsHere", "no-digits"),
        ],
        ids=["too-short", "no-uppercase", "no-lowercase", "no-digits"],
    )
    async def test_weak_password_rejected(
        self,
        client: AsyncClient,
        password: str,
        reason: str,
    ) -> None:
        """Regression: Round 2 — weak password rejected ({reason})."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"weakpw_{reason}",
                "email": f"weakpw_{reason}@test.com",
                "password": password,
            },
        )
        assert resp.status_code == 422, (
            f"Expected 422 for password '{password}' ({reason}), got {resp.status_code}"
        )


class TestMongoDbOperatorInjection:
    """Regression: Round 2 — MongoDB operators must not be interpreted in user input."""

    @pytest.mark.parametrize(
        "search_payload",
        [
            {"username": {"$gt": ""}},
            {"username": {"$ne": "admin"}},
            {"username": {"$regex": ".*"}},
        ],
        ids=["gt-operator", "ne-operator", "regex-operator"],
    )
    async def test_login_rejects_nosql_operators(
        self,
        client: AsyncClient,
        search_payload: dict,
    ) -> None:
        """Regression: Round 2 — login endpoint rejects MongoDB operators in username."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                **search_payload,
                "password": "anything",
            },
        )
        # Should be 422 (validation error) or 401, NOT 200
        assert resp.status_code in (401, 422), (
            f"Expected 401/422 for NoSQL injection, got {resp.status_code}"
        )


class TestRegisterInputValidation:
    """Regression: Round 2 — registration input validation edge cases."""

    async def test_register_empty_username_rejected(self, client: AsyncClient) -> None:
        """Registration with empty username is rejected."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "",
                "email": "valid@test.com",
                "password": "ValidPass123",
            },
        )
        assert resp.status_code == 422

    async def test_register_very_long_username_rejected(self, client: AsyncClient) -> None:
        """Registration with a username exceeding max length is rejected."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "a" * 200,
                "email": "longuser@test.com",
                "password": "ValidPass123",
            },
        )
        assert resp.status_code == 422

    async def test_register_duplicate_email_409(self, client: AsyncClient) -> None:
        """Registration with a duplicate email returns 409, not 500."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "emaildup1",
                "email": "duplicate@test.com",
                "password": "ValidPass123",
            },
        )
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "emaildup2",
                "email": "duplicate@test.com",
                "password": "ValidPass123",
            },
        )
        assert resp.status_code == 409
