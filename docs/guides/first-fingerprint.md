# Building Your First Fingerprint

This walkthrough guides you through creating a software fingerprint for an operational technology (OT) group using a real-world example: a Production Floor group running Siemens WinCC and Rockwell Automation tools.

A fingerprint is the set of software markers that define the expected profile of a machine group. Once built, Sentora automatically compares every agent in that group against its fingerprint and produces a classification verdict.

---

## Prerequisites

Complete the [Quickstart Guide](./quickstart.md) and run your first sync before beginning this walkthrough. You need at least one S1 group with agents and application data loaded.

---

## Step 1: Navigate to the Fingerprint Editor

From the top navigation bar, click **Fingerprint Editor**.

The editor opens in a three-panel layout:

| Panel | Location | Purpose |
|---|---|---|
| Catalog | Left | Searchable library of known software markers |
| Fingerprint Drop Zone | Center | The fingerprint you are currently building |
| Matching Agents | Right | Live preview of agents that match the current fingerprint |

On first load, the center and right panels are empty. You must select a group before editing begins.

---

## Step 2: Select a Group

At the top of the center panel, click the **Group** dropdown. Select the group you want to build a fingerprint for — in this example, **Production Floor OT**.

After selecting the group:
- The right panel populates with all agents in that group, unsorted (no fingerprint exists yet, so all agents are shown).
- The center panel shows an empty drop zone with the prompt: *Drag markers here to start building a fingerprint.*

---

## Step 3: Explore the Catalog

The left panel shows the software catalog organized by category. The categories available in the default seed data include:

- SCADA/HMI
- MES (Manufacturing Execution Systems)
- Labeling
- Water Treatment
- CAD/CAM
- QA and Testing
- ERP
- Remote Access
- General Utilities

Expand the **SCADA/HMI** category by clicking its header.

A list of known SCADA/HMI software entries appears, each showing:
- The software name
- Publisher
- Glob patterns used to match application names reported by S1

Scroll through the list to get a feel for what is available. You can also use the **Search catalog** field at the top of the left panel to jump directly to a specific entry by name, publisher, or pattern.

---

## Step 4: Add Your First Marker

Find **Siemens WinCC** in the SCADA/HMI category.

Drag the **Siemens WinCC** entry from the left panel and drop it onto the center panel's drop zone.

What happens:
- The center panel now shows one marker: Siemens WinCC with a default weight of `1.0`.
- The right panel immediately recalculates. Agents that have at least one application matching the WinCC glob patterns move to the top of the list, sorted by match score (descending).
- A count at the top of the right panel shows how many agents matched.

The match is approximate at this stage — with a single marker, any agent that has WinCC installed will score 100%. The fingerprint becomes more precise as you add more markers.

---

## Step 5: Add a Second Marker

Return to the left panel. Find **Rockwell Automation RSLogix** (also in SCADA/HMI or searchable by name).

Drag it into the center drop zone.

Now the fingerprint has two markers:

| Marker | Weight |
|---|---|
| Siemens WinCC | 1.0 |
| Rockwell Automation RSLogix | 1.0 |

The right panel updates again. It now shows only agents that have **both** WinCC and RSLogix installed. If an agent has only one of the two, its match score drops to 50%, and depending on your threshold settings it may no longer appear in the "matched" section.

This is the core mechanic: adding markers narrows the fingerprint to agents that more precisely match the intended profile.

---

## Step 6: Review Suggestions

Below the drop zone in the center panel, the **Suggestions** section lists applications that appear frequently in the matching agents but are not yet part of the fingerprint.

Suggestions are ranked by a statistical significance score — applications that appear in a high proportion of matching agents and rarely in non-matching agents score higher.

In this example, you might see:

| Suggestion | Frequency in group | Significance |
|---|---|---|
| BarTender Enterprise | 87% | High |
| Siemens S7-PLCSIM | 62% | Medium |
| Adobe Acrobat Reader | 91% | Low (too common across all groups) |

Adobe Acrobat Reader appears frequently but scores low significance because it is common across every group — it does not distinguish Production Floor OT machines from any other machine type.

---

## Step 7: Accept a Suggestion

Click **Accept** next to **BarTender Enterprise**.

It moves from the Suggestions section into the fingerprint drop zone with a default weight of `1.0`.

---

## Step 8: Adjust a Marker Weight

BarTender Enterprise is a labeling application that appears in most but not all Production Floor OT machines. It is a useful signal but not as definitive as WinCC or RSLogix. Reduce its weight to reflect this.

In the center panel, click the weight value next to **BarTender Enterprise**. Change it from `1.0` to `0.6` and press Enter.

The right panel recalculates. Agents without BarTender are penalized less severely than agents without WinCC or RSLogix.

**How weights affect scoring:**

The match score for an agent is calculated as:

```
score = sum of weights for matched markers / sum of all marker weights
```

With the current fingerprint:

| Marker | Weight | Agent has it? |
|---|---|---|
| Siemens WinCC | 1.0 | Yes |
| Rockwell Automation RSLogix | 1.0 | Yes |
| BarTender Enterprise | 0.6 | No |

Score = (1.0 + 1.0) / (1.0 + 1.0 + 0.6) = 2.0 / 2.6 ≈ **0.77** (77%)

An agent that has all three would score 100%. Weights let you express "this is the canonical profile" without hard-requiring every single piece of software.

See [Interpreting Results](./interpreting-results.md) for full details on scoring thresholds and verdict definitions.

---

## Step 9: Save the Fingerprint

Click **Save Fingerprint** at the bottom of the center panel.

Classification for this group runs automatically after saving. A progress indicator appears briefly, then the UI updates with new verdict counts.

---

## Step 10: Review Results on the Dashboard

Click **Dashboard** in the top navigation.

The group **Production Floor OT** now shows classification statistics:

- **Correct** — agents with a high match score against the fingerprint.
- **Ambiguous** — agents whose score for this group is close to their score for another group.
- **Misclassified** — agents with very low match scores (do not look like Production Floor OT machines).
- **Unclassifiable** — agents with no application data, making classification impossible.

---

## Step 11: Investigate Anomalies

Click **Anomalies** in the top navigation.

The Anomalies view lists agents with `misclassified` or `ambiguous` verdicts. For each agent you can:

1. Click the agent row to expand its **match score breakdown** — a per-marker table showing which markers were found and which were missing.
2. Review the **top scoring groups** section — if an agent scores highly for two groups, that explains an ambiguous verdict.
3. Click **Acknowledge** to mark the anomaly as reviewed. Acknowledged anomalies are filtered from the default view but remain in the data.

Use the match score breakdown to decide whether the fingerprint needs refinement or whether the agent itself is genuinely misconfigured.

---

## Next Steps

- Build fingerprints for additional groups.
- Add new software to the catalog if you encounter entries not present in the seed data — see [Custom Taxonomy](./custom-taxonomy.md).
- For a full explanation of scoring, thresholds, and verdict logic — see [Interpreting Results](./interpreting-results.md).
