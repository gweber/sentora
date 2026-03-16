"""Auth domain router.

POST  /api/v1/auth/login               — authenticate (optionally with TOTP)
POST  /api/v1/auth/register            — create user + TOTP setup
POST  /api/v1/auth/totp/verify-setup   — confirm first TOTP code to activate 2FA
POST  /api/v1/auth/refresh             — exchange refresh token for new token pair
POST  /api/v1/auth/logout              — revoke current session's refresh tokens
POST  /api/v1/auth/logout/all          — revoke ALL refresh tokens for current user
POST  /api/v1/auth/change-password     — change current user's password
GET   /api/v1/auth/me                  — return the current authenticated user
GET   /api/v1/auth/password-policy     — return current password policy
GET   /api/v1/auth/users               — list all users (admin only)
PATCH /api/v1/auth/users/:username/role     — change role (admin only)
PATCH /api/v1/auth/users/:username/disabled — toggle disabled (admin only)
PATCH /api/v1/auth/users/:username/status   — change lifecycle status (admin only)
DELETE /api/v1/auth/users/:username    — delete user (admin only)
GET   /api/v1/auth/sessions            — list current user's sessions
DELETE /api/v1/auth/sessions/:id       — revoke a specific session
DELETE /api/v1/auth/sessions           — revoke all other sessions
GET   /api/v1/auth/admin/sessions      — list sessions for a user (admin only)
DELETE /api/v1/auth/admin/sessions     — revoke all sessions for a user (admin only)
GET   /api/v1/auth/oidc/login          — redirect to OIDC provider (SSO)
GET   /api/v1/auth/oidc/callback       — handle OIDC callback, issue JWT tokens
GET   /api/v1/auth/saml/login          — redirect to SAML IdP (SSO)
POST  /api/v1/auth/saml/callback       — handle SAML assertion callback
GET   /api/v1/auth/saml/metadata       — return SP metadata XML
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from audit.log import audit
from config import get_settings
from database import get_tenant_db
from middleware.auth import get_current_user, require_role
from utils.http import client_ip
from utils.rate_limit import RateLimiter

from .dto import (
    ChangePasswordRequest,
    LoginRequest,
    OIDCLoginResponse,
    PasswordPolicyResponse,
    RefreshRequest,
    RegisterRequest,
    SAMLLoginResponse,
    SessionResponse,
    SessionsListResponse,
    TokenPayload,
    TokenResponse,
    TotpSetupResponse,
    TotpVerifySetupRequest,
    UpdateUserDisabledRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserResponse,
    UsersListResponse,
)
from .entities import AccountStatus, User, UserRole
from .service import (
    activate_totp,
    authenticate_user,
    change_user_password,
    check_breached_password,
    check_password_history,
    create_access_token,
    create_refresh_token,
    create_user,
    generate_qr_svg,
    generate_totp_secret,
    get_password_hash,
    get_totp_uri,
    get_user_by_username,
    record_login_metadata,
    revoke_family,
    revoke_user_tokens,
    rotate_refresh_token,
    soft_delete_user,
    verify_password,
    verify_totp,
)
from .service import (
    list_users as list_users_from_db,
)
from .service import (
    update_user_disabled as update_user_disabled_in_db,
)
from .service import (
    update_user_role as update_user_role_in_db,
)
from .service import (
    update_user_status as update_user_status_in_db,
)
from .session_service import (
    create_session,
    find_active_session_by_family,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
)

router = APIRouter()

# Rate limiters — per-IP sliding window
_login_limiter = RateLimiter(max_requests=10, window_seconds=60)
_register_limiter = RateLimiter(max_requests=5, window_seconds=300)
_refresh_limiter = RateLimiter(max_requests=30, window_seconds=60)
_totp_limiter = RateLimiter(max_requests=5, window_seconds=60)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_user_agent(request: Request) -> str:
    """Extract the User-Agent header from the request.

    Args:
        request: The incoming HTTP request.

    Returns:
        User-Agent string or 'unknown'.
    """
    return request.headers.get("user-agent", "unknown")[:500]


def _user_to_response(user: User, *, user_status: AccountStatus | None = None) -> UserResponse:
    """Convert a User entity to a UserResponse DTO.

    Args:
        user: User entity.
        user_status: Override status (if different from entity).

    Returns:
        UserResponse DTO.
    """
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        disabled=user.disabled,
        totp_enabled=user.totp_enabled,
        status=user_status or user.status,
    )


async def _issue_tokens_with_session(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    user: User,
    request: Request,
) -> TokenResponse:
    """Create a session and issue JWT token pair.

    Centralizes the login completion logic used by all auth flows
    (password, OIDC, SAML, TOTP verification).

    Args:
        db: Motor database handle.
        user: Authenticated User entity.
        request: The incoming HTTP request (for IP/UA extraction).

    Returns:
        TokenResponse with access and refresh tokens.
    """
    ip_address = client_ip(request)
    user_agent = _get_user_agent(request)

    # Create refresh token (gets family_id)
    refresh_token, family_id = await create_refresh_token(db, user.username, user.role.value)

    # Create server-side session
    session = await create_session(
        db,
        user_id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        refresh_token_family=family_id,
    )

    # Resolve tenant_id: prefer user's bound tenant, fall back to request tenant
    tenant_id = user.tenant_id
    if not tenant_id:
        req_tenant = getattr(request.state, "tenant", None)
        if req_tenant and isinstance(req_tenant, dict):
            tenant_id = req_tenant.get("slug")

    # Create access token with session_id and tenant_id embedded
    access_token = create_access_token(
        {"sub": user.username, "role": user.role.value},
        session_id=session.id,
        tenant_id=tenant_id,
    )

    # Record login metadata (new device detection, etc.)
    anomalies = await record_login_metadata(db, user.username, ip_address, user_agent)

    # Audit anomalies
    if anomalies.get("new_device"):
        await audit(
            db,
            domain="auth",
            action="auth.new_device_detected",
            actor=user.username,
            status="info",
            summary=f"New device detected for '{user.username}'",
            details={"ip_address": ip_address, "user_agent": user_agent},
        )

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ── Login / Token lifecycle ─────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TokenResponse:
    """Authenticate with username/password and optionally TOTP code.

    Returns an access + refresh token pair on success. Creates a server-side
    session for immediate revocation support.
    """
    _login_limiter.check(request)
    user = await authenticate_user(db, payload.username, payload.password)
    if not user:
        await audit(
            db,
            domain="auth",
            action="auth.login_failed",
            actor=payload.username,
            status="failure",
            summary=f"Login failed for '{payload.username}'",
            details={"ip_address": client_ip(request)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account status
    if user.disabled or user.status in (
        AccountStatus.suspended,
        AccountStatus.deactivated,
        AccountStatus.deleted,
    ):
        detail = "Account is disabled"
        if user.status == AccountStatus.suspended:
            detail = "Account is suspended — contact your administrator"
        elif user.status == AccountStatus.invited:
            detail = "Account has not been activated — check your invitation"
        await audit(
            db,
            domain="auth",
            action="auth.login_failed",
            actor=payload.username,
            status="failure",
            summary=f"Login blocked — account status: {user.status}",
            details={"status": user.status},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    # If user has TOTP enabled, require the code
    if user.totp_enabled:
        if not payload.totp_code:
            # Signal frontend to show the TOTP modal
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"requires_totp": True},
            )
        if not user.totp_secret or not verify_totp(user.totp_secret, payload.totp_code):
            await audit(
                db,
                domain="auth",
                action="auth.totp_verify_failed",
                actor=user.username,
                status="failure",
                summary=f"TOTP verification failed for '{user.username}'",
                details={"ip_address": client_ip(request)},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

    token_response = await _issue_tokens_with_session(db, user, request)
    await audit(
        db,
        domain="auth",
        action="auth.login",
        actor=user.username,
        summary=f"User '{user.username}' logged in",
        details={"ip_address": client_ip(request), "user_agent": _get_user_agent(request)},
    )
    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    payload: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair.

    The old refresh token is consumed (single-use). If a consumed token is
    presented again, the entire token family is revoked (theft detection).
    Session ID is carried forward to the new access token.
    """
    _refresh_limiter.check(request)

    # Session ID is now resolved from the refresh token's DB record
    # inside rotate_refresh_token (via the token family → session lookup).
    try:
        tokens = await rotate_refresh_token(db, payload.refresh_token)
    except ValueError as exc:
        await audit(
            db,
            domain="auth",
            action="auth.token_refresh_failed",
            actor="unknown",
            status="failure",
            summary=f"Token refresh failed: {exc}",
            details={"ip_address": client_ip(request)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


@router.post("/logout", status_code=204)
async def logout(
    payload: RefreshRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> None:
    """Revoke the current session (token family) by supplying the refresh token.

    Also revokes the associated server-side session.
    Does not require authentication — the refresh token itself is proof of session.
    """
    # Extract family_id and find the associated session
    settings = get_settings()
    actor = "unknown"
    try:
        import jwt as _jwt

        _token_payload = _jwt.decode(
            payload.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        actor = _token_payload.get("sub", "unknown")
        family_id = _token_payload.get("fam")

        # Revoke the session associated with this token family
        if family_id:
            session_id = await find_active_session_by_family(db, family_id)
            if session_id:
                await revoke_session(db, session_id, reason="logout")
    except Exception as exc:
        from loguru import logger

        logger.warning("Logout session cleanup failed: {}", exc)

    await revoke_family(db, payload.refresh_token)
    await audit(db, domain="auth", action="auth.logout", actor=actor, summary="Session revoked")


@router.post("/logout/all", status_code=204)
async def logout_all(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    token_payload: TokenPayload = Depends(get_current_user),
) -> None:
    """Revoke ALL refresh tokens and sessions for the current user (logout all devices).

    Requires a valid access token.
    """
    await revoke_user_tokens(db, token_payload.sub)
    await revoke_all_user_sessions(db, token_payload.sub, reason="logout_all")
    await audit(
        db,
        domain="auth",
        action="auth.logout_all",
        actor=token_payload.sub,
        summary=f"All sessions revoked for '{token_payload.sub}'",
    )


# ── Password change ──────────────────────────────────────────────────────────

_password_change_limiter = RateLimiter(max_requests=5, window_seconds=300)


@router.post("/change-password", status_code=204)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    token_payload: TokenPayload = Depends(get_current_user),
) -> None:
    """Change the current user's password.

    Validates the current password, checks password policy (history, breach),
    and invalidates all other sessions on success.
    """
    _password_change_limiter.check(request)

    from domains.config import repository as config_repo

    cfg = await config_repo.get(db)

    user = await get_user_by_username(db, token_payload.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify current password
    pw_valid = user.hashed_password and verify_password(
        payload.current_password, user.hashed_password
    )
    if not pw_valid:
        await audit(
            db,
            domain="auth",
            action="auth.password_change_failed",
            actor=token_payload.sub,
            status="failure",
            summary=f"Password change failed for '{token_payload.sub}'",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Validate new password against policy
    if len(payload.new_password) < cfg.password_min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {cfg.password_min_length} characters",
        )

    # Check password history
    if cfg.password_history_count > 0 and check_password_history(
        payload.new_password, user.password_history
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reuse any of your last {cfg.password_history_count} passwords",
        )

    # Check breached password (optional)
    if cfg.password_check_breached and await check_breached_password(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has been found in a data breach",
        )

    # Update password and history
    from utils.dt import utc_now

    new_hash = get_password_hash(payload.new_password)
    history_entry = {"hash": user.hashed_password, "set_at": utc_now()}
    history = [history_entry] + user.password_history[: cfg.password_history_count - 1]

    await change_user_password(
        db,
        token_payload.sub,
        new_hash=new_hash,
        password_history=history,
    )

    # Invalidate all other sessions (keep current)
    await revoke_all_user_sessions(
        db,
        token_payload.sub,
        reason="password_changed",
        exclude_session_id=token_payload.sid,
    )

    await audit(
        db,
        domain="auth",
        action="auth.password_changed",
        actor=token_payload.sub,
        summary=f"Password changed for '{token_payload.sub}'",
    )


# ── Password policy ──────────────────────────────────────────────────────────


@router.get("/password-policy", response_model=PasswordPolicyResponse)
async def get_password_policy(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> PasswordPolicyResponse:
    """Return the current password policy configuration.

    Reads from persisted config (MongoDB) with env var defaults.
    Public endpoint — used by the frontend to display password requirements
    during registration and password changes.
    """
    from domains.config import repository as config_repo

    cfg = await config_repo.get(db)
    return PasswordPolicyResponse(
        min_length=cfg.password_min_length,
        require_uppercase=cfg.password_require_uppercase,
        require_lowercase=cfg.password_require_lowercase,
        require_digit=cfg.password_require_digit,
        require_special=cfg.password_require_special,
        history_count=cfg.password_history_count,
        max_age_days=cfg.password_max_age_days or None,
        check_breached=cfg.password_check_breached,
    )


# ── Registration + TOTP setup ──────────────────────────────────────────────


@router.post("/register", response_model=TotpSetupResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TotpSetupResponse:
    """Register a new user account with TOTP 2FA setup.

    The first registered user is automatically promoted to super_admin.
    Returns a QR code SVG for authenticator app enrollment.
    """
    _register_limiter.check(request)

    # Read password policy from persisted config
    from domains.config import repository as config_repo

    cfg = await config_repo.get(db)
    if len(payload.password) < cfg.password_min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {cfg.password_min_length} characters",
        )

    # Check breached password (optional)
    if cfg.password_check_breached and await check_breached_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has been found in a data breach",
        )

    existing = await get_user_by_username(db, payload.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already taken",
        )

    # Atomically claim first-user status to auto-promote the first registrant
    from .first_user import claim_first_user

    role = await claim_first_user(db, payload.username)

    totp_secret = generate_totp_secret()
    from utils.dt import utc_now

    doc: dict[str, object] = {
        "username": payload.username,
        "email": payload.email,
        "hashed_password": get_password_hash(payload.password),
        "role": role.value,
        "disabled": False,
        "status": AccountStatus.active.value,
        "totp_secret": totp_secret,
        "totp_enabled": False,
        "password_history": [],
        "password_changed_at": utc_now(),
        "failed_login_attempts": 0,
        "known_user_agents": [],
    }
    from pymongo.errors import DuplicateKeyError

    try:
        inserted_id = await create_user(db, doc)
    except DuplicateKeyError as exc:
        # Determine which unique constraint was violated for a helpful message
        err_msg = str(exc)
        if "email" in err_msg:
            detail = f"Email '{payload.email}' is already registered"
        elif "username" in err_msg:
            detail = f"Username '{payload.username}' is already taken"
        else:
            detail = "Username or email is already taken"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc

    user_resp = UserResponse(
        id=inserted_id,
        username=payload.username,
        email=payload.email,
        role=role,
        disabled=False,
        totp_enabled=False,
        status=AccountStatus.active,
    )

    totp_uri = get_totp_uri(totp_secret, payload.username)
    qr_svg = generate_qr_svg(totp_uri)

    await audit(
        db,
        domain="auth",
        action="auth.registered",
        actor=payload.username,
        summary=f"User '{payload.username}' registered",
    )

    return TotpSetupResponse(
        user=user_resp,
        totp_uri=totp_uri,
        qr_code_svg=qr_svg,
    )


@router.post("/totp/verify-setup", response_model=TokenResponse)
async def verify_totp_setup(
    request: Request,
    payload: TotpVerifySetupRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TokenResponse:
    """Verify the first TOTP code to activate 2FA and return a token pair.

    Called after registration once the user has scanned the QR code.
    Creates a server-side session on success.
    """
    _totp_limiter.check(request)
    user = await get_user_by_username(db, payload.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TOTP is already enabled for this account",
        )
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No TOTP secret configured — re-register",
        )

    if not verify_totp(user.totp_secret, payload.code):
        await audit(
            db,
            domain="auth",
            action="auth.totp_verify_failed",
            actor=user.username,
            status="failure",
            summary=f"TOTP setup verification failed for '{user.username}'",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code — please try again",
        )

    # Activate 2FA
    await activate_totp(db, payload.username)

    await audit(
        db,
        domain="auth",
        action="auth.totp_activated",
        actor=payload.username,
        summary=f"TOTP activated for '{payload.username}'",
    )

    # Issue token pair with session
    token_response = await _issue_tokens_with_session(db, user, request)
    return token_response


# ── Session management ─────────────────────────────────────────────────────


@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    token_payload: TokenPayload = Depends(get_current_user),
) -> SessionsListResponse:
    """List the current user's active sessions (device management).

    Shows all active sessions with device info, IP, and last activity.
    The current session is marked with ``is_current: true``.
    """
    sessions = await list_user_sessions(db, token_payload.sub, active_only=True)
    items = [
        SessionResponse(
            id=s.id,
            username=s.username,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
            expires_at=s.expires_at,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            is_active=s.is_active,
            is_current=s.id == token_payload.sid,
        )
        for s in sessions
    ]
    return SessionsListResponse(sessions=items, total=len(items))


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_single_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    token_payload: TokenPayload = Depends(get_current_user),
) -> None:
    """Revoke a specific session (log out a single device).

    Users can only revoke their own sessions.
    """
    from .session_service import get_session

    session = await get_session(db, session_id)
    if not session or session.username != token_payload.sub:
        raise HTTPException(status_code=404, detail="Session not found")

    revoked = await revoke_session(db, session_id, reason="user_revoked")
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found or already revoked")

    await audit(
        db,
        domain="auth",
        action="auth.session_revoked",
        actor=token_payload.sub,
        summary=f"Session revoked by '{token_payload.sub}'",
        details={"session_id": session_id[:8]},
    )


@router.delete("/sessions", status_code=204)
async def revoke_other_sessions(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    token_payload: TokenPayload = Depends(get_current_user),
) -> None:
    """Revoke all sessions except the current one (log out other devices)."""
    count = await revoke_all_user_sessions(
        db,
        token_payload.sub,
        reason="user_revoked_others",
        exclude_session_id=token_payload.sid,
    )
    await audit(
        db,
        domain="auth",
        action="auth.sessions_revoked_all",
        actor=token_payload.sub,
        summary=f"Revoked {count} other session(s) for '{token_payload.sub}'",
    )


# ── Admin session management ────────────────────────────────────────────────


@router.get(
    "/admin/sessions",
    response_model=SessionsListResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def admin_list_sessions(
    username: str = Query(..., min_length=1),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SessionsListResponse:
    """List all active sessions for a specific user. Admin only.

    Args:
        username: Username whose sessions to list.
    """
    sessions = await list_user_sessions(db, username, active_only=True)
    items = [
        SessionResponse(
            id=s.id,
            username=s.username,
            created_at=s.created_at,
            last_active_at=s.last_active_at,
            expires_at=s.expires_at,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            is_active=s.is_active,
        )
        for s in sessions
    ]
    return SessionsListResponse(sessions=items, total=len(items))


@router.delete(
    "/admin/sessions",
    status_code=204,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def admin_revoke_sessions(
    username: str = Query(..., min_length=1),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    """Revoke all sessions for a specific user. Admin only.

    Used for emergency access termination.
    """
    count = await revoke_all_user_sessions(db, username, reason="admin_revoked")
    await revoke_user_tokens(db, username)
    await audit(
        db,
        domain="auth",
        action="auth.admin_sessions_revoked",
        actor=current_user.sub,
        summary=f"Admin revoked {count} session(s) for '{username}'",
        details={"target_user": username, "count": count},
    )


# ── User management (admin only) ─────────────────────────────────────────────


@router.get(
    "/users", response_model=UsersListResponse, dependencies=[Depends(require_role(UserRole.admin))]
)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> UsersListResponse:
    """List all users. Admin only."""
    user_docs, total = await list_users_from_db(db, skip=skip, limit=limit)
    users = []
    for doc in user_docs:
        status_raw = doc.get("status")
        if status_raw:
            user_status = AccountStatus(status_raw)
        elif doc.get("disabled", False):
            user_status = AccountStatus.deactivated
        else:
            user_status = AccountStatus.active
        users.append(
            UserResponse(
                id=str(doc["_id"]),
                username=doc["username"],
                email=doc["email"],
                role=UserRole(doc.get("role", "viewer")),
                disabled=doc.get("disabled", False),
                totp_enabled=doc.get("totp_enabled", False),
                status=user_status,
            )
        )
    return UsersListResponse(users=users, total=total)


@router.patch(
    "/users/{username}/role",
    response_model=UserResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def update_user_role(
    username: str,
    payload: UpdateUserRoleRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    current_user: TokenPayload = Depends(get_current_user),
) -> UserResponse:
    """Change a user's role. Admin only.

    Also revokes all refresh tokens and sessions for the user so they must
    re-authenticate with the updated role.
    """
    # Self-modification guard — users cannot change their own role
    if username == current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )
    if payload.role == UserRole.super_admin and current_user.role != UserRole.super_admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can escalate to super_admin role",
        )
    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Protect admin/super_admin targets — only super_admin can modify their roles
    if (
        user.role in (UserRole.admin, UserRole.super_admin)
        and current_user.role != UserRole.super_admin.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can modify admin or super_admin roles",
        )
    await update_user_role_in_db(db, username, payload.role.value)
    # Role changed — invalidate all sessions so new tokens reflect new role
    await revoke_user_tokens(db, username)
    await revoke_all_user_sessions(db, username, reason="role_changed")
    await audit(
        db,
        domain="auth",
        action="auth.role_changed",
        actor=current_user.sub,
        summary=f"Role changed for '{username}' to {payload.role.value}",
        details={"target": username, "old_role": user.role.value, "new_role": payload.role.value},
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=payload.role,
        disabled=user.disabled,
        totp_enabled=user.totp_enabled,
        status=user.status,
    )


@router.patch(
    "/users/{username}/disabled",
    response_model=UserResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def update_user_disabled(
    username: str,
    payload: UpdateUserDisabledRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    current_user: TokenPayload = Depends(get_current_user),
) -> UserResponse:
    """Enable or disable a user account. Admin only."""
    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_status = AccountStatus.deactivated if payload.disabled else AccountStatus.active
    await update_user_disabled_in_db(
        db,
        username,
        disabled=payload.disabled,
        status=new_status.value,
    )
    # If disabling, revoke all sessions and update revocation cache immediately
    if payload.disabled:
        await revoke_user_tokens(db, username)
        await revoke_all_user_sessions(db, username, reason="account_disabled")
        from utils.user_revocation import mark_user_revoked

        mark_user_revoked(username)
    else:
        from utils.user_revocation import mark_user_restored

        mark_user_restored(username)
    action = "auth.user_disabled" if payload.disabled else "auth.user_enabled"
    await audit(
        db,
        domain="auth",
        action=action,
        actor=current_user.sub,
        summary=f"User '{username}' {'disabled' if payload.disabled else 'enabled'}",
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        disabled=payload.disabled,
        totp_enabled=user.totp_enabled,
        status=new_status,
    )


@router.patch(
    "/users/{username}/status",
    response_model=UserResponse,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def update_user_status(
    username: str,
    payload: UpdateUserStatusRequest,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    current_user: TokenPayload = Depends(get_current_user),
) -> UserResponse:
    """Change a user's account lifecycle status. Admin only.

    Supports transitions: active ↔ suspended, active → deactivated, * → deleted.
    Suspending or deactivating a user revokes all their sessions immediately.
    """
    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate state transitions
    _non_active = {
        AccountStatus.suspended,
        AccountStatus.deactivated,
        AccountStatus.deleted,
    }
    valid_transitions: dict[AccountStatus, set[AccountStatus]] = {
        AccountStatus.active: _non_active,
        AccountStatus.invited: {AccountStatus.active, AccountStatus.deleted},
        AccountStatus.suspended: {AccountStatus.active} | _non_active,
        AccountStatus.deactivated: {AccountStatus.active, AccountStatus.deleted},
        AccountStatus.deleted: set(),
    }
    allowed = valid_transitions.get(user.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{user.status}' to '{payload.status}'",
        )

    disabled = payload.status in _non_active
    await update_user_status_in_db(
        db,
        username,
        status=payload.status.value,
        disabled=disabled,
    )

    # Revoke sessions for non-active statuses
    if disabled:
        await revoke_user_tokens(db, username)
        await revoke_all_user_sessions(db, username, reason=f"status_changed_{payload.status}")
        from utils.user_revocation import mark_user_revoked

        mark_user_revoked(username)
    else:
        from utils.user_revocation import mark_user_restored

        mark_user_restored(username)

    await audit(
        db,
        domain="auth",
        action=f"auth.user_{payload.status}",
        actor=current_user.sub,
        summary=f"User '{username}' status changed to {payload.status}",
        details={
            "target": username,
            "old_status": user.status.value,
            "new_status": payload.status.value,
            "reason": payload.reason,
        },
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        disabled=disabled,
        totp_enabled=user.totp_enabled,
        status=payload.status,
    )


@router.delete(
    "/users/{username}",
    status_code=204,
    dependencies=[Depends(require_role(UserRole.admin))],
)
async def delete_user(
    username: str,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    current_user: TokenPayload = Depends(get_current_user),
) -> None:
    """Soft-delete a user account. Admin only.

    Sets status to 'deleted' and revokes all tokens. The user document
    is retained for audit trail integrity (compliance requirement).
    """
    if username == current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    # Prevent non-super_admin from deleting super_admin accounts
    target = await get_user_by_username(db, username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if (
        target.role in (UserRole.admin, UserRole.super_admin)
        and current_user.role != UserRole.super_admin.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super_admin can delete admin accounts",
        )

    # Soft-delete: mark as deleted instead of removing the document
    await soft_delete_user(db, username)
    await revoke_user_tokens(db, username)
    await revoke_all_user_sessions(db, username, reason="account_deleted")
    from utils.user_revocation import mark_user_revoked

    mark_user_revoked(username)
    await audit(
        db,
        domain="auth",
        action="auth.user_deleted",
        actor=current_user.sub,
        summary=f"User '{username}' soft-deleted",
    )


# ── Profile ──────────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def me(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
    token_payload: TokenPayload = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user's profile.

    Args:
        db: Motor database handle (injected).
        token_payload: Decoded JWT payload (injected via auth middleware).

    Returns:
        UserResponse with the current user's public profile data.
    """
    user = await get_user_by_username(db, token_payload.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_response(user)


# ── OIDC / SSO ───────────────────────────────────────────────────────────────
_oidc_limiter = RateLimiter(max_requests=20, window_seconds=60)


@router.get("/oidc/login", response_model=OIDCLoginResponse)
async def oidc_login(
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> OIDCLoginResponse:
    """Redirect to OIDC provider login page.

    Returns the authorization URL the frontend should redirect the user to.
    Returns 404 if OIDC is not enabled.
    """
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC authentication is not enabled",
        )

    from .oidc import get_authorization_url

    try:
        url = await get_authorization_url(db)
    except ValueError as exc:
        logger.warning("OIDC configuration error: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC configuration error — check server logs",
        ) from exc

    return OIDCLoginResponse(authorization_url=url)


@router.get("/oidc/callback", response_model=TokenResponse)
async def oidc_callback(
    request: Request,
    code: str,
    state: str,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TokenResponse:
    """Handle OIDC callback — exchange code, create/find user, issue JWT.

    Creates a server-side session on successful authentication.
    """
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC authentication is not enabled",
        )

    _oidc_limiter.check(request)

    # Handle OIDC provider errors
    if error:
        logger.warning("OIDC callback error: {} — {}", error, error_description)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC authentication failed: {error_description or error}",
        )

    from .oidc import exchange_code, get_or_create_user, validate_state

    # Validate CSRF state and retrieve PKCE code_verifier
    state_doc = await validate_state(db, state)
    if not state_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OIDC state parameter",
        )

    # Exchange authorization code for ID token claims (with PKCE)
    try:
        claims = await exchange_code(code, code_verifier=state_doc.get("code_verifier"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # Get or create the local user
    user = await get_or_create_user(db, claims)

    if user.disabled or user.status in (
        AccountStatus.suspended,
        AccountStatus.deactivated,
        AccountStatus.deleted,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Issue Sentora JWT tokens with session
    token_response = await _issue_tokens_with_session(db, user, request)
    await audit(
        db,
        domain="auth",
        action="auth.oidc_login",
        actor=user.username,
        summary=f"OIDC login by '{user.username}'",
        details={"ip_address": client_ip(request)},
    )
    return token_response


# ── SAML SSO ──────────────────────────────────────────────────────────────────
_saml_limiter = RateLimiter(max_requests=20, window_seconds=60)


@router.get("/saml/login", response_model=SAMLLoginResponse)
async def saml_login(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> SAMLLoginResponse:
    """Return the SAML IdP redirect URL for SP-initiated SSO.

    Returns 404 if SAML is not enabled, 501 if python3-saml is not installed.
    """
    settings = get_settings()
    if not settings.saml_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SAML authentication is not enabled",
        )

    from .saml import SAML_AVAILABLE, get_auth_request_url

    if not SAML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SAML support requires python3-saml — install it with: pip install python3-saml",
        )

    http_host = request.headers.get("host", "localhost:5002")
    try:
        url = await get_auth_request_url(db, http_host)
    except (ValueError, ImportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SAML configuration error: {exc}",
        ) from exc

    return SAMLLoginResponse(redirect_url=url)


@router.post("/saml/callback", response_class=RedirectResponse)
async def saml_callback(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> RedirectResponse:
    """Handle SAML ACS callback — validate assertion, provision user, issue JWT.

    Creates a server-side session. Stores tokens with a one-time nonce
    for secure frontend exchange.
    """
    settings = get_settings()
    if not settings.saml_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SAML authentication is not enabled",
        )

    from .saml import SAML_AVAILABLE, process_response
    from .sso_provisioning import provision_sso_user

    if not SAML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SAML support requires python3-saml",
        )

    _saml_limiter.check(request)

    http_host = request.headers.get("host", "localhost:5002")
    form_data = await request.form()
    post_data = {key: value for key, value in form_data.items()}

    try:
        claims = await process_response(db, http_host, post_data)
    except (ValueError, ImportError) as exc:
        logger.warning("SAML callback failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SAML authentication failed: {exc}",
        ) from exc

    if not claims.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SAML response missing NameID (subject)",
        )

    # Provision or find the local user
    user = await provision_sso_user(db, claims, "saml_subject", claims["sub"])

    if user.disabled or user.status in (
        AccountStatus.suspended,
        AccountStatus.deactivated,
        AccountStatus.deleted,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Issue Sentora JWT tokens with session
    token_response = await _issue_tokens_with_session(db, user, request)
    await audit(
        db,
        domain="auth",
        action="auth.saml_login",
        actor=user.username,
        summary=f"SAML login by '{user.username}'",
        details={"ip_address": client_ip(request)},
    )

    # Store tokens server-side with a one-time nonce to avoid leaking JWTs
    import secrets as _secrets

    from .saml import store_token_exchange

    nonce = _secrets.token_urlsafe(32)
    await store_token_exchange(db, nonce, token_response.access_token, token_response.refresh_token)

    from urllib.parse import urlencode

    params = urlencode({"saml_nonce": nonce})
    return RedirectResponse(url=f"/auth/oidc/callback?{params}", status_code=302)


@router.get("/saml/metadata")
async def saml_metadata(request: Request) -> Response:
    """Return the SAML SP metadata XML for IdP registration."""
    settings = get_settings()
    if not settings.saml_enabled:
        raise HTTPException(status_code=404, detail="SAML is not enabled")

    from .saml import SAML_AVAILABLE, generate_sp_metadata

    if not SAML_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SAML support requires python3-saml",
        )

    http_host = request.headers.get("host", "localhost:5002")
    try:
        metadata_xml = generate_sp_metadata(http_host)
    except (ValueError, ImportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SP metadata: {exc}",
        ) from exc

    return Response(content=metadata_xml, media_type="application/xml")


# ── SAML one-time token exchange ─────────────────────────────────────────────
_saml_exchange_limiter = RateLimiter(max_requests=10, window_seconds=60)


@router.post("/saml/exchange", response_model=TokenResponse)
async def saml_token_exchange(
    request: Request,
    nonce: str = Query(..., min_length=1, max_length=100),
    db: AsyncIOMotorDatabase = Depends(get_tenant_db),  # type: ignore[type-arg]
) -> TokenResponse:
    """Exchange a one-time SAML nonce for JWT tokens.

    The SAML callback stores tokens server-side keyed by a random nonce
    and redirects the browser with only the nonce in the URL.  The frontend
    calls this endpoint to retrieve the actual tokens.

    The nonce is consumed atomically (find-and-delete) so it cannot be reused.
    Nonces auto-expire via a TTL index after 5 minutes.

    Args:
        request: The incoming HTTP request (for rate limiting).
        nonce: The one-time nonce from the SAML callback redirect.
        db: Motor database handle (injected).

    Returns:
        TokenResponse with access and refresh tokens.

    Raises:
        HTTPException 400: If the nonce is invalid, expired, or already consumed.
    """
    _saml_exchange_limiter.check(request)

    from .saml import consume_token_exchange

    doc = await consume_token_exchange(db, nonce)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired SAML exchange nonce",
        )

    return TokenResponse(
        access_token=doc["access_token"],
        refresh_token=doc["refresh_token"],
    )
