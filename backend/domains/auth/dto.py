"""Auth domain DTOs — request/response models for the auth API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .entities import AccountStatus, UserRole


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)
    totp_code: str | None = Field(None, min_length=6, max_length=6)


class RegisterRequest(BaseModel):
    """POST /auth/register request body."""

    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce minimum password complexity (NIST SP 800-63B inspired).

        Requires at least one uppercase letter, one lowercase letter, and one digit.
        Minimum length of 12 characters is enforced via the Field constraint.
        """
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class ChangePasswordRequest(BaseModel):
    """POST /auth/change-password — change the current user's password."""

    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, v: str) -> str:
        """Enforce password complexity on the new password."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class TotpSetupResponse(BaseModel):
    """Returned after registration — contains QR code for authenticator app setup."""

    user: UserResponse
    totp_uri: str
    qr_code_svg: str


class TotpVerifySetupRequest(BaseModel):
    """POST /auth/totp/verify-setup — confirm first TOTP code to activate 2FA."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    """JWT token pair returned on successful login or refresh."""

    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    requires_totp: bool = False


class RefreshRequest(BaseModel):
    """POST /auth/refresh — exchange a refresh token for a new token pair."""

    refresh_token: str = Field(..., min_length=1)


class TokenPayload(BaseModel):
    """Decoded JWT access token payload.

    Attributes:
        sub: Username (JWT subject claim).
        role: User role for RBAC enforcement.
        exp: Token expiration timestamp (epoch seconds).
        sid: Server-side session ID for immediate revocation.
        jti: Unique token ID for revocation lookup.
    """

    sub: str  # username
    role: str
    exp: int | None = None
    sid: str | None = None  # session_id — present on all new tokens
    jti: str | None = None  # JWT ID — unique per token


class UpdateUserRoleRequest(BaseModel):
    """PATCH /auth/users/:username/role — change a user's role."""

    role: UserRole


class UpdateUserDisabledRequest(BaseModel):
    """PATCH /auth/users/:username/disabled — enable/disable a user."""

    disabled: bool


class UpdateUserStatusRequest(BaseModel):
    """PATCH /auth/users/:username/status — change account lifecycle status."""

    status: AccountStatus
    reason: str | None = Field(None, max_length=500)


class UserResponse(BaseModel):
    """Public user information (no password hash)."""

    id: str
    username: str
    email: str
    role: UserRole
    disabled: bool
    totp_enabled: bool = False
    status: AccountStatus = AccountStatus.active


class UsersListResponse(BaseModel):
    """GET /auth/users — list of all users."""

    users: list[UserResponse]
    total: int


class SessionResponse(BaseModel):
    """Public session information for the session management UI."""

    id: str
    username: str
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str
    is_active: bool
    is_current: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None


class SessionsListResponse(BaseModel):
    """GET /auth/sessions — list of user's active sessions."""

    sessions: list[SessionResponse]
    total: int


class RevokeSessionRequest(BaseModel):
    """DELETE /auth/sessions/:id — reason for revoking a session."""

    reason: str = Field(default="user_revoked", max_length=200)


class PasswordPolicyResponse(BaseModel):
    """GET /auth/password-policy — current password policy configuration."""

    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special: bool
    history_count: int
    max_age_days: int | None
    check_breached: bool


class OIDCLoginResponse(BaseModel):
    """GET /auth/oidc/login — redirect URL for OIDC provider."""

    authorization_url: str


class SAMLLoginResponse(BaseModel):
    """SAML redirect URL response."""

    redirect_url: str
