### Control Shows "not_applicable"

**Cause:** The control has no agents in scope, or it requires configuration.

**Fix:**
1. Check if the control has scope tags/groups that don't match any agents
2. Check if the control needs configuration (e.g. empty `required_apps` or `app_pattern`)
3. Verify that agents exist in the database — run a sync if the fleet is empty

### Control Shows "error"

**Cause:** The check execution failed due to a runtime error.

**Fix:**
1. Check the evidence_summary for the error message
2. Common causes:
   - MongoDB connectivity issues during check execution
   - Corrupt data in agent or app collections
   - Invalid parameter values (e.g. non-numeric threshold)
3. Re-run the compliance check. If the error persists, check the backend logs.

### Score Seems Wrong

**Debug steps:**
1. Go to **Compliance > Dashboard** and note the framework score
2. Click the framework card to see individual control results
3. Verify: Score = Passed / (Total - Not Applicable) x 100
4. Check if disabled controls are correctly excluded
5. Check if `not_applicable` controls are correctly excluded from the denominator
6. If a control shows `pass` but you expect `fail` (or vice versa), click into the control detail to see violations

### Violations Appearing for Wrong Agents

**Cause:** Scope configuration may not match your expectations.

**Fix:**
1. Check the control's scope configuration in **Compliance > Settings**
2. Verify agent tags in SentinelOne match the scope tags configured in Sentora
3. Remember: empty scope = all agents. If you recently removed a scope restriction, the control now checks everything.

### Stale Results (Last Checked Too Long Ago)

**Cause:** Compliance checks haven't run recently.

**Fix:**
1. Check **Compliance > Settings > Schedule** — is the schedule enabled?
2. Check **Sync** view — are syncs completing? Compliance runs after sync by default.
3. Trigger a manual run from **Compliance > Dashboard > Run Checks**

### Performance: Compliance Checks Running Too Slow

Sentora's compliance engine deduplicates identical checks across frameworks. If multiple controls use the same check type with the same parameters and scope, the query runs only once.

**If checks are still slow:**
1. Check your fleet size — 150K+ endpoints will naturally take longer
2. Ensure MongoDB indexes are created (they are applied on startup)
3. Consider disabling frameworks you don't need to reduce the number of active controls
4. Check MongoDB performance metrics for slow queries