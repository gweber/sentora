# Fingerprint Library & Subscriptions

This guide explains how to use the fingerprint library to share reusable fingerprint templates across S1 groups.

---

## Overview

The **Fingerprint Library** is a shared catalog of fingerprint templates. Each library entry contains a set of glob-pattern markers that describe a piece of software. Groups can **subscribe** to library entries — the entry's markers are automatically copied into the group's fingerprint.

When a library entry is updated, subscribed groups can be **re-synced** to pick up the new markers.

---

## Browsing the Library

Navigate to **Library** in the sidebar. The browser view shows:

- **Stats bar** — Total entries, entries by source (manual, NIST CPE, MITRE, etc.), entries by status.
- **Filters** — Filter by status, source, or search by name/vendor.
- **Entry cards** — Each card shows the entry name, vendor, category, source badge, subscriber count, and marker count.

Click any entry to open its detail page.

---

## Creating a Library Entry

1. In the Library browser, click **Create Entry** (requires analyst or admin role).
2. Fill in:
   - **Name** — Human-readable name (e.g. "Google Chrome").
   - **Vendor** — Software vendor.
   - **Category** — Taxonomy category.
   - **Description** — Optional description.
   - **Tags** — Free-form tags for filtering.
   - **Markers** — Add glob patterns with weights. Each marker needs a pattern (e.g. `*chrome*`) and a display name.
3. Click **Create**. The entry is created with status `published` by default.

---

## Entry Lifecycle

Library entries follow a workflow:

| Status | Description |
|--------|-------------|
| `draft` | Work in progress. Not visible to subscribers. |
| `pending_review` | Submitted for review (community entries). |
| `published` | Active and available for subscription. |
| `deprecated` | No longer recommended. Existing subscriptions continue to work. |

Admins can transition entries between states using the **Publish** and **Deprecate** buttons on the entry detail page.

---

## Subscribing a Group

1. Open a library entry's detail page.
2. Click **Subscribe Group**.
3. Select the S1 group you want to subscribe.
4. Choose whether to enable **auto-update** (on by default).
5. Click **Subscribe**.

The entry's markers are immediately copied into the group's fingerprint with:
- `source = "library"` — distinguishes library markers from manual/statistical markers.
- `added_by = "library:{entry_id}"` — provenance tracking for clean removal.

---

## Unsubscribing

1. On the entry detail page, find the subscription in the subscriptions list.
2. Click **Unsubscribe**.

All markers with matching provenance (`added_by = "library:{entry_id}"`) are removed from the group's fingerprint. Manually-added markers are never affected.

---

## Syncing Stale Subscriptions

When a library entry is updated, its internal `version` is bumped. Subscriptions track the `synced_version` they last copied.

To sync all stale subscriptions:

```bash
# Via API
curl -X POST http://localhost:5002/api/v1/library/subscriptions/sync \
  -H "Authorization: Bearer <token>"
```

Or use the **Sync Subscriptions** button in the Library admin UI.

The response reports how many subscriptions were synced.

---

## Viewing Group Subscriptions

To see which library entries a group is subscribed to:

```bash
curl http://localhost:5002/api/v1/library/subscriptions/group/{group_id} \
  -H "Authorization: Bearer <token>"
```

---

## Tips

- **Start with published entries** — Filter by `status=published` to see only active, vetted entries.
- **Use tags for organization** — Tag entries with domain-specific labels (e.g. `ot`, `browser`, `security_tool`).
- **Review before subscribing** — Preview an entry's markers to ensure they match your environment's naming conventions.
- **Bulk ingestion** — Use the [Ingestion Sources](ingestion-sources.md) to populate the library from public databases.

---

## Role Requirements by Deployment Mode

| Action | On-Prem | SaaS |
|--------|---------|------|
| Browse library entries | Any authenticated user | Any authenticated user |
| Create/update entries | `analyst` or `admin` | `analyst` or `admin` |
| Subscribe/unsubscribe groups | `analyst` or `admin` | `analyst` or `admin` |
| Manage ingestion sources | `admin` | `super_admin` |
| Trigger ingestion | `admin` | `super_admin` |

In SaaS mode, library entries and ingestion runs are stored in the shared master database (accessible to all tenants). Subscriptions and fingerprint markers are stored per-tenant.
