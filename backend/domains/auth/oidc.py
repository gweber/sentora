"""OIDC / SSO service — OpenID Connect authentication flow.

Supports any OIDC-compliant identity provider (Azure AD, Okta, Google Workspace,
Keycloak, etc.) via standard discovery document auto-configuration.

The flow:
1. Frontend redirects user to ``GET /api/v1/auth/oidc/login``
2. Backend returns the OIDC provider's authorization URL
3. User authenticates with the IdP and is redirected to ``/api/v1/auth/oidc/callback``
4. Backend exchanges the authorization code for tokens, validates the ID token,
   creates or finds the local user, and issues Sentora JWT tokens.

Completely opt-in — disabled by default (``OIDC_ENABLED=false``).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings

from .entities import User
from .sso_provisioning import provision_sso_user

# ── Discovery document cache ────────────────────────────────────────────────

_discovery_cache: dict[str, Any] = {}
_discovery_cache_ts: float = 0.0
_DISCOVERY_CACHE_TTL: float = 3600.0  # 1 hour

_jwks_cache: dict[str, Any] = {}
_jwks_cache_ts: float = 0.0
_JWKS_CACHE_TTL: float = 3600.0  # 1 hour

_cache_lock = asyncio.Lock()


async def _fetch_discovery() -> dict[str, Any]:
    """Fetch and cache the OIDC discovery document.

    The discovery document (``/.well-known/openid-configuration``) tells us
    the authorization, token, JWKS, and userinfo endpoints.
    """
    global _discovery_cache, _discovery_cache_ts  # noqa: PLW0603

    async with _cache_lock:
        # Double-check after acquiring lock (another coroutine may have refreshed)
        now = time.monotonic()
        if _discovery_cache and (now - _discovery_cache_ts) < _DISCOVERY_CACHE_TTL:
            return _discovery_cache

        settings = get_settings()
        url = settings.oidc_discovery_url
        if not url:
            raise ValueError("OIDC_DISCOVERY_URL is not configured")

        logger.info("Fetching OIDC discovery document from {}", url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            doc = resp.json()

        # Validate required fields
        for field in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"):
            if field not in doc:
                raise ValueError(f"OIDC discovery document missing required field: {field}")

        _discovery_cache = doc
        _discovery_cache_ts = now
        logger.debug("OIDC discovery cached — issuer={}", doc.get("issuer"))
        return doc


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch and cache the JWKS (JSON Web Key Set) from the OIDC provider.

    Used to validate the signature of ID tokens without needing the client secret.
    """
    global _jwks_cache, _jwks_cache_ts  # noqa: PLW0603

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_cache_ts) < _JWKS_CACHE_TTL:
        return _jwks_cache

    async with _cache_lock:
        # Double-check after acquiring lock
        now = time.monotonic()
        if _jwks_cache and (now - _jwks_cache_ts) < _JWKS_CACHE_TTL:
            return _jwks_cache

        discovery = await _fetch_discovery()
        jwks_uri = discovery["jwks_uri"]

        logger.debug("Fetching JWKS from {}", jwks_uri)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(jwks_uri)
            resp.raise_for_status()
            jwks = resp.json()

        _jwks_cache = jwks
        _jwks_cache_ts = now
        return jwks


# ── Authorization URL ────────────────────────────────────────────────────────


async def get_authorization_url(db: AsyncIOMotorDatabase) -> str:  # type: ignore[type-arg]
    """Build the OIDC authorization URL for redirecting the user to the IdP.

    Generates a random ``state`` parameter for CSRF protection and stores it
    in MongoDB (``oidc_pending_states`` collection) so that any worker can
    validate the callback.

    Args:
        db: Motor database instance.

    Returns:
        The full authorization URL to redirect the user to.
    """
    settings = get_settings()
    discovery = await _fetch_discovery()

    state = secrets.token_urlsafe(32)

    # Generate PKCE code verifier and challenge (RFC 7636)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )

    await db["oidc_pending_states"].insert_one(
        {
            "_id": state,
            "created_at": datetime.now(UTC),
            "code_verifier": code_verifier,
        }
    )

    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_endpoint = discovery["authorization_endpoint"]
    url = httpx.URL(auth_endpoint, params=params)
    logger.debug("Built OIDC authorization URL for client_id={}", settings.oidc_client_id)
    return str(url)


