"""Auth service — JWT access/refresh tokens, password hashing, TOTP 2FA, and password policy.

Implements a secure token pair flow:
- **Access token**: short-lived (default 15 min), stateless, used for API auth.
  Contains ``sid`` (session ID), ``jti`` (unique token ID), ``aud`` (audience),
  and ``iss`` (issuer) claims for IdP-grade security.
- **Refresh token**: long-lived (default 7 days), stored in MongoDB for revocation.
- **Token rotation**: each refresh issues a new refresh token and invalidates the old.
- **Family tracking**: detects refresh-token reuse (potential theft) and revokes the
  entire token family when detected.
"""

from __future__ import annotations

import hashlib
import io
import secrets
from datetime import timedelta
from typing import Any

import bcrypt
import jwt
import pyotp
import qrcode
import qrcode.image.svg
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings
from utils.dt import ensure_utc, utc_now

from .dto import TokenPayload
from .entities import AccountStatus, User, UserRole

# ── Password hashing ────────────────────────────────────────────────────────


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# Pre-computed dummy hash used to normalize timing when a user is not found.
# This prevents username-enumeration via response-time side channels.
_DUMMY_BCRYPT_HASH: str = bcrypt.hashpw(b"__timing_oracle_dummy__", bcrypt.gensalt()).decode()


# ── Password policy ─────────────────────────────────────────────────────────


def check_password_history(
    password: str,
    password_history: list[dict[str, object]],
) -> bool:
    """Check if a password has been used recently.

    Args:
        password: The plaintext password to check.
        password_history: List of ``{"hash": ..., "set_at": ...}`` dicts.

    Returns:
        True if the password matches any entry in the history (i.e. reuse detected).
    """
    for entry in password_history:
        stored_hash = str(entry.get("hash", ""))
        if stored_hash and verify_password(password, stored_hash):
            return True
    return False


async def check_breached_password(password: str) -> bool:
    """Check if a password appears in the HaveIBeenPwned breach database.

    Uses the k-Anonymity API: only the first 5 characters of the SHA-1 hash
    are sent to the API. The full password never leaves the server.

    Args:
        password: The plaintext password to check.

    Returns:
        True if the password has been found in a breach.
    """
    try:
        sha1 = hashlib.sha1(password.encode()).hexdigest().upper()  # noqa: S324  # nosec B324 — HIBP k-Anonymity API requires SHA1
        prefix, suffix = sha1[:5], sha1[5:]

        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            if resp.status_code != 200:
                logger.warning("HaveIBeenPwned API returned status {}", resp.status_code)
                return False

            for line in resp.text.splitlines():
                parts = line.strip().split(":")
                if len(parts) == 2 and parts[0] == suffix:
                    return True
    except Exception as exc:
        logger.warning("HaveIBeenPwned check failed (non-blocking): {}", exc)
    return False


