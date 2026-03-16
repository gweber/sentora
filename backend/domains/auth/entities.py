"""Auth domain entities.

Defines user roles, account status, the User model, and Session model
used throughout the authentication system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    """Role-based access control levels.

    Attributes:
        super_admin: Platform-wide access (SaaS only).
        admin: Full access — can manage users, trigger syncs, modify config.
        analyst: Can create/edit fingerprints, run classifications, view all data.
        viewer: Read-only access to dashboards and classification results.
    """

    super_admin = "super_admin"
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class AccountStatus(StrEnum):
    """User account lifecycle states.

    Attributes:
        invited: Invitation sent, user has not yet set a password.
        active: Fully active account that can authenticate.
        suspended: Temporarily locked by admin — can be reactivated.
        deactivated: Permanently disabled — retains data for audit.
        deleted: Soft-deleted — data retained for compliance retention period.
    """

    invited = "invited"
    active = "active"
    suspended = "suspended"
    deactivated = "deactivated"
    deleted = "deleted"


@dataclass
class User:
    """Application user.

    Attributes:
        id: Unique identifier (MongoDB ObjectId as string).
        username: Unique login name.
        email: User email address.
        role: RBAC role controlling endpoint access.
        disabled: Whether the account is deactivated (legacy compat).
        status: Account lifecycle status (replaces ``disabled``).
        hashed_password: bcrypt hash (never exposed in API responses).
        totp_secret: Base32-encoded TOTP secret for 2FA (None if not set up).
        totp_enabled: Whether TOTP 2FA has been verified and activated.
        oidc_subject: OIDC provider subject identifier.
        saml_subject: SAML provider subject identifier.
        tenant_id: Tenant context for multi-tenancy.
        password_history: List of previous password hashes for reuse prevention.
        password_changed_at: Timestamp of most recent password change.
        failed_login_attempts: Consecutive failed login count for lockout.
        locked_until: Account lockout expiry timestamp.
        known_user_agents: Set of previously seen User-Agent strings.
        last_login_ip: IP address of most recent successful login.
        last_login_country: Country code of most recent login (GeoIP).
        last_login_at: Timestamp of most recent successful login.
    """

    id: str
    username: str
    email: str
    role: UserRole = field(default=UserRole.viewer)
    disabled: bool = False
    status: AccountStatus = field(default=AccountStatus.active)
    hashed_password: str = ""
    totp_secret: str | None = None
    totp_enabled: bool = False
    oidc_subject: str | None = None
    saml_subject: str | None = None
    tenant_id: str | None = None
    password_history: list[dict[str, object]] = field(default_factory=list)
    password_changed_at: datetime | None = None
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    known_user_agents: list[str] = field(default_factory=list)
    last_login_ip: str | None = None
    last_login_country: str | None = None
    last_login_at: datetime | None = None


@dataclass
class Session:
    """Server-side session tracking for immediate invalidation and device management.

    Each login creates a session bound to a refresh token family. The session_id
    is embedded in the JWT access token so revocation takes effect on the next
    API call (not just on refresh).

    Attributes:
        id: Unique session identifier (UUID).
        user_id: MongoDB ObjectId of the user (as string).
        username: Username for display and lookup.
        tenant_id: Tenant context for multi-tenancy.
        created_at: When the session was established.
        last_active_at: Most recent API call using this session.
        expires_at: Absolute session expiry (even if actively used).
        ip_address: Client IP at session creation.
        user_agent: Client User-Agent string at session creation.
        is_active: Whether the session is still valid.
        revoked_at: When the session was revoked (None if active).
        revoked_reason: Why the session was revoked.
        refresh_token_family: Links session to the token rotation chain.
    """

    id: str
    user_id: str
    username: str
    tenant_id: str | None
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str
    is_active: bool = True
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    refresh_token_family: str = ""
