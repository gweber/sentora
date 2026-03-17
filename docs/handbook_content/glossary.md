| Term | Definition |
|---|---|
| **Agent** | A SentinelOne agent installed on a managed endpoint. Sentora syncs agent data from the SentinelOne management console. |
| **Approved** | An application classification indicating the software is authorized for use on managed endpoints. |
| **BSI IT-Grundschutz** | The German federal standard for information security published by the Bundesamt fur Sicherheit in der Informationstechnik (BSI). |
| **CDE** | Cardholder Data Environment — systems that store, process, or transmit cardholder data (PCI DSS term). |
| **Check Type** | The implementation that evaluates a compliance control. Each check type queries specific data and produces a pass/fail/warning result. |
| **Classification** | The process of categorizing installed applications as Approved, Flagged, Prohibited, or leaving them unclassified. |
| **Compliance Score** | Percentage of passing controls out of all applicable controls for a framework. Formula: Passed / (Total - Not Applicable) x 100. |
| **Control** | A specific compliance requirement mapped to an automated check. Each control belongs to one framework. |
| **DORA** | Digital Operational Resilience Act — EU regulation (2022/2554) for digital resilience of financial entities. |
| **Endpoint** | A managed device (workstation, laptop, server) with a SentinelOne agent installed. |
| **End-of-Life (EOL)** | Software that no longer receives security patches or updates from the vendor. |
| **ePHI** | Electronic Protected Health Information — health data in electronic form protected under HIPAA. |
| **Enforcement** | Sentora's rule-based violation detection module. Distinct from compliance but feeds into the unified violations view. |
| **Fleet** | The entire set of managed endpoints visible to Sentora through SentinelOne. |
| **Fleet Baseline** | The most common version of an application or agent across the fleet, used as the comparison standard. |
| **Flagged** | An application classification indicating the software is under review or warrants attention. |
| **Framework** | A compliance standard (SOC 2, PCI DSS, HIPAA, BSI IT-Grundschutz, DORA) with its set of controls. |
| **HIPAA** | Health Insurance Portability and Accountability Act — U.S. federal law protecting electronic health information. |
| **not_applicable** | A check result status indicating the control cannot be evaluated (no agents in scope, or unconfigured). Does not affect the compliance score. |
| **PCI DSS** | Payment Card Industry Data Security Standard — requirements for protecting cardholder data. |
| **Prohibited** | An application classification indicating the software must not be installed on managed endpoints. |
| **Scope** | The subset of endpoints a control checks, defined by SentinelOne tags and/or groups. |
| **SOC 2** | Service Organization Control 2 — AICPA framework for security, availability, processing integrity, confidentiality, and privacy. |
| **Sync** | The data synchronization process that pulls agent and application data from SentinelOne into Sentora. |
| **Taxonomy** | Sentora's application classification system for categorizing software. |
| **Violation** | A specific finding where an endpoint does not meet a control's requirements. |