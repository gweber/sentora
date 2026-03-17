### Configuring Scope Per Control

Every control can be scoped to a subset of your endpoint fleet using SentinelOne tags and groups.

1. Go to **Compliance > Settings > [Framework] > [Control ID]**
2. **Scope Tags**: Enter one or more SentinelOne tags. Only agents with at least one matching tag are checked.
3. **Scope Groups**: Enter one or more SentinelOne group names. Only agents in these groups are checked.
4. If both tags and groups are specified, an agent must match at least one tag AND be in one of the specified groups.
5. Leave both empty to check all managed endpoints.

### Adjusting Thresholds

Many controls use configurable thresholds. To adjust:

1. Go to **Compliance > Settings > [Framework] > [Control ID]**
2. Modify the threshold parameter (e.g. `max_offline_days`, `min_classified_percent`)
3. Click **Save**
4. Run a compliance check to see the updated results

**Examples:**
- Lower `max_unclassified_percent` from 10% to 5% for stricter classification requirements
- Increase `max_offline_days` from 7 to 14 if your organization has endpoints that go offline for extended periods (e.g. field laptops)
- Set `min_version` explicitly instead of using auto-detected fleet baseline

### Enabling/Disabling Individual Controls

1. Go to **Compliance > Settings > [Framework]**
2. Toggle the control on or off
3. Disabled controls do not run, do not appear in results, and do not affect the framework score

### Creating Custom Controls

You can create additional controls that use the same check types as built-in controls:

1. Go to **Compliance > Settings > Custom Controls**
2. Click **Create Custom Control**
3. Fill in:
   - **ID**: Must start with `custom-` (e.g. `custom-vpn-check`)
   - **Framework**: Which framework this control belongs to
   - **Check Type**: Which check to run
   - **Parameters**: Configure the check parameters
   - **Scope**: Optional tags and groups
4. Click **Create**

### Schedule Configuration

1. Go to **Compliance > Settings > Schedule**
2. Configure:
   - **Run after sync**: Automatically run compliance checks after each data sync (default: on)
   - **Cron expression**: Optional additional schedule (e.g. `0 6 * * *` for daily at 06:00 UTC)
   - **Enabled**: Master toggle for the schedule