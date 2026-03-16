"""Tenant domain entities.

Each tenant maps to an isolated MongoDB database. The tenant registry
lives in a shared master database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from utils.dt import utc_now


@dataclass
class Tenant:
    """A customer tenant with its own isolated database.

    Attributes:
        id: Unique identifier (MongoDB ObjectId as string).
        name: Human-readable tenant name.
        slug: URL-safe identifier used in subdomain or X-Tenant-ID header.
        database_name: MongoDB database name for this tenant's data.
        created_at: ISO timestamp of creation.
        disabled: Whether the tenant is deactivated.
        plan: Subscription plan (standard, enterprise).
    """

    id: str = ""
    name: str = ""
    slug: str = ""
    database_name: str = ""
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    disabled: bool = False
    plan: str = "standard"