async def validate_state(db: AsyncIOMotorDatabase, state: str) -> dict[str, Any] | None:  # type: ignore[type-arg]
    """Validate and consume a CSRF state token.

    Atomically finds and deletes the state from MongoDB. Returns the state
    document (containing the PKCE ``code_verifier``) if valid, None otherwise.
    Expiry is handled by a TTL index on the ``oidc_pending_states`` collection.

    Args:
        db: Motor database instance.
        state: The state parameter from the OIDC callback.

    Returns:
        The state document dict if valid, None otherwise.
    """
    doc = await db["oidc_pending_states"].find_one_and_delete({"_id": state})
    if doc is None:
        logger.warning("OIDC callback with unknown or expired state parameter")
        return None

    return doc


# ── Code exchange + ID token validation ──────────────────────────────────────


async def exchange_code(code: str, *, code_verifier: str | None = None) -> dict[str, Any]:
    """Exchange an authorization code for tokens and validate the ID token.

    Performs the standard OIDC token exchange, then validates the ID token's
    signature using the provider's JWKS.

    Args:
        code: The authorization code from the callback.
        code_verifier: PKCE code verifier to include in the token request.

    Returns:
        The decoded and validated ID token claims.

    Raises:
        ValueError: If the token exchange fails or the ID token is invalid.
    """
    settings = get_settings()
    discovery = await _fetch_discovery()
    token_endpoint = discovery["token_endpoint"]

    # Exchange authorization code for tokens
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_endpoint, data=payload)
        if resp.status_code != 200:
            logger.error("OIDC token exchange failed: {} {}", resp.status_code, resp.text)
            raise ValueError(f"OIDC token exchange failed: {resp.status_code}")
        token_data = resp.json()

    id_token_raw = token_data.get("id_token")
    if not id_token_raw:
        raise ValueError("OIDC token response missing id_token")

    # Validate ID token signature using JWKS
    claims = await _validate_id_token(id_token_raw, discovery["issuer"])

    logger.info(
        "OIDC code exchange successful — sub={}, email={}",
        claims.get("sub"),
        claims.get("email"),
    )
    return claims


async def _validate_id_token(id_token: str, issuer: str) -> dict[str, Any]:
    """Validate an OIDC ID token's signature and standard claims.

    Uses the provider's JWKS to verify the RS256/RS384/RS512 signature.
    Validates issuer, audience, and expiration claims.

    Args:
        id_token: The raw JWT ID token string.
        issuer: The expected issuer from the discovery document.

    Returns:
        The decoded and validated token claims.

    Raises:
        ValueError: If the token signature or claims are invalid.
    """
    settings = get_settings()
    jwks_data = await _fetch_jwks()

    try:
        # Construct signing keys from cached JWKS data
        signing_keys = []
        for key_data in jwks_data.get("keys", []):
            try:
                signing_keys.append(jwt.PyJWK(key_data))
            except Exception:
                continue

        if not signing_keys:
            raise ValueError("No valid signing keys found in JWKS")

        # Get the key ID from the token header to find the right key
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")
        _ALLOWED_ALGS = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
        alg = unverified_header.get("alg", "RS256")
        if alg not in _ALLOWED_ALGS:
            raise ValueError(f"Unsupported OIDC token algorithm: {alg}")

        signing_key = None
        if kid:
            # Match by key ID — the only safe lookup when the token specifies a kid
            for key in signing_keys:
                if getattr(key, "key_id", None) == kid:
                    signing_key = key
                    break
            if signing_key is None:
                raise ValueError(f"No signing key found for kid={kid}")
        elif len(signing_keys) == 1:
            # Token has no kid and JWKS has exactly one key — safe to use it
            signing_key = signing_keys[0]
        else:
            raise ValueError(
                "Token has no 'kid' header and JWKS contains multiple keys — "
                "cannot determine which key to use"
            )

        # Decode and validate the token
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=[alg],
            audience=settings.oidc_client_id,
            issuer=issuer,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )

    except jwt.ExpiredSignatureError as exc:
        raise ValueError("OIDC ID token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise ValueError("OIDC ID token audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise ValueError("OIDC ID token issuer mismatch") from exc
    except jwt.PyJWTError as exc:
        raise ValueError(f"OIDC ID token validation failed: {exc}") from exc

    # Ensure required claims are present
    if not claims.get("sub"):
        raise ValueError("OIDC ID token missing 'sub' claim")

    return claims


# ── User provisioning ────────────────────────────────────────────────────────
# Delegated to the shared SSO provisioning module.


async def get_or_create_user(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    claims: dict[str, Any],
) -> User:
    """Find an existing user by OIDC subject or email, or create a new one.

    Delegates to the shared SSO provisioning logic in ``sso_provisioning.py``.

    Args:
        db: Motor database instance.
        claims: Validated OIDC ID token claims.

    Returns:
        The matched or newly created User entity.
    """
    return await provision_sso_user(db, claims, "oidc_subject", claims["sub"])
