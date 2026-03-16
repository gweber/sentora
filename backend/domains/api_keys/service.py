"""API Keys domain service — key generation, CRUD, validation, and rotation."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from domains.api_keys import repository
from domains.api_keys.dto import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyCurrentResponse,
    APIKeyResponse,
    APIKeyRotateResponse,
    APIKeyUpdateRequest,
)
from domains.api_keys.entities import AVAILABLE_SCOPES, APIKey
from errors import APIKeyError, APIKeyNotFoundError, APIKeyScopeError
from utils.dt import utc_now

#: Grace period after rotation during which the old key remains valid.
_ROTATION_GRACE_MINUTES = 5


# ── Key generation ───────────────────────────────────────────────────────────


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash).
        The full_key is shown once to the user and never stored.
    """
    random_part = secrets.token_hex(24)  # 48 hex chars, 192 bits entropy
    full_key = f"sentora_sk_live_{random_part}"
    key_prefix = full_key[:20]  # "sentora_sk_live_a8f3" — for UI identification
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_prefix, key_hash


def hash_key(key: str) -> str:
    """Compute the SHA-256 hash of a raw API key."""
    return hashlib.sha256(key.encode()).hexdigest()


# ── Converters ───────────────────────────────────────────────────────────────


def _entity_to_response(entity: APIKey) -> APIKeyResponse:
    """Convert an APIKey entity to its API response DTO."""
    return APIKeyResponse(
        id=entity.id,
        tenant_id=entity.tenant_id,
        name=entity.name,
        description=entity.description,
        key_prefix=entity.key_prefix,
        scopes=entity.scopes,
        rate_limit_per_minute=entity.rate_limit_per_minute,
        rate_limit_per_hour=entity.rate_limit_per_hour,
        created_at=entity.created_at,
        created_by=entity.created_by,
        expires_at=entity.expires_at,
        last_used_at=entity.last_used_at,
        last_used_ip=entity.last_used_ip,
        is_active=entity.is_active,
        revoked_at=entity.revoked_at,
        revoked_by=entity.revoked_by,
    )


# ── Scope validation ────────────────────────────────────────────────────────


def _validate_scopes(scopes: list[str]) -> None:
    """Raise APIKeyScopeError if any scope is not recognized."""
    invalid = set(scopes) - set(AVAILABLE_SCOPES)
    if invalid:
        raise APIKeyScopeError(
            f"Invalid scope(s): {', '.join(sorted(invalid))}. "
            f"Valid scopes: {', '.join(sorted(AVAILABLE_SCOPES))}"
        )


# ── CRUD ─────────────────────────────────────────────────────────────────────


async def create_api_key(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    req: APIKeyCreateRequest,
    *,
    tenant_id: str,
    created_by: str,
) -> APIKeyCreateResponse:
    """Create a new API key. Returns the full key exactly once."""
    _validate_scopes(req.scopes)

    full_key, key_prefix, key_hash = generate_api_key()
    now = utc_now()

    entity = APIKey(
        id=str(ObjectId()),
        tenant_id=tenant_id,
        name=req.name,
        description=req.description,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=req.scopes,
        rate_limit_per_minute=req.rate_limit_per_minute,
        rate_limit_per_hour=req.rate_limit_per_hour,
        created_at=now,
        created_by=created_by,
        expires_at=req.expires_at,
    )
    await repository.create(db, entity)

    await audit(
        db,
        domain="api_keys",
        action="api_key.created",
        actor=created_by,
        summary=f"API key '{req.name}' created with scopes: {', '.join(req.scopes)}",
        details={"api_key_id": entity.id, "scopes": req.scopes, "name": req.name},
    )

    return APIKeyCreateResponse(
        key=_entity_to_response(entity),
        full_key=full_key,
    )


async def list_api_keys(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    tenant_id: str,
) -> list[APIKeyResponse]:
    """List all API keys for a tenant."""
    keys = await repository.list_by_tenant(db, tenant_id)
    return [_entity_to_response(k) for k in keys]


