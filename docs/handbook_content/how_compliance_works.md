Sentora's compliance module continuously monitors your endpoint fleet against industry frameworks. It checks the software installed on your endpoints — what's there, what's missing, what's outdated, and what's prohibited — and maps findings to specific compliance requirements.

### What Sentora Checks

- **Software inventory**: Which applications are installed on each endpoint
- **Application classification**: Whether each app is Approved, Flagged, Prohibited, or unclassified
- **Agent health**: SentinelOne agent version, online status, and data freshness
- **Change detection**: New or removed software between sync windows
- **End-of-Life**: Software that no longer receives security patches

### What Sentora Does NOT Check

- SentinelOne policy configuration (threat detection settings, firewall rules)
- Network security (firewalls, IDS/IPS, segmentation)
- User access controls (Active Directory, SSO, MFA)
- Physical security controls
- Operational procedures (incident response plans, training records)
- Contractual or legal compliance requirements

### How Checks Run

Compliance checks execute automatically in two ways:
1. **After sync**: When a data sync completes, compliance checks run against the fresh data
2. **Scheduled**: A configurable cron schedule (default: daily at 06:00 UTC)

You can also trigger a manual compliance run from **Compliance > Run Checks**.

### How Scores Are Calculated

Each framework's score is calculated as:

```
Score = (Passed Controls / Applicable Controls) x 100
```

- **Applicable** = all enabled controls minus those returning `not_applicable`
- Controls with status `not_applicable` (unconfigured or no agents in scope) do not affect the score
- Controls with status `error` count as non-passing
- Controls with status `warning` count as non-passing

### Compliance vs. Enforcement

Sentora has two related but distinct modules:

| | Compliance | Enforcement |
|---|---|---|
| **Purpose** | Monitor and report posture | Detect and alert on rule violations |
| **Scope** | Framework-mapped controls | Custom rules (prohibited apps, required apps) |
| **Output** | Compliance scores + audit evidence | Violation alerts + webhook notifications |
| **Audience** | Auditors, compliance officers | MSP technicians, SOC analysts |

Both modules feed into the **Unified Violations** view, giving you a single pane for everything that's broken.