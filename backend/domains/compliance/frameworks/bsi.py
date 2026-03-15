"""BSI IT-Grundschutz — control definitions.

BSI IT-Grundschutz is the German federal standard for information
security.  It uses „Bausteine" (building blocks) with „Anforderungen"
(requirements) at three levels:
- Basis (MUSS) — mandatory baseline
- Standard (SOLLTE) — recommended standard
- Elevated (SOLLTE bei erhöhtem Schutzbedarf) — for higher protection

This is a DACH-market differentiator — few endpoint management tools
provide BSI IT-Grundschutz mapping.
"""

from __future__ import annotations

from domains.compliance.entities import (
    BsiLevel,
    CheckType,
    ComplianceFramework,
    ControlDefinition,
    ControlSeverity,
    FrameworkId,
)

FRAMEWORK = ComplianceFramework(
    id=FrameworkId.bsi,
    name="BSI IT-Grundschutz",
    version="Edition 2023",
    description=(
        "Bundesamt für Sicherheit in der Informationstechnik — "
        "IT-Grundschutz-Kompendium für systematische Informationssicherheit"
    ),
    disclaimer=(
        "BSI IT-Grundschutz-Konformität erfordert eine vollständige "
        "Grundschutz-Prüfung durch einen zertifizierten BSI-Auditor. "
        "Sentora überwacht die Endpoint-Software-Management-Anforderungen "
        "und liefert Evidenz für Audits."
    ),
)

