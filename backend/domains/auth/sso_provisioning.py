"""Shared SSO user provisioning for OIDC and SAML providers.

Handles user creation/linking logic common to all SSO flows:
username derivation, uniqueness enforcement, and account matching.
"""

from __future__ import annotations

import secrets
from typing import Any

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings

from .entities import User, UserRole
from .service import _doc_to_user


async def provision_sso_user(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    claims: dict[str, Any],
    provider_field: str,
    provider_value: str,
) -> User:
    """Find an existing user by SSO provider field or email, or create a new one.

    Matching priority:
    1. Match by ``provider_field`` (stable identifier from the IdP).
    2. Match by ``email`` (links pre-existing local accounts to SSO).
    3. Create a new user if no match is found.

    When linking by email, the provider field is set on the existing account
    so subsequent logins use the stable subject identifier.

    Args:
        db: Motor database instance.
        claims: Validated SSO claims (must contain at minimum a subject).
        provider_field: The field name for the provider subject, e.g.
            ``"oidc_subject"`` or ``"saml_subject"``.
        provider_value: The IdP-provided identifier value.

    Returns:
        The matched or newly created User entity.
    """
    settings = get_settings()
    email = claims.get("email", "")

    # Determine default role setting based on provider
    if provider_field == "saml_subject":
        default_role_str = settings.saml_default_role
    else:
        default_role_str = settings.oidc_default_role

    # 1. Find by provider subject
    doc = await db["users"].find_one({provider_field: provider_value})
    if doc:
        logger.debug("SSO login — matched user by {}: {}", provider_field, doc["username"])
        return _doc_to_user(doc)

    # 2. Find by email (link existing account) — only if email is verified
    if email and claims.get("email_verified") is True:
        doc = await db["users"].find_one({"email": email})
        if doc:
            # Only link if the user has no existing SSO identity for this provider
            if not doc.get(provider_field):
                await db["users"].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {provider_field: provider_value}},
                )
                logger.info(
                    "SSO login — linked existing user '{}' to {} {}",
                    doc["username"],
                    provider_field,
                    provider_value,
                )
                doc[provider_field] = provider_value
                return _doc_to_user(doc)
            # User already has a different SSO identity — don't overwrite, create new account
            logger.warning(
                "SSO email match for '{}' but user already has {} set — creating new account",
                email,
                provider_field,
            )

    # 3. Create a new user
    username = _derive_username(claims)
    username = await _ensure_unique_username(db, username)

    # Atomically claim first-user status to auto-promote the first registrant
    from .first_user import claim_first_user

    first_user_role = await claim_first_user(db, username)
    if first_user_role != UserRole.viewer:
        # First user — use the elevated role
        role = first_user_role
    else:
        # Non-first user — use the SSO provider's default role
        try:
            role = UserRole(default_role_str)
        except ValueError:
            logger.warning(
                "Invalid SSO default role '{}', falling back to 'viewer'", default_role_str
            )
            role = UserRole.viewer

    import pymongo.errors

    new_doc: dict[str, Any] = {
        "username": username,
        "email": email or f"{username}@sso.local",
        "hashed_password": "",  # SSO users have no local password
        "role": role.value,
        "disabled": False,
        "totp_secret": None,
        "totp_enabled": False,
        provider_field: provider_value,
    }
    # Retry with a new username suffix on duplicate key collision
    for _attempt in range(5):
        try:
            result = await db["users"].insert_one(new_doc)
            break
        except pymongo.errors.DuplicateKeyError:
            username = f"{username}_{secrets.token_urlsafe(4)}"
            new_doc["username"] = username
            new_doc["email"] = email or f"{username}@sso.local"
    else:
        # All retries exhausted — generate a fully random username
        username = f"sso_{secrets.token_urlsafe(8)}"
        new_doc["username"] = username
        new_doc["email"] = email or f"{username}@sso.local"
        result = await db["users"].insert_one(new_doc)

    logger.info(
        "SSO login — created new user '{}' (role={}, {}={})",
        username,
        role.value,
        provider_field,
        provider_value,
    )

    return User(
        id=str(result.inserted_id),
        username=username,
        email=new_doc["email"],
        role=role,
        disabled=False,
        hashed_password="",
        totp_secret=None,
        totp_enabled=False,
        oidc_subject=new_doc.get("oidc_subject"),
        saml_subject=new_doc.get("saml_subject"),
    )


def _derive_username(claims: dict[str, Any]) -> str:
    """Derive a username from SSO claims, preferring human-readable values."""
    preferred_username = claims.get("preferred_username", "")
    email = claims.get("email", "")
    display_name = claims.get("name", "")
    sub = claims.get("sub", "")

    if preferred_username:
        name = preferred_username.split("@")[0]
        if name:
            return name

    if email:
        name = email.split("@")[0]
        if name:
            return name

    if display_name:
        return display_name.lower().replace(" ", ".")

    # Last resort — use a truncated subject ID
    return f"sso_{sub[:12]}" if sub else f"sso_{secrets.token_urlsafe(6)}"


async def _ensure_unique_username(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    base_username: str,
) -> str:
    """Ensure a username is unique by appending a numeric suffix if needed."""
    username = base_username
    suffix = 1
    while await db["users"].find_one({"username": username}):
        username = f"{base_username}{suffix}"
        suffix += 1
        if suffix > 100:
            username = f"sso_{secrets.token_urlsafe(8)}"
            break
    return username
