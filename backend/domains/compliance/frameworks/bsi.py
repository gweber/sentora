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
            "SYS.2.1.A3 fordert automatische Updates auf Clients. Diese "
            "Kontrolle prüft, ob der Anteil veralteter Anwendungen unter "
            "15% liegt, indem installierte Versionen mit der "
            "Library-Baseline verglichen werden."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 15},
        bsi_level=BsiLevel.standard,
        remediation=(
            "Veraltete Anwendungen auf aktuelle Versionen aktualisieren. "
            "In der Library-Ansicht können installierte Versionen mit der "
            "Baseline verglichen werden. Auto-Update-Mechanismen aktivieren."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A4",
        framework_id=FrameworkId.bsi,
        name="Regelmäßige Datensicherung",
        description=(
            "SYS.2.1.A4 fordert regelmäßige Datensicherung. Diese "
            "Kontrolle prüft, ob die konfigurierte Backup-Software auf "
            "allen Clients installiert ist. Erfordert mandantenspezifische "
            "Konfiguration der Backup-Software."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.medium,
        check_type=CheckType.custom_app_presence,
        parameters={"app_pattern": "", "must_exist": True},
        bsi_level=BsiLevel.standard,
        remediation=(
            "Konfigurieren Sie den Namen der Backup-Software unter "
            "Compliance > Einstellungen > BSI > BSI-SYS.2.1.A4. Geben "
            "Sie das app_pattern an (z.B. 'Veeam*', 'Acronis*'). Bis "
            "zur Konfiguration zeigt diese Kontrolle 'not_applicable'."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A6",
        framework_id=FrameworkId.bsi,
        name="Einsatz von Virenschutzprogrammen",
        description=(
            "SYS.2.1.A6 fordert aktiven Virenschutz auf allen Clients. "
            "Diese Kontrolle prüft, ob der SentinelOne Agent als "
            "Virenschutzlösung auf der aktuellen Fleet-Baseline-Version "
            "läuft und damit vollständigen Echtzeitschutz bietet."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_version,
        parameters={},
        bsi_level=BsiLevel.basis,
        remediation=(
            "SentinelOne Agent auf die aktuelle Fleet-Baseline-Version "
            "aktualisieren. Verwenden Sie die SentinelOne-Konsole, um "
            "Agent-Upgrades für nicht-konforme Endpoints zu planen."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A6-ONLINE",
        framework_id=FrameworkId.bsi,
        name="Virenschutz — Agent-Erreichbarkeit",
        description=(
            "SYS.2.1.A6 fordert lückenlosen Virenschutz. Diese Kontrolle "
            "prüft, ob alle SentinelOne Agents innerhalb von 3 Tagen "
            "eingecheckt haben — Offline-Agents können nicht überwacht "
            "oder geschützt werden."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_online,
        parameters={"max_offline_days": 3},
        bsi_level=BsiLevel.basis,
        remediation=(
            "Offline-Endpoints sofort untersuchen. Netzwerkkonnektivität "
            "prüfen, SentinelOne-Agent-Dienst verifizieren und "
            "Kommunikation mit der Management-Konsole wiederherstellen."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A42",
        framework_id=FrameworkId.bsi,
        name="Nutzung von Allowlists",
        description=(
            "SYS.2.1.A42 fordert den Einsatz von Allowlists bei erhöhtem "
            "Schutzbedarf. Diese Kontrolle erkennt Software, die als "
            "Prohibited klassifiziert ist, und stellt sicher, dass nur "
            "explizit genehmigte Anwendungen installiert sind."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.prohibited_app,
        parameters={},
        bsi_level=BsiLevel.elevated,
        remediation=(
            "Alle als Prohibited klassifizierten Anwendungen von "
            "betroffenen Endpoints entfernen. In der Taxonomie prüfen, "
            "ob die Allowlist vollständig und aktuell ist. Untersuchen, "
            "wie nicht-genehmigte Software installiert wurde."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A42-UNCL",
        framework_id=FrameworkId.bsi,
        name="Allowlists — Unklassifizierte Apps",
        description=(
            "SYS.2.1.A42 ergänzend: Für funktionierende Allowlists muss "
            "die Klassifizierung nahezu vollständig sein. Diese Kontrolle "
            "prüft, ob der Anteil unklassifizierter Anwendungen unter 10% "
            "liegt."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 10},
        bsi_level=BsiLevel.elevated,
        remediation=(
            "Unklassifizierte Anwendungen auf betroffenen Endpoints "
            "überprüfen. Im Taxonomie-Editor unbekannte Software "
            "klassifizieren oder Fingerprints für wiederkehrende "
            "Anwendungen erstellen."
        ),
    ),
    # ── APP.6 Allgemeine Software ──────────────────────────────────────
    ControlDefinition(
        id="BSI-APP.6.A1",
        framework_id=FrameworkId.bsi,
        name="Planung des Software-Einsatzes",
        description=(
            "APP.6.A1 fordert eine Planung des Software-Einsatzes. Diese "
            "Kontrolle prüft, ob mindestens 85% der Anwendungen auf allen "
            "Endpoints klassifiziert sind, um ein vollständiges "
            "Software-Inventar sicherzustellen."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.high,
        check_type=CheckType.classification_coverage,
        parameters={"min_classified_percent": 85},
        bsi_level=BsiLevel.basis,
        remediation=(
            "Klassifizierungs-Engine auf allen unbearbeiteten Endpoints "
            "ausführen. In der Agents-Ansicht nach 'unclassified' filtern, "
            "um Endpoints mit geringer Klassifizierungsabdeckung zu finden."
        ),
    ),
    ControlDefinition(
        id="BSI-APP.6.A1-SYNC",
        framework_id=FrameworkId.bsi,
        name="Software-Inventar — Aktualität",
        description=(
            "APP.6.A1 fordert ein aktuelles Software-Inventar. Diese "
            "Kontrolle prüft, ob der letzte Daten-Sync innerhalb von "
            "24 Stunden abgeschlossen wurde, damit das Inventar den "
            "aktuellen Zustand der Endpoints widerspiegelt."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.high,
        check_type=CheckType.sync_freshness,
        parameters={"max_hours_since_sync": 24},
        bsi_level=BsiLevel.basis,
        remediation=(
            "In der Sync-Ansicht nach Fehlern oder blockierten Sync-Läufen "
            "prüfen. Sicherstellen, dass Sync-Zeitpläne aktiv sind und "
            "die SentinelOne-API-Verbindung funktioniert."
        ),
    ),
    ControlDefinition(
        id="BSI-APP.6.A2",
        framework_id=FrameworkId.bsi,
        name="Erstellung eines Anforderungskatalogs",
        description=(
            "APP.6.A2 fordert einen Anforderungskatalog für Software. "
            "Diese Kontrolle prüft, ob die konfigurierten Pflicht-"
            "Anwendungen auf allen Clients installiert sind. Erfordert "
            "mandantenspezifische Konfiguration."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.medium,
        check_type=CheckType.required_app,
        parameters={"required_apps": []},
        bsi_level=BsiLevel.standard,
        remediation=(
            "Definieren Sie die Pflicht-Software unter Compliance > "
            "Einstellungen > BSI > BSI-APP.6.A2. Geben Sie die "
            "Anwendungsnamen an, die auf allen Clients vorhanden sein "
            "müssen."
        ),
    ),
    ControlDefinition(
        id="BSI-APP.6.A4",
        framework_id=FrameworkId.bsi,
        name="Sicherstellung der Integrität von Software",
        description=(
            "APP.6.A4 fordert die Sicherstellung der Software-Integrität. "
            "Diese Kontrolle erkennt Software-Installationen und "
            "-Deinstallationen innerhalb der letzten 24 Stunden durch "
            "Vergleich aufeinanderfolgender Sync-Ergebnisse."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.high,
        check_type=CheckType.delta_detection,
        parameters={"lookback_hours": 24},
        bsi_level=BsiLevel.basis,
        remediation=(
            "Erkannte Software-Änderungen in der Anomalien-Ansicht prüfen. "
            "Sicherstellen, dass alle Änderungen über den "
            "Änderungsmanagement-Prozess autorisiert wurden."
        ),
    ),
    ControlDefinition(
        id="BSI-APP.6.A5",
        framework_id=FrameworkId.bsi,
        name="Deinstallation nicht benötigter Software",
        description=(
            "APP.6.A5 fordert die Deinstallation nicht benötigter Software. "
            "Diese Kontrolle prüft, ob der Anteil unklassifizierter "
            "Anwendungen unter 5% liegt — unklassifizierte Software gilt "
            "als potenziell nicht benötigt."
        ),
        category="APP.6 — Allgemeine Software",
        severity=ControlSeverity.medium,
        check_type=CheckType.unclassified_threshold,
        parameters={"max_unclassified_percent": 5},
        bsi_level=BsiLevel.standard,
        remediation=(
            "Unklassifizierte Anwendungen auf betroffenen Endpoints "
            "prüfen. Im Taxonomie-Editor klassifizieren oder "
            "nicht-benötigte Software deinstallieren."
        ),
    ),
    # ── OPS.1.1.3 Patch- und Änderungsmanagement ──────────────────────
    ControlDefinition(
        id="BSI-OPS.1.1.3.A1",
        framework_id=FrameworkId.bsi,
        name="Konzept für Patch- und Änderungsmanagement",
        description=(
            "OPS.1.1.3.A1 fordert ein Konzept für Patch-Management. Diese "
            "Kontrolle prüft, ob der Anteil veralteter Anwendungen unter "
            "10% liegt, indem installierte Versionen gegen die "
            "Library-Baseline verglichen werden."
        ),
        category="OPS.1.1.3 — Patch-Management",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 10},
        bsi_level=BsiLevel.basis,
        remediation=(
            "Veraltete Anwendungen auf aktuelle Versionen aktualisieren. "
            "In der Library-Ansicht installierte Versionen mit der "
            "Baseline vergleichen und Updates priorisieren."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1-EOL",
        framework_id=FrameworkId.bsi,
        name="End-of-Life Software Identification",
        description=(
            "EOL-Software erhält keine Sicherheitsupdates und MUSS "
            "identifiziert werden. Diese Kontrolle nutzt endoflife.date "
            "Lebenszyklusdaten, um End-of-Life Software auf Endpoints "
            "zu erkennen."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.eol_software,
        parameters={"flag_security_only": True, "min_match_confidence": 0.8},
        bsi_level=BsiLevel.basis,
        remediation=(
            "EOL-Software durch unterstützte Versionen ersetzen. "
            "Informationen zu unterstützten Versionen unter endoflife.date."
        ),
    ),
    ControlDefinition(
        id="BSI-OPS.1.1.3.A15",
        framework_id=FrameworkId.bsi,
        name="Regelmäßige Aktualisierung der IT",
        description=(
            "OPS.1.1.3.A15 fordert regelmäßige Aktualisierung der IT. "
            "Diese Kontrolle prüft mit einem strengeren Schwellenwert von "
            "5%, ob installierte Software-Versionen aktuell sind, und "
            "unterstützt die Analyse der Software-Altersstruktur."
        ),
        category="OPS.1.1.3 — Patch-Management",
        severity=ControlSeverity.high,
        check_type=CheckType.app_version,
        parameters={"max_outdated_percent": 5},
        bsi_level=BsiLevel.standard,
        remediation=(
            "Veraltete und EOL-Software durch unterstützte Versionen "
            "ersetzen. In der Library-Ansicht die Altersstruktur der "
            "installierten Software analysieren."
        ),
    ),
    ControlDefinition(
        id="BSI-OPS.1.1.3.A15-EDR",
        framework_id=FrameworkId.bsi,
        name="EDR-Agent Aktualisierung",
        description=(
            "OPS.1.1.3.A15 fordert aktuelle EDR-Agents im Rahmen des "
            "Patch-Managements. Diese Kontrolle prüft, ob der SentinelOne "
            "Agent auf allen Endpoints die aktuelle Fleet-Baseline-Version "
            "hat, damit Bedrohungserkennung auf dem neuesten Stand ist."
        ),
        category="OPS.1.1.3 — Patch-Management",
        severity=ControlSeverity.critical,
        check_type=CheckType.agent_version,
        parameters={},
        bsi_level=BsiLevel.basis,
        remediation=(
            "SentinelOne Agent auf die aktuelle Fleet-Baseline-Version "
            "aktualisieren. Verwenden Sie die SentinelOne-Konsole, um "
            "Agent-Upgrades für nicht-konforme Endpoints zu planen."
        ),
    ),
    ControlDefinition(
        id="BSI-SYS.2.1.A9",
        framework_id=FrameworkId.bsi,
        name="Festlegung einer Sicherheitsrichtlinie für Clients",
        description=(
            "SYS.2.1.A9 fordert die Durchsetzung der Sicherheitsrichtlinie "
            "für Clients. Diese Kontrolle erkennt Software, die als "
            "Prohibited klassifiziert ist, und erzwingt damit die "
            "Einhaltung der organisationsweiten Software-Richtlinie."
        ),
        category="SYS.2.1 — Allgemeiner Client",
        severity=ControlSeverity.high,
        check_type=CheckType.prohibited_app,
        parameters={},
        bsi_level=BsiLevel.basis,
        remediation=(
            "Alle als Prohibited klassifizierten Anwendungen von "
            "betroffenen Endpoints entfernen. Untersuchen, wie die "
            "Software installiert wurde, und Sicherheitsrichtlinie "
            "durchsetzen."
        ),
    ),
]
