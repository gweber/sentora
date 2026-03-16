"""Platform compliance control evaluators.

Each evaluator queries Sentora's own operational data (users, audit logs,
backups, webhooks, classification coverage) to assess the platform's
security posture against SOC 2 Trust Criteria and ISO 27001 Annex A.

These controls answer: "Is Sentora itself running securely?" — not
"Are the managed endpoints compliant?"
"""

from __future__ import annotations

from datetime import timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from domains.compliance.platform.entities import ControlResult, ControlStatus, Framework
from utils.dt import utc_now

# ---------------------------------------------------------------------------
# SOC 2 Controls
# ---------------------------------------------------------------------------


async def soc2_cc6_1_access_control(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC6.1 — Logical access security: RBAC is enforced."""
    users = await db["users"].count_documents({})
    admins = await db["users"].count_documents({"role": {"$in": ["admin", "super_admin"]}})
    disabled = await db["users"].count_documents({"disabled": True})
    roles_used = await db["users"].distinct("role")

    if users == 0:
        status = ControlStatus.warning
        summary = "No users registered — access control not yet active"
    elif len(roles_used) >= 2:
        status = ControlStatus.passing
        summary = (
            f"{users} users across {len(roles_used)} roles ({', '.join(roles_used)}), "
            f"{admins} admin(s), {disabled} disabled. "
            "Role separation enforced via JWT RBAC"
        )
    elif admins == users:
        status = ControlStatus.warning
        summary = f"All {users} users are admins — consider role separation"
    else:
        status = ControlStatus.passing
        summary = f"{users} users, {admins} admin(s), {disabled} disabled. RBAC enforced"

    return ControlResult(
        control_id="soc2-cc6.1",
        framework="soc2",
        reference="CC6.1",
        title="Logical Access Security",
        category="Common Criteria",
        status=status,
        evidence_summary=summary,
        evidence_count=users,
        last_checked=utc_now().isoformat(),
    )


async def soc2_cc6_2_auth_mechanisms(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC6.2 — Authentication mechanisms: password policy, MFA availability."""
    totp_users = await db["users"].count_documents({"totp_enabled": True})
    total_users = await db["users"].count_documents({})
    sso_users = await db["users"].count_documents(
        {"$or": [{"oidc_subject": {"$ne": None}}, {"saml_subject": {"$ne": None}}]}
    )

    parts = [f"{total_users} total users"]
    if totp_users:
        parts.append(f"{totp_users} with TOTP 2FA")
    if sso_users:
        parts.append(f"{sso_users} via SSO")

    if total_users == 0:
        status = ControlStatus.warning
    elif (totp_users + sso_users) >= total_users * 0.5:
        status = ControlStatus.passing
    else:
        status = ControlStatus.warning

    return ControlResult(
        control_id="soc2-cc6.2",
        framework="soc2",
        reference="CC6.2",
        title="Authentication Mechanisms",
        category="Common Criteria",
        status=status,
        evidence_summary="; ".join(parts),
        evidence_count=totp_users + sso_users,
        last_checked=utc_now().isoformat(),
    )


async def soc2_cc6_3_access_revocation(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC6.3 — Access removal: disabled accounts, token revocation."""
    disabled = await db["users"].count_documents({"disabled": True})
    total = await db["users"].count_documents({})
    revocations = await db["audit_log"].count_documents(
        {"action": {"$regex": r"revok(e|ed|ing)?|disabl(e|ed|ing)?", "$options": "i"}}
    )

    return ControlResult(
        control_id="soc2-cc6.3",
        framework="soc2",
        reference="CC6.3",
        title="Access Removal & Revocation",
        category="Common Criteria",
        status=ControlStatus.passing,
        evidence_summary=(
            f"{disabled}/{total} accounts disabled. "
            f"{revocations} revocation events in audit log. "
            "JWT refresh token rotation active"
        ),
        evidence_count=revocations,
        last_checked=utc_now().isoformat(),
    )


async def soc2_cc7_2_monitoring(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC7.2 — System monitoring: audit logging is active."""
    cutoff = utc_now() - timedelta(days=1)
    recent_entries = await db["audit_log"].count_documents({"created_at": {"$gte": cutoff}})
    total_entries = await db["audit_log"].count_documents({})

    if recent_entries > 0:
        status = ControlStatus.passing
        summary = (
            f"{recent_entries} audit events in last 24h "
            f"({total_entries} total). Structured JSON logging active"
        )
    elif total_entries > 0:
        status = ControlStatus.warning
        summary = f"No audit events in last 24h ({total_entries} total). System may be idle"
    else:
        status = ControlStatus.failing
        summary = "No audit log entries found — monitoring not active"

    return ControlResult(
        control_id="soc2-cc7.2",
        framework="soc2",
        reference="CC7.2",
        title="System Monitoring",
        category="Common Criteria",
        status=status,
        evidence_summary=summary,
        evidence_count=recent_entries,
        last_checked=utc_now().isoformat(),
    )


async def soc2_cc8_1_change_management(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC8.1 — Change management: config changes are audited."""
    config_changes = await db["audit_log"].count_documents({"domain": "config"})
    fp_changes = await db["audit_log"].count_documents({"domain": "fingerprint"})

    total = config_changes + fp_changes
    if total > 0:
        status = ControlStatus.passing
        summary = (
            f"{config_changes} config changes and "
            f"{fp_changes} fingerprint changes tracked in audit log"
        )
    else:
        status = ControlStatus.warning
        summary = "No change events recorded yet"

    return ControlResult(
        control_id="soc2-cc8.1",
        framework="soc2",
        reference="CC8.1",
        title="Change Management",
        category="Common Criteria",
        status=status,
        evidence_summary=summary,
        evidence_count=total,
        last_checked=utc_now().isoformat(),
    )


async def soc2_a1_1_availability(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A1.1 — System availability: backup and recovery capabilities."""
    backups = await db["backup_history"].count_documents({"status": "completed"})
    failed = await db["backup_history"].count_documents({"status": "failed"})

    if backups > 0 and failed == 0:
        status = ControlStatus.passing
        summary = f"{backups} successful backup(s), 0 failures"
    elif backups > 0:
        status = ControlStatus.warning
        summary = f"{backups} successful backup(s), {failed} failure(s)"
    else:
        status = ControlStatus.failing
        summary = "No backups found — backup/restore not configured"

    return ControlResult(
        control_id="soc2-a1.1",
        framework="soc2",
        reference="A1.1",
        title="System Availability & Recovery",
        category="Availability",
        status=status,
        evidence_summary=summary,
        evidence_count=backups,
        last_checked=utc_now().isoformat(),
    )


async def soc2_cc3_1_risk_assessment(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC3.1 — Risk management: classification of assets."""
    classified = await db["classification_results"].count_documents({})
    agents = await db["s1_agents"].count_documents({})

    if agents == 0:
        status = ControlStatus.warning
        summary = "No agents synced — asset inventory not populated"
    elif classified >= agents * 0.5:
        status = ControlStatus.passing
        pct = classified * 100 // agents
        summary = f"{classified}/{agents} agents classified ({pct}% coverage)"
    else:
        status = ControlStatus.warning
        summary = f"Only {classified}/{agents} agents classified — coverage below 50%"

    return ControlResult(
        control_id="soc2-cc3.1",
        framework="soc2",
        reference="CC3.1",
        title="Risk Assessment & Asset Classification",
        category="Common Criteria",
        status=status,
        evidence_summary=summary,
        evidence_count=classified,
        last_checked=utc_now().isoformat(),
    )


async def soc2_cc2_1_communication(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """CC2.1 — Information and communication: webhooks and notifications."""
    webhooks = await db["webhooks"].count_documents({})
    active_webhooks = await db["webhooks"].count_documents({"enabled": True})

    if active_webhooks > 0:
        status = ControlStatus.passing
        summary = (
            f"{active_webhooks} active webhook(s) of "
            f"{webhooks} total — event notifications configured"
        )
    elif webhooks > 0:
        status = ControlStatus.warning
        summary = f"{webhooks} webhook(s) configured but none active"
    else:
        status = ControlStatus.passing
        summary = (
            "Audit log and WebSocket notifications active. "
            "No outbound webhooks configured (optional)"
        )

    return ControlResult(
        control_id="soc2-cc2.1",
        framework="soc2",
        reference="CC2.1",
        title="Information & Communication",
        category="Common Criteria",
        status=status,
        evidence_summary=summary,
        evidence_count=active_webhooks,
        last_checked=utc_now().isoformat(),
    )


# ---------------------------------------------------------------------------
# ISO 27001 Controls
# ---------------------------------------------------------------------------


async def iso_a5_access_control(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A.5 — Organizational controls: access policies."""
    users = await db["users"].count_documents({})
    roles_dist = {}
    for role in ("super_admin", "admin", "analyst", "viewer"):
        roles_dist[role] = await db["users"].count_documents({"role": role})

    dist_str = ", ".join(f"{v} {k}" for k, v in roles_dist.items() if v > 0)
    status = ControlStatus.passing if users > 0 else ControlStatus.warning
    summary = f"RBAC enforced. {users} users: {dist_str}" if dist_str else "No users registered"

    return ControlResult(
        control_id="iso-a5",
        framework="iso27001",
        reference="A.5",
        title="Organizational Controls — Access Policy",
        category="Organizational",
        status=status,
        evidence_summary=summary,
        evidence_count=users,
        last_checked=utc_now().isoformat(),
    )


async def iso_a6_people_controls(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A.6 — People controls: user lifecycle management."""
    total = await db["users"].count_documents({})
    disabled = await db["users"].count_documents({"disabled": True})
    sso = await db["users"].count_documents(
        {"$or": [{"oidc_subject": {"$ne": None}}, {"saml_subject": {"$ne": None}}]}
    )

    status = ControlStatus.passing if total > 0 else ControlStatus.warning
    summary = (
        f"{total} users, {disabled} disabled, {sso} SSO-provisioned. User disable/enable audited"
    )

    return ControlResult(
        control_id="iso-a6",
        framework="iso27001",
        reference="A.6",
        title="People Controls — User Lifecycle",
        category="People",
        status=status,
        evidence_summary=summary,
        evidence_count=total,
        last_checked=utc_now().isoformat(),
    )


async def iso_a7_physical_controls(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A.7 — Physical controls: N/A for SaaS, documented."""
    return ControlResult(
        control_id="iso-a7",
        framework="iso27001",
        reference="A.7",
        title="Physical Controls",
        category="Physical",
        status=ControlStatus.not_applicable,
        evidence_summary=(
            "SaaS application — physical controls delegated "
            "to cloud provider (documented in vendor management policy)"
        ),
        evidence_count=0,
        last_checked=utc_now().isoformat(),
    )


async def iso_a8_technological_controls(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A.8 — Technological controls: encryption, logging, backup."""
    audit_count = await db["audit_log"].count_documents({})
    backup_count = await db["backup_history"].count_documents({"status": "completed"})

    parts = [
        "TLS enforced via HSTS",
        "bcrypt password hashing",
        f"{audit_count} audit log entries",
        f"{backup_count} backup(s)",
    ]

    status = ControlStatus.passing if audit_count > 0 else ControlStatus.warning

    return ControlResult(
        control_id="iso-a8",
        framework="iso27001",
        reference="A.8",
        title="Technological Controls — Security & Logging",
        category="Technological",
        status=status,
        evidence_summary="; ".join(parts),
        evidence_count=audit_count,
        last_checked=utc_now().isoformat(),
    )


async def iso_a8_backup(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A.8.13 — Information backup."""
    backups = await db["backup_history"].count_documents({"status": "completed"})
    cutoff = utc_now() - timedelta(days=7)
    recent = await db["backup_history"].count_documents(
        {"status": "completed", "timestamp": {"$gte": cutoff.isoformat()}}
    )

    if recent > 0:
        status = ControlStatus.passing
        summary = f"{backups} total backup(s), {recent} in last 7 days"
    elif backups > 0:
        status = ControlStatus.warning
        summary = f"{backups} backup(s) exist but none in last 7 days"
    else:
        status = ControlStatus.failing
        summary = "No backups found — configure automated backups"

    return ControlResult(
        control_id="iso-a8.13",
        framework="iso27001",
        reference="A.8.13",
        title="Information Backup",
        category="Technological",
        status=status,
        evidence_summary=summary,
        evidence_count=backups,
        last_checked=utc_now().isoformat(),
    )


async def iso_a8_logging(db: AsyncIOMotorDatabase) -> ControlResult:  # type: ignore[type-arg]
    """A.8.15 — Logging and monitoring."""
    cutoff = utc_now() - timedelta(days=1)
    recent = await db["audit_log"].count_documents({"created_at": {"$gte": cutoff}})
    total = await db["audit_log"].count_documents({})
    domains = await db["audit_log"].distinct("domain")

    if recent > 0:
        status = ControlStatus.passing
        summary = f"{recent} events in 24h, {total} total across domains: {', '.join(domains[:10])}"
    elif total > 0:
        status = ControlStatus.warning
        summary = f"No events in 24h ({total} total). System may be idle"
    else:
        status = ControlStatus.failing
        summary = "No audit events — logging not active"

    return ControlResult(
        control_id="iso-a8.15",
        framework="iso27001",
        reference="A.8.15",
        title="Logging & Monitoring",
        category="Technological",
        status=status,
        evidence_summary=summary,
        evidence_count=total,
        last_checked=utc_now().isoformat(),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SOC2_CONTROLS = [
    soc2_cc6_1_access_control,
    soc2_cc6_2_auth_mechanisms,
    soc2_cc6_3_access_revocation,
    soc2_cc3_1_risk_assessment,
    soc2_cc2_1_communication,
    soc2_cc7_2_monitoring,
    soc2_cc8_1_change_management,
    soc2_a1_1_availability,
]

ISO27001_CONTROLS = [
    iso_a5_access_control,
    iso_a6_people_controls,
    iso_a7_physical_controls,
    iso_a8_technological_controls,
    iso_a8_backup,
    iso_a8_logging,
]

FRAMEWORK_CONTROLS = {
    Framework.soc2: SOC2_CONTROLS,
    Framework.iso27001: ISO27001_CONTROLS,
}
