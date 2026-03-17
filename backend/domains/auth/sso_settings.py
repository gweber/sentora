"""SSO settings resolver — per-tenant OIDC/SAML configuration.

Resolves SSO settings with a two-tier fallback:
1. Per-tenant config from MongoDB (``app_config`` collection) — allows
   each tenant to have its own IdP configuration.
2. Environment variables via ``config.get_settings()`` — global fallback
   for single-tenant deployments or tenants without DB-level config.

This supports the multi-tenant philosophy: each tenant can configure its
own OIDC/SAML provider from the Settings UI without affecting other tenants.
"""

from __future__ import annotations

from dataclasses import dataclass

from motor.motor_asyncio import AsyncIOMotorDatabase

from config import get_settings


@dataclass(frozen=True, slots=True)
class OIDCSettings:
    """Resolved OIDC configuration for a single request context.

    Attributes:
        enabled: Whether OIDC is active.
        discovery_url: OIDC discovery URL.
        client_id: OIDC client ID.
        client_secret: OIDC client secret (plaintext, decrypted from DB).
        redirect_uri: Callback URL for the OIDC flow.
        default_role: Role assigned to new OIDC-provisioned users.
    """

    enabled: bool
    discovery_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    default_role: str


@dataclass(frozen=True, slots=True)
class SAMLSettings:
    """Resolved SAML configuration for a single request context.

    Attributes:
        enabled: Whether SAML is active.
        idp_metadata_url: SAML IdP metadata URL.
        sp_entity_id: SAML SP entity ID.
        sp_acs_url: SAML SP ACS URL (callback).
        default_role: Role assigned to new SAML-provisioned users.
    """

    enabled: bool
    idp_metadata_url: str
    sp_entity_id: str
    sp_acs_url: str
    default_role: str


async def resolve_oidc_settings(db: AsyncIOMotorDatabase) -> OIDCSettings:  # type: ignore[type-arg]
    """Resolve OIDC settings for the current tenant.

    Checks the tenant's ``app_config`` document first. If the OIDC fields
    are empty or OIDC is disabled at the DB level, falls back to the
    global environment-variable settings.

    Args:
        db: The tenant's Motor database handle.

    Returns:
        Fully resolved OIDCSettings for this tenant.
    """
    from utils.crypto import decrypt_field

    env = get_settings()

    # Try tenant-level config from DB
    doc = await db["app_config"].find_one({"_id": "global"})
    if doc and doc.get("oidc_enabled"):
        client_secret_raw = doc.get("oidc_client_secret", "")
        try:
            client_secret = decrypt_field(client_secret_raw) or ""
        except ValueError:
            client_secret = ""

        return OIDCSettings(
            enabled=True,
            discovery_url=doc.get("oidc_discovery_url", ""),
            client_id=doc.get("oidc_client_id", ""),
            client_secret=client_secret,
            redirect_uri=doc.get("oidc_redirect_uri", ""),
            default_role=doc.get("oidc_default_role", "viewer"),
        )

    # Fall back to environment variables
    return OIDCSettings(
        enabled=env.oidc_enabled,
        discovery_url=env.oidc_discovery_url,
        client_id=env.oidc_client_id,
        client_secret=env.oidc_client_secret,
        redirect_uri=env.oidc_redirect_uri,
        default_role=env.oidc_default_role,
    )


async def resolve_saml_settings(db: AsyncIOMotorDatabase) -> SAMLSettings:  # type: ignore[type-arg]
    """Resolve SAML settings for the current tenant.

    Same two-tier fallback as OIDC: DB config first, env vars second.

    Args:
        db: The tenant's Motor database handle.

    Returns:
        Fully resolved SAMLSettings for this tenant.
    """
    env = get_settings()

    doc = await db["app_config"].find_one({"_id": "global"})
    if doc and doc.get("saml_enabled"):
        return SAMLSettings(
            enabled=True,
            idp_metadata_url=doc.get("saml_idp_metadata_url", ""),
            sp_entity_id=doc.get("saml_sp_entity_id", ""),
            sp_acs_url=doc.get("saml_sp_acs_url", ""),
            default_role=doc.get("saml_default_role", "viewer"),
        )

    return SAMLSettings(
        enabled=env.saml_enabled,
        idp_metadata_url=env.saml_idp_metadata_url,
        sp_entity_id=env.saml_sp_entity_id,
        sp_acs_url=env.saml_sp_acs_url,
        default_role=env.saml_default_role,
    )