async def get_api_key(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
    tenant_id: str,
) -> APIKeyResponse:
    """Get a single API key by ID."""
    entity = await repository.find_by_id(db, key_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise APIKeyNotFoundError(f"API key '{key_id}' not found")
    return _entity_to_response(entity)


async def update_api_key(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
    req: APIKeyUpdateRequest,
    *,
    tenant_id: str,
    updated_by: str,
) -> APIKeyResponse:
    """Update an API key's metadata (not the key itself)."""
    entity = await repository.find_by_id(db, key_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise APIKeyNotFoundError(f"API key '{key_id}' not found")

    if not entity.is_active:
        raise APIKeyError("Cannot update a revoked API key")

    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.scopes is not None:
        _validate_scopes(req.scopes)
        updates["scopes"] = req.scopes
    if req.rate_limit_per_minute is not None:
        updates["rate_limit_per_minute"] = req.rate_limit_per_minute
    if req.rate_limit_per_hour is not None:
        updates["rate_limit_per_hour"] = req.rate_limit_per_hour
    if req.expires_at is not None:
        updates["expires_at"] = req.expires_at

    if updates:
        await repository.update(db, key_id, updates)
        await audit(
            db,
            domain="api_keys",
            action="api_key.updated",
            actor=updated_by,
            summary=f"API key '{entity.name}' updated",
            details={"api_key_id": key_id, "fields": list(updates.keys())},
        )

    updated = await repository.find_by_id(db, key_id)
    if updated is None:
        raise APIKeyNotFoundError(f"API key '{key_id}' not found")
    return _entity_to_response(updated)


async def revoke_api_key(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
    *,
    tenant_id: str,
    revoked_by: str,
) -> None:
    """Revoke an API key immediately."""
    entity = await repository.find_by_id(db, key_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise APIKeyNotFoundError(f"API key '{key_id}' not found")

    now = utc_now()
    await repository.update(
        db,
        key_id,
        {
            "is_active": False,
            "revoked_at": now,
            "revoked_by": revoked_by,
        },
    )

    await audit(
        db,
        domain="api_keys",
        action="api_key.revoked",
        actor=revoked_by,
        summary=f"API key '{entity.name}' revoked",
        details={"api_key_id": key_id, "name": entity.name},
    )


async def rotate_api_key(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
    *,
    tenant_id: str,
    rotated_by: str,
) -> APIKeyRotateResponse:
    """Rotate an API key: create a new key, revoke the old one with a grace period."""
    entity = await repository.find_by_id(db, key_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise APIKeyNotFoundError(f"API key '{key_id}' not found")

    if not entity.is_active:
        raise APIKeyError("Cannot rotate a revoked API key")

    now = utc_now()
    grace_expires = now + timedelta(minutes=_ROTATION_GRACE_MINUTES)

    # Revoke old key with grace period
    await repository.update(
        db,
        key_id,
        {
            "is_active": False,
            "revoked_at": now,
            "revoked_by": rotated_by,
            "grace_expires_at": grace_expires,
        },
    )

    # Generate new key with same configuration
    full_key, key_prefix, key_hash = generate_api_key()
    new_entity = APIKey(
        id=str(ObjectId()),
        tenant_id=entity.tenant_id,
        name=entity.name,
        description=entity.description,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=entity.scopes,
        rate_limit_per_minute=entity.rate_limit_per_minute,
        rate_limit_per_hour=entity.rate_limit_per_hour,
        created_at=now,
        created_by=rotated_by,
        expires_at=entity.expires_at,
        rotated_from_id=entity.id,
    )
    await repository.create(db, new_entity)

    await audit(
        db,
        domain="api_keys",
        action="api_key.rotated",
        actor=rotated_by,
        summary=f"API key '{entity.name}' rotated (old key valid for {_ROTATION_GRACE_MINUTES}min)",
        details={
            "old_key_id": key_id,
            "new_key_id": new_entity.id,
            "grace_minutes": _ROTATION_GRACE_MINUTES,
        },
    )

    return APIKeyRotateResponse(
        key=_entity_to_response(new_entity),
        full_key=full_key,
    )


async def get_current_key_info(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    key_id: str,
) -> APIKeyCurrentResponse:
    """Return self-info for an authenticated API key."""
    entity = await repository.find_by_id(db, key_id)
    if entity is None:
        raise APIKeyNotFoundError("API key not found")
    return APIKeyCurrentResponse(
        id=entity.id,
        name=entity.name,
        key_prefix=entity.key_prefix,
        scopes=entity.scopes,
        rate_limit_per_minute=entity.rate_limit_per_minute,
        rate_limit_per_hour=entity.rate_limit_per_hour,
        last_used_at=entity.last_used_at,
    )
