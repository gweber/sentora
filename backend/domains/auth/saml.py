"""SAML 2.0 Service Provider implementation.

Provides SP-initiated SSO alongside the existing OIDC integration.
Uses the python3-saml library for SAML assertion handling.

When python3-saml is not installed, all functions raise ImportError
gracefully so the rest of the app continues to work.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings

# ── Conditional python3-saml import ──────────────────────────────────────────

try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # type: ignore[import-untyped]
    from onelogin.saml2.utils import OneLogin_Saml2_Utils  # type: ignore[import-untyped]

    SAML_AVAILABLE = True
except ImportError:
    SAML_AVAILABLE = False

# ── IdP metadata cache ───────────────────────────────────────────────────────

_idp_metadata_cache: dict[str, Any] = {}
_idp_metadata_cache_ts: float = 0.0
_IDP_METADATA_CACHE_TTL: float = 3600.0  # 1 hour

_cache_lock = asyncio.Lock()

# ── CSRF request-ID tracking — stored in MongoDB for multi-worker support ────


def _check_saml_available() -> None:
    """Raise ImportError if python3-saml is not installed."""
    if not SAML_AVAILABLE:
        raise ImportError(
            "python3-saml is not installed. Install it with: pip install python3-saml"
        )


# ── IdP metadata fetching ───────────────────────────────────────────────────


async def _fetch_idp_metadata() -> dict[str, Any]:
    """Fetch and cache the IdP metadata from the configured URL.

    The metadata document provides the IdP's SSO endpoint, certificate,
    and NameID format.

    Returns:
        Parsed metadata as a dict suitable for python3-saml settings.
    """
    global _idp_metadata_cache, _idp_metadata_cache_ts  # noqa: PLW0603

    async with _cache_lock:
        # Double-check after acquiring lock
        now = time.monotonic()
        if _idp_metadata_cache and (now - _idp_metadata_cache_ts) < _IDP_METADATA_CACHE_TTL:
            return _idp_metadata_cache

        settings = get_settings()
        url = settings.saml_idp_metadata_url
        if not url:
            raise ValueError("SAML_IDP_METADATA_URL is not configured")

        logger.info("Fetching SAML IdP metadata from {}", url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            metadata_xml = resp.text

        _check_saml_available()

        # Parse metadata XML using python3-saml utilities
        idp_data = OneLogin_Saml2_Utils.parse_remote_idp_metadata(metadata_xml)

        if not idp_data:
            raise ValueError("Failed to parse SAML IdP metadata")

        _idp_metadata_cache = idp_data
        _idp_metadata_cache_ts = now
        logger.debug("SAML IdP metadata cached — entityId={}", idp_data.get("entityId", "unknown"))
        return idp_data


def _read_pem_or_file(value: str) -> str:
    """Read a PEM string directly or from a file path.

    If the value starts with ``-----BEGIN``, it's treated as a PEM string.
    Otherwise, it's treated as a file path and the contents are read.

    Args:
        value: PEM string or file path.

    Returns:
        The PEM content as a string.
    """
    if not value:
        return ""
    value = value.strip()
    if value.startswith("-----BEGIN"):
        return value
    # Treat as file path
    try:
        from pathlib import Path

        return Path(value).read_text().strip()
    except Exception as exc:
        logger.warning("Failed to read PEM file {}: {}", value, exc)
        return ""


def _load_saml_settings(http_host: str) -> dict[str, Any]:
    """Build the python3-saml settings dict from configuration.

    Args:
        http_host: The HTTP host header (e.g. ``localhost:5002``).

    Returns:
        Settings dict for ``OneLogin_Saml2_Auth``.
    """
    _check_saml_available()

    settings = get_settings()

    sp_entity_id = settings.saml_sp_entity_id or f"https://{http_host}/api/v1/auth/saml/metadata"
    sp_acs_url = settings.saml_sp_acs_url or f"https://{http_host}/api/v1/auth/saml/callback"

    sp_cert = _read_pem_or_file(settings.saml_sp_cert)
    sp_key = _read_pem_or_file(settings.saml_sp_key)

    saml_settings: dict[str, Any] = {
        "strict": True,
        "debug": settings.is_development,
        "sp": {
            "entityId": sp_entity_id,
            "assertionConsumerService": {
                "url": sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": settings.saml_name_id_format,
        },
        "security": {
            "authnRequestsSigned": bool(sp_cert and sp_key),
            "wantAssertionsSigned": True,
            "wantNameIdEncrypted": False,
            "signMetadata": bool(sp_cert and sp_key),
        },
    }

    if sp_cert:
        saml_settings["sp"]["x509cert"] = sp_cert
    if sp_key:
        saml_settings["sp"]["privateKey"] = sp_key

    return saml_settings


async def _build_full_settings(http_host: str) -> dict[str, Any]:
    """Build full python3-saml settings including fetched IdP metadata.

    Args:
        http_host: The HTTP host header.

    Returns:
        Complete settings dict for ``OneLogin_Saml2_Auth``.
    """
    saml_settings = _load_saml_settings(http_host)
    idp_data = await _fetch_idp_metadata()
    saml_settings["idp"] = idp_data
    return saml_settings


def _prepare_request_data(
    http_host: str, script_name: str = "", post_data: dict | None = None
) -> dict[str, Any]:
    """Build the request data dict expected by OneLogin_Saml2_Auth.

    Args:
        http_host: The HTTP host header.
        script_name: The WSGI script name / path prefix.
        post_data: POST data for callback processing.

    Returns:
        Request dict for ``OneLogin_Saml2_Auth.__init__``.
    """
    # Determine scheme from host or default to https
    scheme = "https"
    if http_host.startswith("localhost") or http_host.startswith("127.0.0.1"):
        scheme = "http"

    return {
        "https": "on" if scheme == "https" else "off",
        "http_host": http_host,
        "script_name": script_name,
        "server_port": "443" if scheme == "https" else "80",
        "get_data": {},
        "post_data": post_data or {},
    }


# ── Public API ───────────────────────────────────────────────────────────────


async def get_auth_request_url(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    http_host: str,
    script_name: str = "",
) -> str:
    """Create a SAML authentication request and return the redirect URL.

    Generates the AuthnRequest XML, stores the request ID in MongoDB for
    later validation, and returns the IdP login URL.

    Args:
        db: Motor database instance.
        http_host: The HTTP host header (e.g. ``localhost:5002``).
        script_name: The WSGI script name / path prefix.

    Returns:
        The full URL to redirect the user to for IdP authentication.

    Raises:
        ImportError: If python3-saml is not installed.
        ValueError: If SAML configuration is invalid.
    """
    _check_saml_available()

    full_settings = await _build_full_settings(http_host)
    request_data = _prepare_request_data(http_host, script_name)

    auth = OneLogin_Saml2_Auth(request_data, full_settings)
    redirect_url = auth.login()

    # Store the request ID in MongoDB for validation during callback
    request_id = auth.get_last_request_id()
    if request_id:
        await db["saml_pending_requests"].insert_one(
            {"_id": request_id, "created_at": datetime.now(UTC)}
        )
        logger.debug("SAML AuthnRequest created — request_id={}", request_id)

    return redirect_url


async def process_response(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    http_host: str,
    post_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate a SAML response and extract user claims.

    Processes the SAML assertion from the IdP callback, validates
    the signature and conditions, and extracts normalized user claims.

    Args:
        db: Motor database instance.
        http_host: The HTTP host header.
        post_data: The form POST data from the IdP callback.

    Returns:
        Normalized claims dict with keys: ``sub``, ``email``, ``name``,
        ``preferred_username``.

    Raises:
        ImportError: If python3-saml is not installed.
        ValueError: If the SAML response is invalid.
    """
    _check_saml_available()

    full_settings = await _build_full_settings(http_host)
    request_data = _prepare_request_data(http_host, post_data=post_data)

    auth = OneLogin_Saml2_Auth(request_data, full_settings)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        error_reason = auth.get_last_error_reason() or ", ".join(errors)
        logger.error("SAML response validation failed: {}", error_reason)
        raise ValueError(f"SAML response validation failed: {error_reason}")

    if not auth.is_authenticated():
        raise ValueError("SAML authentication failed — user is not authenticated")

    # Validate the InResponseTo matches a pending request (atomic check-and-consume)
    response_in_response_to = auth.get_last_response_in_response_to()
    if response_in_response_to:
        doc = await db["saml_pending_requests"].find_one_and_delete(
            {"_id": response_in_response_to}
        )
        if doc is None:
            raise ValueError(
                f"SAML response with unknown or expired InResponseTo: {response_in_response_to}"
            )
    else:
        raise ValueError("SAML response missing InResponseTo — unsolicited assertions are rejected")

    # Extract claims
    name_id = auth.get_nameid()
    attributes = auth.get_attributes()

    # Check if the SAML assertion contains an email verification attribute
    email_verified_attrs = [
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailverified",
        "urn:oid:1.3.6.1.4.1.5923.1.1.1.11",
        "emailVerified",
        "email_verified",
    ]
    email_verified = False
    for attr in email_verified_attrs:
        values = attributes.get(attr, [])
        if values:
            email_verified = str(values[0]).lower() in ("true", "1", "yes")
            break

    # Normalize claims to a consistent dict (same shape as OIDC claims)
    claims: dict[str, Any] = {
        "sub": name_id or "",
        "email": "",
        "email_verified": email_verified,
        "name": "",
        "preferred_username": "",
    }

    # Extract email — check multiple common attribute names
    email_attrs = [
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "urn:oid:0.9.2342.19200300.100.1.3",  # mail
        "email",
        "Email",
        "mail",
    ]
    for attr in email_attrs:
        values = attributes.get(attr, [])
        if values:
            claims["email"] = values[0]
            break

    # If NameID is an email and no email attribute found, use NameID
    if not claims["email"] and name_id and "@" in name_id:
        claims["email"] = name_id

    # Extract display name
    name_attrs = [
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "urn:oid:2.16.840.1.113730.3.1.241",  # displayName
        "displayName",
        "name",
    ]
    for attr in name_attrs:
        values = attributes.get(attr, [])
        if values:
            claims["name"] = values[0]
            break

    # Extract username
    username_attrs = [
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
        "urn:oid:0.9.2342.19200300.100.1.1",  # uid
        "preferred_username",
        "username",
        "uid",
    ]
    for attr in username_attrs:
        values = attributes.get(attr, [])
        if values:
            claims["preferred_username"] = values[0]
            break

    logger.info(
        "SAML response processed — sub={}, email={}",
        claims["sub"],
        claims.get("email"),
    )
    return claims