CONTROLS: list[ControlDefinition] = [
    # ── SYS.2.1 Allgemeiner Client ─────────────────────────────────────
    ControlDefinition(
        id="BSI-SYS.2.1.A3",
        framework_id=FrameworkId.bsi,
        name="Aktivierung von Auto-Update-Mechanismen",
        description=(
            "Software auf Clients SOLLTE auf dem aktuellen Stand gehalten "
            "werden.  Veraltete Versionen stellen ein Sicherheitsrisiko dar."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 15},
        bsi_level=BsiLevel.standard,
        remediation="Veraltete Software aktualisieren oder Auto-Updates aktivieren.",
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A4",
        framework_id=FrameworkId.bsi,
        name="Regelmäßige Datensicherung",
        description=(
            "Backup-Software SOLLTE auf allen Clients installiert sein."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.medium,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        bsi_level=BsiLevel.standard,
        remediation="Backup-Software installieren und konfigurieren.",
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A6",
        framework_id=FrameworkId.bsi,
        name="Einsatz von Virenschutzprogrammen",
        description=(
            "Auf allen Clients MUSS ein Virenschutzprogramm (SentinelOne) "
            "aktiv und aktuell sein."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_version,
        parameters={},
        bsi_level=BsiLevel.basis,
        remediation="SentinelOne Agent aktualisieren und Aktivität sicherstellen.",
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A6-ONLINE",
        framework_id=FrameworkId.bsi,
        name="Virenschutz — Agent-Erreichbarkeit",
        description=(
            "SentinelOne Agent MUSS regelmäßig einchecken.  Offline-Agents "
            "stellen eine Schutzlücke dar."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 3},
        bsi_level=BsiLevel.basis,
        remediation="Offline-Endpoints untersuchen und Konnektivität wiederherstellen.",
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A42",
        framework_id=FrameworkId.bsi,
        name="Nutzung von Allowlists",
        description=(
            "Nur genehmigte (Approved) Software SOLLTE auf Clients installiert "
            "sein.  Nicht-genehmigte Software SOLLTE entfernt werden."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.prohibited_app,
        parameters={},
        bsi_level=BsiLevel.elevated,
        remediation="Nicht-genehmigte Software von Endpoints entfernen.",
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A42-UNCL",
        framework_id=FrameworkId.bsi,
        name="Allowlists — Unklassifizierte Apps",
        description=(
            "Der Anteil unklassifizierter Anwendungen SOLLTE unter dem "
            "konfigurierten Schwellenwert liegen."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        bsi_level=BsiLevel.elevated,
        remediation="Unbekannte Anwendungen klassifizieren und bewerten.",
    ),
    # ── APP.6 Allgemeine Software ──────────────────────────────────────
    ControlDefinition(
        id="BSI-APP.6.A1",
        framework_id=FrameworkId.bsi,
        name="Planung des Software-Einsatzes",
        description=(
            "Ein vollständiges Software-Inventar MUSS vorhanden sein.  "
            "Die Abdeckung der Klassifizierung MUSS gemessen werden."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 85},
        bsi_level=BsiLevel.basis,
        remediation="Software-Inventar vervollständigen und Klassifizierung durchführen.",
    ),
    ControlDefinition(
        id="BSI-APP.6.A1-SYNC",
        framework_id=FrameworkId.bsi,
        name="Software-Inventar — Aktualität",
        description=(
            "Das Software-Inventar MUSS regelmäßig aktualisiert werden."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        bsi_level=BsiLevel.basis,
        remediation="Daten-Sync konfigurieren und regelmäßig ausführen.",
    ),
    ControlDefinition(
        id="BSI-APP.6.A2",
        framework_id=FrameworkId.bsi,
        name="Erstellung eines Anforderungskatalogs",
        description=(
            "Pflicht-Software (Required Apps) SOLLTE definiert und auf "
            "allen Clients installiert sein."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.medium,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        bsi_level=BsiLevel.standard,
        remediation="Pflicht-Software definieren und auf allen Endpoints installieren.",
    ),
    ControlDefinition(
        id="BSI-APP.6.A4",
        framework_id=FrameworkId.bsi,
        name="Sicherstellung der Integrität von Software",
        description=(
            "Unautorisierte Software-Änderungen MÜSSEN erkannt werden.  "
            "Delta-Detection zwischen Syncs identifiziert Änderungen."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        bsi_level=BsiLevel.basis,
        remediation="Software-Änderungen prüfen und autorisieren.",
    ),
    ControlDefinition(
        id="BSI-APP.6.A5",
        framework_id=FrameworkId.bsi,
        name="Deinstallation nicht benötigter Software",
        description=(
            "Software die weder Approved noch Required ist SOLLTE von "
            "Endpoints entfernt werden."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        bsi_level=BsiLevel.standard,
        remediation="Nicht-benötigte Software identifizieren und deinstallieren.",
    ),
    # ── OPS.1.1.3 Patch- und Änderungsmanagement ──────────────────────
    ControlDefinition(
        id="BSI-OPS.1.1.3.A1",
        framework_id=FrameworkId.bsi,
        name="Konzept für Patch- und Änderungsmanagement",
        description=(
            "Updates MÜSSEN zeitnah installiert werden.  Veraltete "
            "Software-Versionen MÜSSEN erkannt werden."
        ),
        category="OPS.1.1.3 — Patch-Management",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        bsi_level=BsiLevel.basis,
        remediation="Veraltete Software-Versionen identifizieren und aktualisieren.",
    ),
    ControlDefinition(
        id="BSI-OPS.1.1.3.A15",
        framework_id=FrameworkId.bsi,
        name="Regelmäßige Aktualisierung der IT",
        description=(
            "Die Altersstruktur der installierten Software SOLLTE regelmäßig "
            "analysiert werden.  EOL-Software MUSS identifiziert werden."
        ),
        category="OPS.1.1.3 — Patch-Management",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 5},
        bsi_level=BsiLevel.standard,
        remediation="EOL-Software ersetzen und regelmäßige Aktualisierungen sicherstellen.",
    ),
    ControlDefinition(
        id="BSI-OPS.1.1.3.A15-EDR",
        framework_id=FrameworkId.bsi,
        name="EDR-Agent Aktualisierung",
        description=(
            "Der SentinelOne Agent MUSS auf allen Endpoints auf dem "
            "aktuellen Stand sein."
        ),
        category="OPS.1.1.3 — Patch-Management",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_version,
        parameters={},
        bsi_level=BsiLevel.basis,
        remediation="SentinelOne Agent auf aktuelle Version aktualisieren.",
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A9",
        framework_id=FrameworkId.bsi,
        name="Festlegung einer Sicherheitsrichtlinie für Clients",
        description=(
            "Die Einhaltung der Sicherheitsrichtlinie für installierte "
            "Software MUSS überprüft werden.  Prohibited Software MUSS "
            "erkannt und entfernt werden."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.prohibited_app,
        parameters={},
        bsi_level=BsiLevel.basis,
        remediation="Prohibited Software entfernen und Richtlinie durchsetzen.",
    ),
]