# ── JWT access tokens (stateless) ───────────────────────────────────────────


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    *,
    session_id: str | None = None,
) -> str:
    """Create a signed JWT access token.

    Claims include ``sub`` (username), ``role``, ``type`` ("access"), ``exp``,
    ``sid`` (session ID), ``jti`` (unique token ID), ``iss`` (issuer),
    and ``aud`` (audience).

    Args:
        data: Base claims (must include ``sub`` and ``role``).
        expires_delta: Custom expiry duration (defaults to config value).
        session_id: Server-side session ID to embed as ``sid`` claim.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    to_encode = data.copy()
    to_encode["type"] = "access"
    to_encode["jti"] = secrets.token_urlsafe(16)
    to_encode["iss"] = "sentora"
    to_encode["aud"] = "sentora-api"
    if session_id:
        to_encode["sid"] = session_id
    expire = utc_now() + (expires_delta or timedelta(minutes=settings.jwt_access_expire_minutes))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token.

    Raises ValueError if the token is invalid, expired, or is not an access token.

    Args:
        token: The encoded JWT string.

    Returns:
        Decoded TokenPayload with username, role, session_id, and token ID.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except Exception as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    # Validate aud/iss when present (new tokens always include them)
    if payload.get("aud") and payload["aud"] != "sentora-api":
        raise ValueError("Invalid token audience")
    if payload.get("iss") and payload["iss"] != "sentora":
        raise ValueError("Invalid token issuer")

    # Reject refresh tokens presented as access tokens
    if payload.get("type") != "access":
        raise ValueError("Invalid token type — expected access token")

    sub: str | None = payload.get("sub")
    role: str | None = payload.get("role")
    if not sub or not role:
        raise ValueError("Token missing required claims (sub, role)")

    return TokenPayload(
        sub=sub,
        role=role,
        exp=payload.get("exp"),
        sid=payload.get("sid"),
        jti=payload.get("jti"),
    )


# ── JWT refresh tokens (stateful, stored in MongoDB) ────────────────────────


async def create_refresh_token(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
    role: str,
    family_id: str | None = None,
) -> tuple[str, str]:
    """Create and persist a refresh token.

    Each refresh token belongs to a *family* — a chain of rotated tokens
    originating from a single login. If ``family_id`` is None a new family
    is started (i.e. fresh login).

    Args:
        db: Motor database handle.
        username: Username for the token subject.
        role: User role for the token.
        family_id: Existing family ID for rotation, or None for new login.

    Returns:
        Tuple of (encoded JWT refresh token, family_id).
    """
    settings = get_settings()
    token_id = secrets.token_urlsafe(32)
    family = family_id or secrets.token_urlsafe(16)
    expire = utc_now() + timedelta(days=settings.jwt_refresh_expire_days)

    # Persist in MongoDB for revocation / reuse detection
    await db["refresh_tokens"].insert_one(
        {
            "token_id": token_id,
            "family_id": family,
            "username": username,
            "role": role,
            "expires_at": expire,
            "created_at": utc_now(),
            "used": False,
        }
    )

    claims = {
        "sub": username,
        "role": role,
        "type": "refresh",
        "jti": token_id,
        "fam": family,
        "exp": expire,
    }
    encoded = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded, family


async def rotate_refresh_token(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    token: str,
    *,
    session_id: str | None = None,
) -> dict[str, str]:
    """Validate a refresh token, rotate it, and return a new token pair.

    - Marks the old refresh token as used.
    - If the old token was *already* used (reuse detected), revokes the
      entire family to protect against stolen tokens.
    - Returns ``{"access_token": ..., "refresh_token": ...}``.

    Args:
        db: Motor database handle.
        token: The encoded refresh token JWT.
        session_id: Session ID to embed in the new access token.

    Returns:
        Dict with new access_token and refresh_token.

    Raises:
        ValueError: On any validation failure.
    """
    settings = get_settings()

    # Decode
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except Exception as exc:
        raise ValueError(f"Invalid refresh token: {exc}") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type — expected refresh token")

    token_id = payload.get("jti")
    family_id = payload.get("fam")
    username = payload.get("sub")
    role = payload.get("role")

    if not all([token_id, family_id, username, role]):
        raise ValueError("Refresh token missing required claims")
    assert isinstance(username, str)
    assert isinstance(role, str)

    # Atomically mark the token as used (prevents race conditions)
    stored = await db["refresh_tokens"].find_one_and_update(
        {"token_id": token_id, "used": False},
        {"$set": {"used": True}},
    )
    if not stored:
        # Token not found or already used — revoke entire family
        if family_id:
            await db["refresh_tokens"].delete_many({"family_id": family_id})
            logger.warning(
                "Refresh token reuse or not found (family {}), revoked family", family_id
            )
        raise ValueError("Refresh token has been revoked or reused")

    # Issue new pair
    new_access = create_access_token(
        {"sub": username, "role": role},
        session_id=session_id,
    )
    new_refresh, _ = await create_refresh_token(db, username, role, family_id=family_id)

    return {"access_token": new_access, "refresh_token": new_refresh}


async def revoke_user_tokens(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
) -> int:
    """Revoke all refresh tokens for a user (logout from all devices).

    Args:
        db: Motor database handle.
        username: Username whose tokens to revoke.

    Returns:
        The number of tokens deleted.
    """
    result = await db["refresh_tokens"].delete_many({"username": username})
    logger.info("Revoked {} refresh tokens for user '{}'", result.deleted_count, username)
    return result.deleted_count


async def revoke_family(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    token: str,
) -> int:
    """Revoke a single token family (logout current session only).

    Args:
        db: Motor database handle.
        token: The refresh token JWT to extract the family from.

    Returns:
        The number of tokens deleted.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
    except Exception:
        return 0

    family_id = payload.get("fam")
    if not family_id:
        return 0

    result = await db["refresh_tokens"].delete_many({"family_id": family_id})
    return result.deleted_count


# ── User lookup ─────────────────────────────────────────────────────────────


def _doc_to_user(doc: dict[str, Any]) -> User:
    """Convert a MongoDB user document to a User entity.

    Args:
        doc: Raw MongoDB document from the ``users`` collection.

    Returns:
        Fully hydrated User entity.
    """
    # Derive status from legacy disabled field if status is not set
    status_raw = doc.get("status")
    if status_raw:
        status = AccountStatus(status_raw)
    elif doc.get("disabled", False):
        status = AccountStatus.deactivated
    else:
        status = AccountStatus.active

    return User(
        id=str(doc["_id"]),
        username=doc["username"],
        email=doc["email"],
        role=UserRole(doc.get("role", "viewer")),
        disabled=doc.get("disabled", False),
        status=status,
        hashed_password=doc.get("hashed_password", ""),
        totp_secret=doc.get("totp_secret"),
        totp_enabled=doc.get("totp_enabled", False),
        oidc_subject=doc.get("oidc_subject"),
        saml_subject=doc.get("saml_subject"),
        tenant_id=doc.get("tenant_id"),
        password_history=doc.get("password_history", []),
        password_changed_at=doc.get("password_changed_at"),
        failed_login_attempts=doc.get("failed_login_attempts", 0),
        locked_until=doc.get("locked_until"),
        known_user_agents=doc.get("known_user_agents", []),
        last_login_ip=doc.get("last_login_ip"),
        last_login_country=doc.get("last_login_country"),
        last_login_at=doc.get("last_login_at"),
    )