async def store_token_exchange(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    nonce: str,
    access_token: str,
    refresh_token: str,
) -> None:
    """Store JWT tokens server-side keyed by a one-time nonce for SAML exchange.

    The nonce is used by the frontend to retrieve the actual tokens after the
    SAML callback redirect. A TTL index on the collection auto-expires entries.

    Args:
        db: Motor database handle.
        nonce: The one-time random nonce (used as document _id).
        access_token: The JWT access token to store.
        refresh_token: The JWT refresh token to store.
    """
    await db["saml_token_exchange"].insert_one(
        {
            "_id": nonce,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "created_at": datetime.now(UTC),
        }
    )


async def consume_token_exchange(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    nonce: str,
) -> dict[str, Any] | None:
    """Atomically consume a one-time SAML token exchange nonce.

    Finds and deletes the exchange document in a single atomic operation,
    preventing nonce reuse.

    Args:
        db: Motor database handle.
        nonce: The one-time nonce to consume.

    Returns:
        The exchange document (with access_token, refresh_token) if found,
        None if the nonce is invalid, expired, or already consumed.
    """
    return await db["saml_token_exchange"].find_one_and_delete({"_id": nonce})


def generate_sp_metadata(http_host: str) -> str:
    """Generate SP metadata XML for IdP registration.

    Args:
        http_host: The HTTP host header.

    Returns:
        SP metadata as an XML string.

    Raises:
        ImportError: If python3-saml is not installed.
    """
    _check_saml_available()

    saml_settings = _load_saml_settings(http_host)

    # Provide a minimal IdP stub so OneLogin_Saml2_Auth can initialize
    saml_settings.setdefault(
        "idp",
        {
            "entityId": "https://stub.invalid",
            "singleSignOnService": {
                "url": "https://stub.invalid/sso",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
        },
    )

    request_data = _prepare_request_data(http_host)
    auth = OneLogin_Saml2_Auth(request_data, saml_settings)
    metadata = auth.get_settings().get_sp_metadata()

    errors = auth.get_settings().validate_metadata(metadata)
    if errors:
        logger.warning("SP metadata validation warnings: {}", errors)

    return metadata
