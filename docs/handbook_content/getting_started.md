### Step 1: Enable Your First Framework

1. Go to **Compliance > Settings**
2. Toggle on the framework you need (e.g. SOC 2, PCI DSS)
3. Click **Save**

Start with one framework. You can enable additional frameworks at any time.

### Step 2: Review Controls That Need Configuration

Some controls require tenant-specific configuration before they work. After enabling a framework:

1. Go to **Compliance > Settings > [Framework Name]**
2. Look for controls marked "Configuration Required"
3. Configure each one (e.g. specify which apps are required, which encryption tool to check)

**Common configurations:**
- **Required apps**: Specify which security software must be installed (e.g. "SentinelOne", "BitLocker")
- **App presence checks**: Specify which application to verify (e.g. "Cisco AnyConnect*" for VPN)

Controls left unconfigured will show `not_applicable` and won't affect your compliance score.

### Step 3: Run Your First Compliance Check

1. Go to **Compliance > Dashboard**
2. Click **Run Checks**
3. Wait for results (typically 5-30 seconds depending on fleet size)

### Step 4: Understand the Dashboard

The dashboard shows:
- **Framework cards**: One per enabled framework with its compliance score
- **Score color coding**: Green (>90%), Yellow (70-90%), Red (<70%)
- **Violations feed**: Latest violations across all frameworks, sorted by severity
- **Control status table**: Pass/fail status for every active control

### Step 5: Configure Scope (Optional)

By default, controls check all managed endpoints. To restrict a control to specific endpoints:

1. Go to **Compliance > Settings > [Framework] > [Control]**
2. Set **Scope Tags** (e.g. `PCI-CDE` to check only cardholder data environment endpoints)
3. Set **Scope Groups** (e.g. `Finance Department` to check only that group)
4. Click **Save**

PCI DSS controls come pre-scoped to `PCI-CDE` tags where appropriate.