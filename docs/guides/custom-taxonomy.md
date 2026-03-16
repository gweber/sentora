# Custom Taxonomy Guide

The software catalog (taxonomy) is the foundation of fingerprint matching. Every marker you place in a fingerprint must first exist as a catalog entry with one or more glob patterns. This guide explains how to browse, search, extend, and maintain the catalog.

---

## What Is the Taxonomy?

The taxonomy is a hierarchical list of known software packages, organized by category. Each entry contains:

- **Name** — human-readable display name (e.g., "Siemens WinCC Runtime")
- **Category** — the functional group this software belongs to
- **Patterns** — one or more glob patterns matched against application names as reported by SentinelOne
- **Publisher** — optional; used for display and search filtering
- **Is Universal** — if true, this software is excluded from all fingerprint matching (see [Universal Exclusions](#universal-exclusions))

When an agent's application name matches any pattern in a catalog entry, that entry is considered "present" on that agent.

---

## Built-In Categories

The default seed data includes entries in these categories:

| Category | Examples |
|---|---|
| SCADA/HMI | Siemens WinCC, Wonderware InTouch, Ignition, FactoryTalk View |
| MES | Apriso FlexNet, Siemens Opcenter, Rockwell Plex |
| Labeling | BarTender Enterprise, NiceLabel, ZebraDesigner |
| Water Treatment | SCADA for Water, Ovation, OSIsoft PI |
| CAD/CAM | AutoCAD, SolidWorks, Mastercam, CATIA |
| QA and Testing | Minitab, SPC software, LabVIEW |
| ERP | SAP GUI, Oracle E-Business Suite Client |
| Remote Access | TeamViewer, VNC Viewer, AnyDesk, Secomea |
| General Utilities | (mostly universal exclusions — see below) |

---

## Browsing the Catalog

Navigate to **Catalog** in the top navigation bar (or use the left panel of the Fingerprint Editor).

- Click any category header to expand it and see its entries.
- Each entry shows its name, publisher, and the number of patterns defined.
- Click an entry to open its detail view, which lists the full pattern set and a live preview of which agents in the selected group match.

---

## Searching the Catalog

Use the **Search** field at the top of the left panel. Search is fuzzy and matches against:

- Entry name
- Publisher name
- Pattern text

Example: searching for `siemens` returns all catalog entries from Siemens across all categories.

---

## Adding a New Catalog Entry

If a software package used in your environment is not in the catalog, you must add it before it can be used as a fingerprint marker.

### Navigate to the Add Entry Form

1. Click **Catalog** in the top navigation.
2. Click **Add Entry** (top-right button).

### Fill In the Form Fields

**Name** (required)

The display name of the software. Use the official product name. Examples:
- `Siemens STEP 7 Professional`
- `BarTender Enterprise`
- `Rockwell Automation RSLogix 5000`

**Category** (required)

Select from the existing category list, or type a new category name to create one. Use consistent naming — prefer the existing categories unless the software genuinely does not fit.

**Publisher** (optional, recommended)

The software vendor name. Used for grouping and filtering in search. Example: `Siemens AG`, `Rockwell Automation`, `Seagull Scientific`.

**Patterns** (required — at least one)

One or more glob patterns. Each pattern is matched against the application names that SentinelOne reports for each agent. See [Writing Effective Patterns](#writing-effective-patterns) for guidance.

**Is Universal** (checkbox)

Check this if the software should be excluded from all fingerprint scoring. See [Universal Exclusions](#universal-exclusions).

---

## Writing Effective Patterns

Patterns use glob syntax: `*` matches any sequence of characters, and matching is case-insensitive.

### Basic Examples

| Pattern | Matches | Does Not Match |
|---|---|---|
| `*wincc*` | "Siemens WinCC Runtime Professional", "WinCC Flexible 2008" | "WINCE SDK" |
| `siemens*step*7*` | "Siemens STEP 7 Professional V5.7", "Siemens STEP 7 Basic" | "STEP 7 Micro/WIN" (missing "siemens" prefix) |
| `bartender*` | "BarTender Enterprise", "BarTender Designer" | "bartend helper" — this one would actually match |
| `rockwell*rslogix*5000*` | "Rockwell Automation RSLogix 5000 v34", "Rockwell RSLogix 5000 Programming Software" | "RSLogix 500" (missing "5000") |

### Tips for Writing Good Patterns

**Start broad, then narrow with the preview.**

Begin with a loose pattern like `*rslogix*` and use the Pattern Preview (see below) to see what it matches. If it picks up unrelated entries, make the pattern more specific.

**Account for version numbers.**

Application names in SentinelOne often include version strings. A pattern like `*wincc*` handles all WinCC versions without needing version-specific patterns. Only add version specificity if you need to distinguish between versions.

**Use multiple patterns for the same product.**

If a product is known by several names (legacy name, rebranded name, installer package name), add a pattern for each. Example, for Wonderware InTouch (now AVEVA InTouch):

```
*wonderware*intouch*
*aveva*intouch*
*intouch*hmi*
```

**Avoid overly broad patterns.**

A pattern like `*siemens*` would match every Siemens product — WinCC, STEP 7, TIA Portal, SIMATIC, and more — into a single catalog entry. This makes the entry useless for distinguishing different Siemens products. Keep patterns product-specific.

**Check for common suffixes.**

SentinelOne often appends version numbers, edition names, or architecture labels to application names:
- `Siemens WinCC Runtime Professional V17`
- `Rockwell Automation RSLogix 5000 x64 v34.00.00`
- `BarTender Enterprise 2022 R5`

Patterns like `*wincc*` or `*bartender*enterprise*` handle these automatically without listing every version.

---

## Using Pattern Preview

The pattern preview is available while editing or creating a catalog entry. It is visible in the right side of the entry form.

As you type each pattern, the preview updates in real time, showing:

- **Matched applications** — a sample list of application names from synced agents that match the pattern.
- **Match count** — total number of distinct application name strings matched across all agents.
- **Agent count** — number of agents that have at least one matching application.

**Workflow:**

1. Type your pattern in the Patterns field.
2. Review the matched applications in the preview.
3. If unrelated software appears in the matches, make the pattern more specific.
4. If expected software is missing, broaden the pattern or add a second pattern.
5. Save only when the preview reflects what you expect.

Never save a catalog entry without reviewing the preview — a bad pattern can silently cause all fingerprints using that marker to produce incorrect scores.

---

## Universal Exclusions

Some software is installed on virtually every managed endpoint regardless of its role: antivirus, browsers, OS components, remote management agents, Microsoft Office, and similar tools. Including these in fingerprints would cause every group to look similar, destroying the discriminating power of the matching algorithm.

Mark these entries as **Is Universal = true** to exclude them from fingerprint scoring. Universal entries:

- Are visible in the catalog for reference.
- Can be searched and browsed.
- Are silently skipped during fingerprint score calculation — even if a fingerprint contains a universal marker (which the UI should prevent), it contributes zero weight.
- Are excluded from the Suggestions panel — they will not be suggested as fingerprint markers.

### When to Mark as Universal

Mark an entry as universal if it appears in more than 80–90% of agents across all groups and does not distinguish one group type from another.

**Examples of universal software:**

- Windows Defender / Microsoft Security Client
- Google Chrome, Mozilla Firefox, Microsoft Edge
- Microsoft Office (Word, Excel, Outlook)
- Cisco AnyConnect (unless specific to an IT group)
- 7-Zip, WinZip
- Windows Update components
- SentinelOne Agent itself
- Zoom, Microsoft Teams (in most enterprise environments)

**Examples that should NOT be universal (group-specific):**

- Cisco AnyConnect — if only Remote Access group machines have it, it is a useful fingerprint marker for that group.
- AutoCAD — even though it is widely used, it may be the defining marker for an Engineering Workstations group.
- TeamViewer — in an OT environment, its presence may be a meaningful signal.

Use judgment. If in doubt, check the Suggestions panel — software that appears at high frequency across many diverse groups but with low significance scores is a good universal exclusion candidate.

### When to Mark as Group-Specific

Keep an entry group-specific (Is Universal = false) when:

- It is present in a meaningful fraction of one group but rare in others.
- It is a defining application for a role (e.g., RSLogix for PLC programmers).
- It helps distinguish similar groups from each other (e.g., BarTender distinguishing labeling-focused machines from general OT machines).

---

## Seed Data Reset Procedure

The seed data is the initial set of catalog entries shipped with Sentora. If you have made experimental changes to the catalog and want to return to the factory state, use the seed reset procedure.

> **Warning:** This operation deletes all custom catalog entries and restores only the built-in seed data. Any fingerprints that reference custom entries will lose those markers. This action cannot be undone without a database backup.

### Procedure

1. Take a database backup:
   ```bash
   docker compose exec mongo mongodump \
     --db sentora \
     --archive=/tmp/sentora-backup.gz \
     --gzip
   docker compose cp mongo:/tmp/sentora-backup.gz ./sentora-backup.gz
   ```

2. Navigate to **Settings → Catalog → Reset to Seed Data**.

3. Read the confirmation dialog carefully. Type `RESET` in the confirmation field.

4. Click **Confirm Reset**.

The catalog is cleared and the seed data is re-imported. Existing fingerprints, agents, and sync history are not affected — only catalog entries.

5. Review any fingerprints that used custom entries. Missing markers will be shown with a warning icon in the Fingerprint Editor.

### Alternatively — Restore from Backup

If you want to restore a specific previous state:

```bash
docker compose exec -T mongo mongorestore \
  --db sentora \
  --archive=/dev/stdin \
  --gzip \
  --nsInclude "sentora.taxonomy_entries" \
  < ./sentora-backup.gz
```

This restores only the taxonomy collection from the backup without affecting other collections.
