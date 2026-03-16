"""Central MongoDB index definitions for Sentora.

Call ``ensure_all_indexes(db)`` once at application startup. MongoDB's
``create_index`` is idempotent — it is safe to call on every restart.
"""

from __future__ import annotations

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_all_indexes(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Create all application indexes across every collection."""

    # ── s1_agents ─────────────────────────────────────────────────────────────
    # Primary key for upserts and per-agent lookups
    await db["s1_agents"].create_index("s1_agent_id", unique=True, background=True)
    # Filtering by site and group (list_agents, aggregations, fingerprint matcher)
    await db["s1_agents"].create_index("site_id", background=True)
    await db["s1_agents"].create_index("group_id", background=True)
    # Hostname search (regex)
    await db["s1_agents"].create_index("hostname", background=True)
    # Stale agent dashboard queries: count_documents({"last_active": {"$lt": cutoff}})
    await db["s1_agents"].create_index("last_active", background=True)
    # Denormalized app names — written by sync, read by classification and tag matcher
    await db["s1_agents"].create_index("installed_app_names", background=True)
    # Tags — for future filtering of agents by their current S1 tags
    await db["s1_agents"].create_index("tags", background=True)
    # synced_at — full sync uses this to delete stale agents instead of $nin with 150k+ IDs
    await db["s1_agents"].create_index("synced_at", background=True)

    # ── s1_installed_apps ─────────────────────────────────────────────────────
    # Wrapped in try/except: background index builds on this large collection can
    # cause transient conflicts on rapid restarts (uvicorn --reload). All indexes
    # here are persistent from previous successful runs so a transient failure is safe.
    try:
        await db["s1_installed_apps"].create_index("id", unique=True, sparse=True, background=True)
        await db["s1_installed_apps"].create_index("agent_id", background=True)
        await db["s1_installed_apps"].create_index("normalized_name", background=True)
        await db["s1_installed_apps"].create_index(
            [("agent_id", 1), ("normalized_name", 1)], background=True
        )
        await db["s1_installed_apps"].create_index("last_synced_at", background=True)
        await db["s1_installed_apps"].create_index("publisher", background=True)
        await db["s1_installed_apps"].create_index("risk_level", background=True)
        await db["s1_installed_apps"].create_index(
            [("normalized_name", 1), ("agent_id", 1)], background=True
        )
        await db["s1_installed_apps"].create_index("active", background=True, sparse=True)
    except Exception as exc:
        logger.warning("s1_installed_apps index setup skipped (transient conflict): {}", exc)

    # ── s1_groups ─────────────────────────────────────────────────────────────
    await db["s1_groups"].create_index("s1_group_id", unique=True, background=True)
    await db["s1_groups"].create_index("site_id", background=True)

    # ── s1_sites ──────────────────────────────────────────────────────────────
    await db["s1_sites"].create_index("s1_site_id", unique=True, background=True)
    await db["s1_sites"].create_index("name", background=True)

    # ── s1_tags ────────────────────────────────────────────────────────────────
    await db["s1_tags"].create_index("s1_tag_id", unique=True, background=True)
    await db["s1_tags"].create_index("name", background=True)
    await db["s1_tags"].create_index("scope", background=True)

    # ── s1_sync_runs ──────────────────────────────────────────────────────────
    # Status + completed_at: used in GET /status to find last completed run
    await db["s1_sync_runs"].create_index([("status", 1), ("completed_at", -1)], background=True)
    # started_at: used in GET /history
    await db["s1_sync_runs"].create_index([("started_at", -1)], background=True)

    # ── classification_results ────────────────────────────────────────────────
    # agent_id is unique — created by classification repo, but declared here too
    # for completeness. create_index is idempotent.
    await db["classification_results"].create_index("agent_id", unique=True, background=True)
    await db["classification_results"].create_index("classification", background=True)
    await db["classification_results"].create_index("current_group_id", background=True)
    await db["classification_results"].create_index("run_id", background=True)
    # hostname search in classification list
    await db["classification_results"].create_index("hostname", background=True)
    # acknowledged filter
    await db["classification_results"].create_index("acknowledged", background=True)
    # computed_at sort
    await db["classification_results"].create_index([("computed_at", -1)], background=True)

    # ── classification_runs ───────────────────────────────────────────────────
    await db["classification_runs"].create_index([("started_at", -1)], background=True)
    await db["classification_runs"].create_index("status", background=True)

    # ── fingerprints ──────────────────────────────────────────────────────────
    await db["fingerprints"].create_index("group_id", unique=True, background=True)

    # ── fingerprint_suggestions ───────────────────────────────────────────────
    await db["fingerprint_suggestions"].create_index("group_id", background=True)
    await db["fingerprint_suggestions"].create_index(
        [("group_id", 1), ("status", 1)], background=True
    )
    await db["fingerprint_suggestions"].create_index(
        [("group_id", 1), ("score", -1)], background=True
    )

    # ── auto_fingerprint_proposals ────────────────────────────────────────────
    # Unique per group — upserted on each re-generate run
    await db["auto_fingerprint_proposals"].create_index("group_id", unique=True, background=True)
    # Filtered by status (pending/applied/dismissed) + sorted by quality_score
    await db["auto_fingerprint_proposals"].create_index("status", background=True)
    await db["auto_fingerprint_proposals"].create_index([("quality_score", -1)], background=True)

    # ── app_summaries (materialized view for /apps/ list) ────────────────────
    await db["app_summaries"].create_index("normalized_name", unique=True, background=True)
    await db["app_summaries"].create_index("agent_count", background=True)
    await db["app_summaries"].create_index("category", background=True)

    # ── taxonomy_categories ──────────────────────────────────────────────────
    await db["taxonomy_categories"].create_index("key", unique=True, background=True)

    # ── taxonomy_entries ──────────────────────────────────────────────────────
    await db["taxonomy_entries"].create_index("category", background=True)
    await db["taxonomy_entries"].create_index("name", background=True)
    await db["taxonomy_entries"].create_index(
        [("name", "text"), ("patterns", "text")], background=True
    )

    # ── tag_rules ─────────────────────────────────────────────────────────────
    await db["tag_rules"].create_index("tag_name", unique=True, background=True)
    await db["tag_rules"].create_index("apply_status", background=True)
    await db["tag_rules"].create_index([("updated_at", -1)], background=True)

    # ── audit_log ─────────────────────────────────────────────────────────────
    # Primary sort field + TTL index — auto-delete audit entries older than 90 days.
    # Uses the ``timestamp`` field (native datetime) for both sorting and TTL.
    await db["audit_log"].create_index([("timestamp", -1)], background=True)
    await db["audit_log"].create_index(
        "timestamp", expireAfterSeconds=90 * 24 * 60 * 60, background=True
    )
    # Filter fields used in the audit router
    await db["audit_log"].create_index("domain", background=True)
    await db["audit_log"].create_index("actor", background=True)
    await db["audit_log"].create_index("action", background=True)
    await db["audit_log"].create_index("status", background=True)
    # Hash-chain fields — sequence is the primary ordering for chained entries
    await db["audit_log"].create_index("sequence", unique=True, sparse=True, background=True)
    await db["audit_log"].create_index("epoch", sparse=True, background=True)
    await db["audit_log"].create_index(
        [("epoch", 1), ("sequence", 1)], sparse=True, background=True
    )

    # ── users (auth domain) ──────────────────────────────────────────────────
    await db["users"].create_index("username", unique=True, background=True)
    await db["users"].create_index("email", unique=True, background=True)
    # SSO provider subject identifiers — sparse so null values don't conflict
    await db["users"].create_index("oidc_subject", unique=True, sparse=True, background=True)
    await db["users"].create_index("saml_subject", unique=True, sparse=True, background=True)
    # Account lifecycle status — for admin listing and login checks
    await db["users"].create_index("status", background=True)
    # Account lockout — for lockout expiry queries
    await db["users"].create_index("locked_until", sparse=True, background=True)

    # ── sessions (server-side session registry) ──────────────────────────────
    # Primary lookup by session_id (used on every authenticated request via cache)
    await db["sessions"].create_index("session_id", unique=True, background=True)
    # Per-user session listing and revocation
    await db["sessions"].create_index("username", background=True)
    # Active session queries (list, count)
    await db["sessions"].create_index([("username", 1), ("is_active", 1)], background=True)
    # Token family binding — find session by refresh token family
    await db["sessions"].create_index("refresh_token_family", background=True)
    # TTL — auto-expire sessions after their absolute expiry
    await db["sessions"].create_index("expires_at", expireAfterSeconds=0, background=True)
    # Revocation cache refresh — recently revoked sessions
    await db["sessions"].create_index(
        [("is_active", 1), ("revoked_at", -1)], sparse=True, background=True
    )

    # ── refresh_tokens (JWT refresh token storage) ───────────────────────────
    # Primary lookup for token validation
    await db["refresh_tokens"].create_index("token_id", unique=True, background=True)
    # Family-based revocation (reuse detection, logout)
    await db["refresh_tokens"].create_index("family_id", background=True)
    # Per-user revocation (logout all devices, role change)
    await db["refresh_tokens"].create_index("username", background=True)
    # TTL — auto-expire tokens after they've passed their expiry
    await db["refresh_tokens"].create_index("expires_at", expireAfterSeconds=0, background=True)

    # ── oidc_pending_states (OIDC CSRF state tokens) ───────────────────────────
    # TTL index — auto-expire pending OIDC states after 5 minutes (AUDIT-021).
    # Tighter window reduces the attack surface for CSRF state replay.
    await db["oidc_pending_states"].create_index(
        "created_at", expireAfterSeconds=300, background=True
    )

    # ── saml_pending_requests (SAML CSRF request IDs) ────────────────────────
    # TTL index — auto-expire pending SAML request IDs after 5 minutes (AUDIT-022).
    await db["saml_pending_requests"].create_index(
        "created_at", expireAfterSeconds=300, background=True
    )

    # ── saml_token_exchange (one-time SAML nonce → JWT token pairs) ───────
    # TTL index — auto-expire exchange nonces after 2 minutes (AUDIT-023).
    # Token exchange should complete within seconds; 2 min is generous.
    await db["saml_token_exchange"].create_index(
        "created_at", expireAfterSeconds=120, background=True
    )

    # ── distributed_locks ─────────────────────────────────────────────────────
    # TTL index — MongoDB automatically deletes documents whose expires_at is
    # in the past, cleaning up stale locks from crashed processes.
    await db["distributed_locks"].create_index("expires_at", expireAfterSeconds=0, background=True)

    # ── leader_election ──────────────────────────────────────────────────────
    # TTL index — auto-clean expired leadership claims from crashed workers.
    await db["leader_election"].create_index("expires_at", expireAfterSeconds=0, background=True)

    # ── library_entries ──────────────────────────────────────────────────────
    await db["library_entries"].create_index("name", background=True)
    await db["library_entries"].create_index("vendor", background=True)
    await db["library_entries"].create_index("category", background=True)
    await db["library_entries"].create_index("source", background=True)
    await db["library_entries"].create_index("status", background=True)
    await db["library_entries"].create_index("tags", background=True)
    await db["library_entries"].create_index(
        [("source", 1), ("upstream_id", 1)], unique=True, sparse=True, background=True
    )
    await db["library_entries"].create_index(
        [("subscriber_count", -1), ("name", 1)], background=True
    )
    await db["library_entries"].create_index(
        [("name", "text"), ("vendor", "text"), ("description", "text")],
        background=True,
    )

    # ── library_subscriptions ────────────────────────────────────────────────
    await db["library_subscriptions"].create_index(
        [("group_id", 1), ("library_entry_id", 1)], unique=True, background=True
    )
    await db["library_subscriptions"].create_index("group_id", background=True)
    await db["library_subscriptions"].create_index("library_entry_id", background=True)

    # ── library_ingestion_runs ───────────────────────────────────────────────
    await db["library_ingestion_runs"].create_index([("started_at", -1)], background=True)
    await db["library_ingestion_runs"].create_index("source", background=True)
    await db["library_ingestion_runs"].create_index([("source", 1), ("status", 1)], background=True)

    # ── library_ingestion_checkpoint ─────────────────────────────────────────
    # Documents keyed by _id = "source:<name>"; no extra indexes needed beyond
    # the default _id index. The collection uses replace_one upserts.

    # ── backup_history ──────────────────────────────────────────────────────
    await db["backup_history"].create_index([("timestamp", -1)], background=True)
    await db["backup_history"].create_index("status", background=True)

    # ── compliance_reports (legacy — retained for data access) ───────────
    await db["compliance_reports"].create_index([("generated_at", -1)], background=True)
    await db["compliance_reports"].create_index("framework", background=True)
    await db["compliance_reports"].create_index("status", background=True)

    # ── compliance_framework_config ────────────────────────────────────
    await db["compliance_framework_config"].create_index(
        "framework_id", unique=True, background=True
    )

    # ── compliance_control_config ──────────────────────────────────────
    await db["compliance_control_config"].create_index(
        [("control_id", 1), ("framework_id", 1)], unique=True, background=True
    )
    await db["compliance_control_config"].create_index("framework_id", background=True)

    # ── compliance_custom_controls ─────────────────────────────────────
    await db["compliance_custom_controls"].create_index("control_id", unique=True, background=True)
    await db["compliance_custom_controls"].create_index("framework_id", background=True)

    # ── compliance_results (check result snapshots) ────────────────────
    await db["compliance_results"].create_index("run_id", background=True)
    await db["compliance_results"].create_index(
        [("control_id", 1), ("checked_at", -1)], background=True
    )
    await db["compliance_results"].create_index("framework_id", background=True)
    await db["compliance_results"].create_index([("checked_at", -1)], background=True)
    await db["compliance_results"].create_index("status", background=True)
    # TTL — auto-delete results older than 90 days
    await db["compliance_results"].create_index(
        "checked_at", expireAfterSeconds=90 * 24 * 60 * 60, background=True
    )

    # ── compliance_schedule ────────────────────────────────────────────
    # Single document keyed by _id="schedule" — no extra indexes needed

    # ── enforcement_rules ──────────────────────────────────────────────
    await db["enforcement_rules"].create_index("enabled", background=True)
    await db["enforcement_rules"].create_index("taxonomy_category_id", background=True)
    await db["enforcement_rules"].create_index([("created_at", -1)], background=True)

    # ── enforcement_results ────────────────────────────────────────────
    await db["enforcement_results"].create_index("run_id", background=True)
    await db["enforcement_results"].create_index(
        [("rule_id", 1), ("checked_at", -1)], background=True
    )
    await db["enforcement_results"].create_index([("checked_at", -1)], background=True)
    await db["enforcement_results"].create_index("status", background=True)
    # TTL — auto-delete results older than 90 days
    await db["enforcement_results"].create_index(
        "checked_at", expireAfterSeconds=90 * 24 * 60 * 60, background=True
    )

    # ── api_keys ──────────────────────────────────────────────────────────────
    # Primary lookup by key hash (used on every API key auth request)
    await db["api_keys"].create_index("key_hash", unique=True, background=True)
    # Per-tenant listing
    await db["api_keys"].create_index("tenant_id", background=True)
    # Tenant + active filter for listing
    await db["api_keys"].create_index([("tenant_id", 1), ("is_active", 1)], background=True)
    # Grace period lookup (rotated keys still valid temporarily)
    await db["api_keys"].create_index("grace_expires_at", sparse=True, background=True)
    # Created-at sort for listing
    await db["api_keys"].create_index([("created_at", -1)], background=True)

    logger.info("MongoDB indexes ensured")
