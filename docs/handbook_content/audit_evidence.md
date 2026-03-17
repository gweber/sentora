### Exporting Compliance Results

To export violations for auditor review:

1. Go to **Compliance > Violations**
2. Filter by framework and/or severity as needed
3. Click **Export CSV**

The CSV includes: Framework, Control ID, Control Name, Severity, Agent ID, Hostname, Violation Detail, Application, Version, Remediation, Checked At.

### Interpreting the Dashboard for Audit Evidence

The compliance dashboard provides evidence of:
- **Continuous monitoring**: Timestamps showing regular compliance check execution
- **Control coverage**: Number of controls evaluated per framework
- **Compliance posture**: Pass/fail/warning breakdown per framework
- **Violation tracking**: Specific non-compliant endpoints with remediation guidance

**For SOC 2 audits**: The dashboard demonstrates Trust Services Criteria monitoring. Export results before and after remediation to show progress.

**For PCI DSS assessments**: Filter to the PCI DSS framework. CDE-scoped controls demonstrate focused protection of cardholder data environments.

**For HIPAA assessments**: Filter to the HIPAA framework. ePHI-scoped controls show safeguards applied specifically to systems processing electronic Protected Health Information.

**For BSI IT-Grundschutz**: Filter to the BSI framework. Controls are mapped to specific Bausteine and Anforderungen with the requirement level (Basis/Standard/Erhöht) indicated.

**For DORA assessments**: Filter to the DORA framework. Controls map to specific DORA articles covering ICT asset identification, protection, detection, and business continuity.

### What Sentora Reports vs. What the Auditor Still Needs

| Sentora Provides | Auditor Must Verify Independently |
|---|---|
| Software inventory completeness | Network architecture and segmentation |
| Application classification status | Access control policies and procedures |
| EDR agent deployment and version | Incident response plans and testing |
| Prohibited software detection | Employee training and awareness programs |
| Change detection (software) | Physical security controls |
| Patch currency (application versions) | Vendor management and contracts |
| End-of-Life software identification | Risk assessment methodology |
| Data sync freshness | Backup and recovery testing |

### Per-Framework Disclaimer Text

**Include these disclaimers when presenting Sentora compliance data to auditors:**

**SOC 2**: "These checks support evidence collection for SOC 2 audits. They do not constitute SOC 2 certification. Full compliance requires assessment by a licensed CPA firm."

**PCI DSS**: "PCI DSS compliance requires validation by a Qualified Security Assessor (QSA). Sentora provides evidence and monitoring for endpoint-related requirements, not certification."

**HIPAA**: "HIPAA compliance is determined by the U.S. Department of Health and Human Services. Sentora provides technical safeguard monitoring for endpoint software management."

**BSI IT-Grundschutz**: "BSI IT-Grundschutz-Konformitat erfordert eine vollstandige Grundschutz-Prufung durch einen zertifizierten BSI-Auditor. Sentora uberwacht die Endpoint-Software-Management-Anforderungen und liefert Evidenz fur Audits."

**DORA**: "Sentora evaluates DORA compliance exclusively from the perspective of endpoint software inventory, classification, and enforcement. DORA encompasses broader requirements that are outside Sentora's scope. This module does not constitute legal advice."