async def authenticate_user(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
    password: str,
) -> User | None:
    """Authenticate a user by username and password.

    Runs bcrypt verification even when the user is not found to prevent
    timing-based username enumeration (constant-time response).

    Also enforces account lockout after consecutive failed attempts.

    Args:
        db: Motor database handle.
        username: Login username.
        password: Plaintext password to verify.

    Returns:
        User entity on success, None on failure.
    """
    doc = await db["users"].find_one({"username": username})
    if not doc:
        # Constant-time: run bcrypt against a dummy hash so the response
        # time is indistinguishable from a real password check.
        verify_password(password, _DUMMY_BCRYPT_HASH)
        logger.debug("Auth failed — user '{}' not found", username)
        return None

    # Check account lockout
    locked_until = doc.get("locked_until")
    if locked_until and ensure_utc(locked_until) > utc_now():
        verify_password(password, _DUMMY_BCRYPT_HASH)
        logger.debug("Auth failed — user '{}' is locked until {}", username, locked_until)
        return None

    hashed = doc.get("hashed_password", "")
    if not hashed or not verify_password(password, hashed):
        # Increment failed attempt counter
        settings = get_settings()
        new_count = doc.get("failed_login_attempts", 0) + 1
        update: dict[str, Any] = {"$set": {"failed_login_attempts": new_count}}
        if new_count >= settings.account_lockout_threshold:
            lock_until = utc_now() + timedelta(minutes=settings.account_lockout_duration_minutes)
            update["$set"]["locked_until"] = lock_until
            logger.warning(
                "Account '{}' locked after {} failed attempts (until {})",
                username,
                new_count,
                lock_until,
            )
        await db["users"].update_one({"username": username}, update)
        logger.debug("Auth failed — invalid password for user '{}'", username)
        return None

    # Clear failed attempt counter on successful auth
    if doc.get("failed_login_attempts", 0) > 0:
        await db["users"].update_one(
            {"username": username},
            {"$set": {"failed_login_attempts": 0, "locked_until": None}},
        )

    return _doc_to_user(doc)


async def get_user_by_username(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
) -> User | None:
    """Look up a user by username.

    Args:
        db: Motor database handle.
        username: Username to search for.

    Returns:
        User entity if found, None otherwise.
    """
    doc = await db["users"].find_one({"username": username})
    if not doc:
        return None
    return _doc_to_user(doc)


async def record_login_metadata(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    username: str,
    ip_address: str,
    user_agent: str,
) -> dict[str, bool]:
    """Record login metadata and detect anomalies.

    Updates the user's last login IP, timestamp, and known user agents.
    Returns flags indicating if this is a new device or potentially suspicious.

    Args:
        db: Motor database handle.
        username: Username that just logged in.
        ip_address: Client IP address.
        user_agent: Client User-Agent header.

    Returns:
        Dict with ``new_device`` and ``impossible_travel`` boolean flags.
    """
    now = utc_now()
    doc: dict[str, Any] | None = await db["users"].find_one(
        {"username": username},
        {"known_user_agents": 1, "last_login_ip": 1, "last_login_at": 1, "_id": 0},
    )
    if not doc:
        return {"new_device": False, "impossible_travel": False}

    known_agents = doc.get("known_user_agents", [])
    new_device = user_agent not in known_agents

    update: dict[str, Any] = {
        "$set": {
            "last_login_ip": ip_address,
            "last_login_at": now,
        }
    }
    if new_device and len(known_agents) < 50:
        update["$addToSet"] = {"known_user_agents": user_agent}

    await db["users"].update_one({"username": username}, update)

    return {"new_device": new_device, "impossible_travel": False}


# ── TOTP 2FA ────────────────────────────────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a new base32-encoded TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    """Build an otpauth:// provisioning URI for authenticator apps.

    Args:
        secret: Base32-encoded TOTP secret.
        username: Username for the account identifier.

    Returns:
        otpauth:// URI string.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name="Sentora")


def generate_qr_svg(uri: str) -> str:
    """Generate a QR code as an SVG string from an otpauth URI.

    Args:
        uri: The otpauth:// URI to encode.

    Returns:
        SVG markup string containing the QR code.
    """
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against a secret.

    Allows a ±1 window (30 seconds each side) to account for clock drift.

    Args:
        secret: Base32-encoded TOTP secret.
        code: 6-digit TOTP code from the authenticator app.

    Returns:
        True if the code is valid within the time window.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
