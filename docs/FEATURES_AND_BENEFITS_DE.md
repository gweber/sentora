# Sentora — Feature- & Nutzen-Übersicht

## Elevator Pitch

Sentora ist die Multi-EDR Endpoint-Compliance-Plattform, die rohe Agent- und Applikationsdaten aus EDR-Plattformen (SentinelOne, CrowdStrike, Defender) in verwertbare Compliance-Intelligence transformiert — mit SOC 2, PCI DSS 4.0, HIPAA, BSI IT-Grundschutz, DORA, ISO 27001, NIST CSF 2.0, NIS2 und CIS Controls v8 ab Werk. Statt manueller Spreadsheet-Exporte und Control-Mappings erhalten Security-Teams Echtzeit-Compliance-Scores, automatisierte Violation-Erkennung und audit-fertige Nachweise — über Flotten von 1.000 bis 150.000+ Endpoints.

---

## Kern-Plattform

### 5-Phasen-Sync-Pipeline

**Was es macht:**
Eine produktionserprobte Ingestion-Engine, die Ihren gesamten EDR-Tenant synchronisiert — Sites, Groups, Agents, installierte Applikationen und Tags — über fünf unabhängige, parallelisierbare Phasen mit Checkpoint-basiertem Resume.

**Kundennutzen:**

- Verarbeitet 100.000+ Agents ohne manuelle Datenexporte oder CSV-Jonglage
- Cursor-basierte Pagination mit Checkpoint-Persistenz: Wenn ein Sync mittendrin fehlschlägt, setzt er am letzten Checkpoint fort — kein erneutes Synchronisieren der gesamten Flotte
- Echtzeit-WebSocket-Fortschrittsanzeige: Ihr Team sieht den Sync-Status live im Dashboard, nicht in einer Hintergrund-E-Mail 30 Minuten später
- Konfigurierbares Scheduling (inklusive wöchentlichem Full Sync) stellt sicher, dass Daten stets aktuell sind — ohne manuelles Eingreifen

### Multi-Tenant-Architektur

**Was es macht:**
Database-per-Tenant-Isolation mit Distributed Locking und Leader Election für Multi-Worker-Deployments. Jeder Tenant erhält eine vollständig separate MongoDB-Datenbank.

**Kundennutzen:**

- **Datenisolation garantiert**: Tenant A sieht niemals Daten von Tenant B — nicht über einen Row-Level-Filter, sondern über physisch getrennte Datenbanken
- **MSSPs und Holding-Strukturen** können mehrere EDR-Tenants über eine einzige Sentora-Instanz verwalten
- Distributed Locks stellen sicher, dass parallele Worker niemals doppelte Syncs oder widersprüchliche Compliance-Evaluierungen erzeugen
- Horizontal skalierbar durch Hinzufügen von Workern; Leader Election übernimmt die Koordination automatisch

### Authentifizierung & Zugriffskontrolle

**Was es macht:**
Vollständiger Enterprise-Auth-Stack: JWT mit 15-Minuten-Access-Tokens und 7-Tage-Refresh-Tokens (Family-Tracking zur Diebstahlerkennung), OIDC (Okta, Azure AD, Keycloak), SAML, TOTP-basierte 2FA und API-Key-Authentifizierung mit granularen Scopes.

**Kundennutzen:**

- **SSO-Integration**: Benutzer authentifizieren sich über Ihren bestehenden Identity Provider — kein separates Passwort zu verwalten
- **TOTP 2FA**: Fügt einen zweiten Faktor für lokale Accounts hinzu, mit QR-Code-Provisioning und 6-stelliger Verifizierung
- **4 RBAC-Rollen** (Super Admin, Admin, Analyst, Viewer) ermöglichen Least-Privilege-Zugriff über Ihr gesamtes Compliance-Team
- **API Keys mit Scopes**: Automatisieren Sie Workflows (CI/CD, SIEM-Integration) ohne Benutzer-Credentials offenzulegen
- Passwortsicherheit umfasst bcrypt-Hashing, Breach-Checking via HaveIBeenPwned (k-Anonymity), Passwort-Historien-Prüfung und Account-Lockout
- Serverseitige Session-Verwaltung mit sofortiger Revocation — ein deaktivierter Benutzer verliert den Zugang sofort, nicht erst beim Token-Ablauf

---

## Software Intelligence

### Fingerprint Engine (TF-IDF + Lift Scoring)

**Was es macht:**
Eine statistische Engine, die analysiert, welche Applikationen für jede EDR-Gruppe charakteristisch sind. Sie nutzt TF-IDF-basiertes Matching und Lift Scoring (wie viel wahrscheinlicher eine App in einer Gruppe vorkommt vs. dem Flotten-Durchschnitt), um Fingerprint-Vorschläge automatisch zu generieren.

**Kundennutzen:**

- **Automatische Erkennung**: Statt manuell zu definieren „Gruppe X sollte App Y haben", schlägt die Engine diskriminative Marker vor — z.B. „Agents in der Finance-Gruppe haben Bloomberg Terminal 12× häufiger als der Flottendurchschnitt"
- **Konfigurierbare Schwellwerte**: Coverage-Minimum (≥60%), Outside-Maximum (<25%), Lift-Minimum (≥2.0×), Top-K-Vorschläge (10 pro Gruppe) — anpassbar an die Charakteristiken Ihrer Flotte
- **Glob-Pattern-Matching**: Marker nutzen Wildcards (`*`, `?`) für flexibles App-Name-Matching, mit gewichteter Bewertung (0,1–2,0 pro Marker)
- **Vorschlags-Workflow**: Maschinell generierte Vorschläge durchlaufen einen Pending → Applied/Dismissed-Workflow — der Mensch bleibt in der Entscheidung
- Ergebnis: Von „wir haben 50.000 Apps auf 10.000 Agents" zu „hier sind die 10 charakteristischsten Apps pro Gruppe" — in Minuten, nicht Wochen

### Classification Engine

**Was es macht:**
Klassifiziert jede installierte Applikation auf jedem Endpoint mittels Fingerprint-Matches, Library-Lookups und Anomalie-Erkennung. Liefert Verdicts (Matched, Partial, Unmatched) mit Confidence-Scores.

**Kundennutzen:**

- **Sichtbarkeit auf Shadow IT**: Nicht klassifizierte oder anomale Applikationen werden automatisch sichtbar — Sie sehen, was nicht dazugehört
- **Anomalie-Erkennung**: Flaggt Applikationen, die dort auftauchen, wo sie statistisch nicht hingehören, basierend auf Gruppen-Profilen
- **Confidence Scoring**: Match-Scores (≥0,7 = Matched, 0,4–0,7 = Partial, <0,4 = Unmatched) ermöglichen die Priorisierung des Review-Aufwands auf Grenzfälle
- Klassifikationsergebnisse sind die Grundlage für Compliance-Checks und Enforcement-Regeln — ein Klassifikationslauf speist beide Module

### Library-System

**Was es macht:**
Ingestiert Software-Definitionen aus fünf autoritativen Quellen: NIST CPE (NVD), MITRE ATT&CK, Chocolatey, Homebrew Core und Homebrew Cask. Jede Quelle liefert normalisierte App-Namen, Glob-Patterns und Versions-Metadaten.

**Kundennutzen:**

- **NIST CPE**: Ordnen Sie installierte Software offiziellen CPE-Identifiern zu — dieselben Identifier, die in Schwachstellen-Datenbanken (NVD/CVE) verwendet werden
- **MITRE ATT&CK**: Erkennen Sie bekannte Threat-Actor-Tools und Malware auf Endpoints anhand des MITRE-Software-Katalogs
- **Chocolatey + Homebrew**: Gleichen Sie Applikationen gegen die zwei größten plattformspezifischen Package-Registries ab (Windows und macOS)
- **Keine manuelle Datenpflege**: Library-Einträge werden mit Checkpoint-Recovery und automatischer Normalisierung ingestiert — Ihr Team pflegt kein Spreadsheet mit „bekannt guter" Software
- Library-Matches fließen direkt in Klassifikation und Compliance-Checks ein und schließen den Kreislauf zwischen „was ist installiert" und „was ist erlaubt"

---

## Compliance-Modul

### 9 Frameworks, 142 Controls, 11 Check-Typen

**Was es macht:**
Automatisierte Compliance-Bewertung gegen neun Industrie-Frameworks, mit 142 vorkonfigurierten Controls und 11 unterschiedlichen Check-Typen — alle gegen Live-EDR-Daten evaluiert.

| Framework           | Controls | Fokus                                                     |
| ------------------- | -------- | --------------------------------------------------------- |
| SOC 2 Type II       | 16       | Security, Availability, Integrity, Confidentiality        |
| PCI DSS 4.0.1       | 16       | Malware-Schutz, Patch Management, sichere Software        |
| HIPAA Security Rule | 16       | Required & Addressable Safeguards                         |
| BSI IT-Grundschutz  | 16       | Deutscher/DACH-Regulierungsstandard (3 Anforderungsstufen) |
| DORA                | 20       | Digitale operationale Resilienz für EU-Finanzunternehmen  |
| ISO/IEC 27001       | 16       | Internationaler ISMS-Standard — Annex A technologische Controls |
| NIST CSF 2.0        | 15       | US-Cybersecurity-Standard — Identify, Protect, Detect     |
| NIS2                | 13       | EU-Cybersecurity-Richtlinie 2022/2555 — Artikel 21        |
| CIS Controls v8     | 14       | Priorisierte Security Controls mit Implementation Groups  |

**10 Check-Typen:**

| Check-Typ                 | Was geprüft wird                                                        |
| ------------------------- | ----------------------------------------------------------------------- |
| `prohibited_app`          | Verbotene Software auf Endpoints vorhanden                              |
| `required_app`            | Pflicht-Software fehlt auf Endpoints                                    |
| `agent_version`           | EDR-Agent unter Mindestversion                                         |
| `agent_online`            | Agents nicht erreichbar oder offline                                    |
| `app_version`             | Bestimmte Applikation unter erforderlicher Version                      |
| `sync_freshness`          | Daten älter als akzeptabler Schwellwert                                 |
| `classification_coverage` | Prozentsatz klassifizierter vs. gesamter Applikationen                  |
| `unclassified_threshold`  | Zu viele unbekannte Applikationen auf einem Endpoint                    |
| `delta_detection`         | Unautorisierte Software-Änderungen seit letzter Baseline               |
| `custom_app_presence`     | Individuelle App-Anforderungen (z.B. Backup-Agent installiert)          |

**Kundennutzen:**

- **Audit-Vorbereitung in Stunden statt Wochen**: Führen Sie alle Checks über Ihre Flotte aus, erhalten Sie einen Framework-Level-Compliance-Score und drillen Sie auf einzelne Control-Violations herunter
- **Kontinuierliche Compliance**: Checks laufen automatisch nach jedem Sync — Sie erfahren nicht erst am Tag vor dem Audit, dass Sie non-compliant sind
- **Evidence-ready**: Jede Violation enthält den Agent-Hostnamen, den fehlgeschlagenen Check, das Violation-Detail und einen Remediation-Hinweis
- **Custom Controls**: Erweitern Sie Built-in-Frameworks um Tenant-spezifische Control-Definitionen
- **Scoping**: Wenden Sie Controls gezielt auf bestimmte EDR-Gruppen und/oder Tags an — nicht jedes Control gilt für jeden Endpoint

### Framework-Dashboard & Score Cards

**Was es macht:**
Ein Per-Framework-Dashboard mit dem Gesamt-Compliance-Score (% der bestehenden Controls), individuellem Control-Status (Pass/Fail/Warning/Error) und einem Unified-Violations-Feed mit Filterung und CSV-Export.

**Kundennutzen:**

- **Executive Reporting**: Eine Zahl pro Framework — „Wir sind zu 87% SOC-2-konform" — mit Drill-Down für das Audit-Team
- **Control-Level-Detail**: Jedes Control zeigt seinen aktuellen Status, Severity, letzten Check-Zeitpunkt und alle zugehörigen Violations
- **Unified Violations View**: Compliance- und Enforcement-Violations in einem einzigen, filterbaren Feed — kein Wechseln zwischen Modulen für das Gesamtbild
- **Trend-Sichtbarkeit**: Verfolgen Sie die Compliance-Posture über die Zeit, nicht nur bei Audit-Snapshots
- **CSV-Export**: Laden Sie Violations für externes Reporting oder SIEM-Ingestion herunter

### CQRS-Backend-Architektur

**Was es macht:**
Command-Query Responsibility Separation: Compliance-Check-Ausführung (Commands) und Ergebnis-Reads (Queries) sind in separate Code-Pfade getrennt. Klassifikationsergebnisse werden als Disposable Projections behandelt, deterministisch bei Bedarf neu berechnet.

**Kundennutzen:**

- **Performance**: Read-lastige Dashboard-Queries konkurrieren nicht mit Write-lastiger Check-Ausführung
- **Konsistenz**: Ergebnisse werden immer aus aktuellen Daten abgeleitet — kein staler Cache, kein Event-Replay-Drift
- **Einfachheit**: Kein Event-Sourcing-Overhead; das System ist deterministisch und vollständig testbar

---

## Enforcement-Modul

### 3 Regel-Typen mit Taxonomie-basiertem Matching

**Was es macht:**
Policy-Enforcement über drei Regel-Typen — **Required** (Software muss installiert sein), **Forbidden** (Software darf nicht installiert sein) und **Allowlist** (nur freigegebene Software erlaubt) — unter Nutzung des Taxonomie-basierten Pattern-Matchings der Fingerprint Engine.

**Kundennutzen:**

- **Forbidden-Regeln**: „Keine Cryptocurrency-Miner auf irgendeinem Endpoint" — automatisch nach jedem Sync evaluiert, Violations sofort sichtbar
- **Required-Regeln**: „Jeder Endpoint im PCI-Scope muss den DLP-Agent installiert haben" — fehlende Software pro Agent geflaggt
- **Allowlist-Regeln**: „Nur freigegebene Software in der Secure-Enclave-Gruppe" — alles, was nicht auf der Liste steht, ist eine Violation
- **Taxonomie-Integration**: Regeln referenzieren Taxonomie-Kategorien, nicht rohe App-Namen — wenn eine neue Version einer verbotenen App mit leicht anderem Namen erscheint, greift das Pattern trotzdem
- **Scoping**: Regeln können auf bestimmte EDR-Gruppen und/oder Tags zielen — wenden Sie unterschiedliche Policies auf verschiedene Teile Ihrer Flotte an
- **Framework-Labels**: Taggen Sie Regeln mit Compliance-Framework-Referenzen (z.B. „PCI-DSS 5.2.1") für Audit-Nachvollziehbarkeit
- **Severity-Stufen**: Critical, High, Medium, Low — priorisieren Sie den Remediation-Aufwand

### Webhook-Events bei Violations

**Was es macht:**
13 Webhook-Event-Typen inklusive `enforcement.violation.new` und `enforcement.violation.resolved`, zugestellt via HMAC-SHA256-signiertem HTTP POST an Ihre registrierten Endpoints.

**Kundennutzen:**

- **Echtzeit-Alerting**: Leiten Sie Violations an Slack, PagerDuty, ServiceNow oder Ihr SIEM weiter — sobald eine verbotene App auftaucht, weiß Ihr Team Bescheid
- **Automatisierte Remediation**: Triggern Sie Runbooks oder Orchestrierungs-Workflows bei erkannten Violations
- **Manipulationssichere Zustellung**: HMAC-SHA256-Signierung stellt sicher, dass Webhook-Payloads nicht im Transit verändert wurden
- **Resiliente Zustellung**: Auto-Deaktivierung nach 10 aufeinanderfolgenden Fehlern verhindert unkontrollierte Retry-Schleifen

**Vollständiger Webhook-Event-Katalog:**

| Kategorie      | Events                                                                                                                 |
| -------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Sync           | `sync.completed`, `sync.failed`                                                                                        |
| Klassifikation | `classification.completed`, `classification.anomaly_detected`                                                          |
| Enforcement    | `enforcement.check.completed`, `enforcement.violation.new`, `enforcement.violation.resolved`                           |
| Compliance     | `compliance.check.completed`, `compliance.violation.new`, `compliance.violation.resolved`, `compliance.score.degraded` |
| Audit          | `audit.chain.integrity_failure`                                                                                        |

---

## Integration & UX

### Unified Violations View

**Was es macht:**
Eine einzige Ansicht, die Violations aus Compliance-Modul und Enforcement-Modul zusammenführt — mit Filterung nach Quelle (Compliance/Enforcement), Severity und Pagination.

**Kundennutzen:**

- **Ein Ort für alles**: Ihr SOC-Analyst muss nicht zwei verschiedene Screens prüfen — alle Violations, unabhängig von der Quelle, erscheinen in einem filterbaren Feed
- **Modulübergreifende Korrelation**: Sehen Sie, ob eine Enforcement-Violation (verbotene App) auch eine Compliance-Violation (PCI-Control-Failure) für denselben Agent auslöst
- **Export**: Laden Sie den Unified Feed als CSV herunter für externe Verarbeitung oder Reporting

### Shared Components & Picker

**Was es macht:**
Wiederverwendbare UI-Komponenten — Group Picker, Tag Picker, Taxonomy Category Picker, Category Sidebar — konsistent eingesetzt über Compliance-, Enforcement- und Fingerprint-Module.

**Kundennutzen:**

- **Konsistente Bedienung**: Die Auswahl von Scope (Gruppen, Tags) funktioniert überall gleich — keine Einarbeitungszeit beim Wechseln zwischen Modulen
- **Suche und Filter**: Alle Picker unterstützen Suche, Multi-Select und zeigen kontextuelle Metadaten (Agent-Anzahl, Eintrags-Anzahl)

### Echtzeit-Dashboard & WebSocket-Updates

**Was es macht:**
Ein Haupt-Dashboard mit Fleet-Health (OS-Verteilung, Maschinentypen, Netzwerkstatus), App-Intelligence-Metriken, Fingerprinting-Fortschritt, Compliance-Scores und Enforcement-Violations — in Echtzeit aktualisiert via WebSocket.

**Kundennutzen:**

- **Live-Betriebsansicht**: Sync-Fortschritt, Compliance-Check-Ergebnisse und Enforcement-Evaluierungen streamen in Echtzeit in den Browser — kein manueller Refresh
- **Automatische Reconnection**: WebSocket-Verbindungen reconnecten mit exponentiellem Backoff; Auth-Fehler triggern automatischen Token-Refresh
- **Leichtgewichtig**: Pure-CSS-Visualisierungen (keine schwere Charting-Library) — das Dashboard lädt schnell, auch in eingeschränkten Netzwerken

### In-App Getting Started Guide

**Was es macht:**
Ein Zwei-Tab-Onboarding-Guide: **Tenant Guide** (11 Schritte von initialen Settings bis Compliance) für alle Benutzer, und **Platform Guide** (6 Schritte für Multi-Tenant-Management) für Super Admins. Deployment-aware — SaaS vs. Self-Hosted zeigt die passenden Inhalte.

**Kundennutzen:**

- **Self-Service-Onboarding**: Neue Benutzer folgen einem strukturierten Pfad vom ersten Sync bis zum ersten Compliance-Report — ohne externe Dokumentation
- **Rollengerecht**: Analysten sehen den Tenant-Workflow; Plattform-Admins sehen Tenant-Management, Library-Quellen und Audit-Konfiguration
- **Verkürzt die Time-to-Value**: Geführtes Setup bedeutet, Ihr Team ist ab Tag 1 produktiv, nicht nach einer Woche Dokumentations-Studium

### Toast-Notifications & Bestätigungsdialoge

**Was es macht:**
Systemweite Toast-Notifications (Success, Error, Info) mit Auto-Dismiss und Inline-Bestätigungsdialoge für destruktive Aktionen (Regel löschen, Benutzer entfernen, API Key revoken).

**Kundennutzen:**

- **Sofortiges Feedback**: Jede Aktion erzeugt eine sichtbare Bestätigung — kein Rätselraten „hat es geklappt?"
- **Schutz vor destruktiven Aktionen**: Löschungen erfordern explizite Bestätigung und verhindern versehentlichen Datenverlust

---

## Enterprise-Readiness

### Security Hardening

**Was es macht:**

| Ebene                       | Implementierung                                                                                                                          |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **HTTP Security Headers**   | CSP, HSTS (1 Jahr), X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy                                         |
| **Rate Limiting**           | Per-IP Sliding Window (100 Req/Min global, 5 Req/Min auf Login)                                                                          |
| **Body Size Limit**         | 10 MB maximale Request-Payload                                                                                                           |
| **Input-Validierung**       | Pydantic v2 Strict Types auf allen API-Endpoints; Schema-Violations werden mit HTTP 422 abgelehnt                                        |
| **Passwortsicherheit**      | bcrypt (adaptiver Salt), HaveIBeenPwned-Breach-Checking, Passwort-Historie, Account-Lockout                                             |
| **Session-Sicherheit**      | Serverseitiges Tracking, Family-basierte Token-Reuse-Erkennung, sofortige Revocation                                                    |
| **API Key Format**          | `sentora_sk_live_`-Prefix — erkennbar durch GitHub Secret Scanner                                                                        |
| **Audit Trail**             | SHA-256-Hash-Chain mit Epoch-Segmentierung, Manipulationserkennung, Cold-Storage-Export, Air-Gapped-CLI-Verifizierung                    |
| **Credential-Trennung**     | Profildaten und Auth-Credentials in getrennten Collections gespeichert — Credentials werden niemals in API-Responses exponiert           |
| **Token-Redaction**         | S1 API Tokens automatisch in allen Logs maskiert                                                                                         |

**Kundennutzen:**

- **Audit-bereite Sicherheitsarchitektur**: Security Headers, Rate Limiting und Input-Validierung erfüllen Enterprise-Security-Review-Anforderungen ab Werk
- **Forensischer Audit Trail**: Die SHA-256-Hash-Chain liefert kryptografischen Beweis, dass Audit-Logs nicht manipuliert wurden — eine Anforderung für SOC 2 und regulatorische Audits
- **Breach-Aware Passwörter**: Passwörter werden vor Akzeptanz gegen bekannte Breaches geprüft — reduziert das Credential-Stuffing-Risiko

### Testabdeckung

**Was es macht:**
72 Test-Dateien (23 Unit, 41 Integration, plus Frontend und E2E), erzwungene 85%-Backend-Coverage-Gate, echte MongoDB in Tests (keine Mocks) und Security-spezifische Test-Suiten (Injection, Authorization, Audit Logging).

**Kundennutzen:**

- **Zuverlässigkeit**: 85% Coverage-Minimum im CI erzwungen — Regressionen werden erkannt, bevor sie in Produktion gelangen
- **Echte Datenbank-Tests**: Tests laufen gegen echte MongoDB, nicht gegen Mocks — was im CI besteht, besteht auch in Produktion
- **Security-Tests**: Dedizierte Test-Suiten für NoSQL-Injection, Authorization-Bypass und Audit-Integrität — Security ist kein Nachgedanke

### DevOps & Deployment

**Was es macht:**

| Fähigkeit                | Details                                                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Container**            | Multi-Stage Docker Build (Node 22 → Python 3.12-slim), Non-Root-User (UID 1001), Ressourcen-Limits                                           |
| **Health Checks**        | `/health` (Liveness), `/health/ready` (Readiness mit MongoDB-Check), `/health/replica` (Replica-Set-Status)                                  |
| **HA-fähig**             | Multi-Worker-Modus mit Distributed Locking; konfigurierbar via `WORKERS`-Umgebungsvariable                                                  |
| **CI/CD**                | 8 GitHub-Actions-Gates: Pre-Commit, Backend-Tests, Frontend-Tests, E2E, pip-audit, Bandit SAST, Docker Build + Trivy-Scan, SBOM-Generierung  |
| **Observability**        | OpenTelemetry-Tracing (opt-in), Prometheus-Metrics-Endpoint, Loguru Structured Logging                                                       |
| **Container-Sicherheit** | Trivy-Scan auf CRITICAL/HIGH CVEs, Alpine-basierte Images mit `apk upgrade --no-cache`                                                      |
| **SBOM**                 | CycloneDX Software Bill of Materials, generiert auf dem Main-Branch                                                                          |

**Kundennutzen:**

- **Produktionsreife Container**: Non-Root-Ausführung, Health Checks, Ressourcen-Limits und CVE-Scanning — erfüllt Enterprise-Container-Security-Policies
- **Beobachtbar**: Distributed Tracing (Jaeger/Datadog/etc.), Prometheus-Metrics und Structured Logging — Ihr Ops-Team kann Sentora mit bestehenden Tools überwachen
- **CI/CD-gated**: Jede Änderung durchläuft 8 automatisierte Quality-Gates vor dem Merge — inklusive Security-Scanning (SAST, Dependency-Audit, Container-Scan)
- **SBOM**: Software Bill of Materials für Supply-Chain-Transparenz — zunehmend erforderlich im Enterprise-Beschaffungswesen

### Dokumentation

**Was es macht:**
21 Architectural Decision Records (ADRs), modulspezifische Dokumentation, eine umfassende Security-Policy (SECURITY.md), ein autoritativer Test-Standard (TESTING.md, 26 KB), Datenmodell-Dokumentation (41 KB), Quickstart-Guide, Troubleshooting-Guide und Changelog.

**Kundennutzen:**

- **Selbstdokumentierende Architektur**: ADRs erklären nicht nur was gebaut wurde, sondern warum — Ihr Team versteht Design-Trade-offs ohne Reverse-Engineering des Codes
- **Onboarding-Beschleunigung**: Neue Teammitglieder können das System über strukturierte Dokumentation verstehen, nicht über Stammwissen
- **Audit-Evidence**: Security- und Compliance-Dokumentation dient als Nachweis-Artefakt für SOC 2 und ISO-Audits

---

## Differenzierung

### vs. Generische IT-Asset-Tools (Lansweeper, NinjaOne)

Generische Asset-Tools entdecken und inventarisieren Hardware und Software in Ihrem Netzwerk. Sentora konkurriert nicht auf Breite der Discovery — es scannt nicht Ihr Netzwerk nach Druckern und patcht keine Windows-Updates.

**Wo Sentora tiefer geht:**

- **Compliance-Mapping**: Lansweeper zeigt Ihnen, was installiert ist. Sentora sagt Ihnen, ob das Installierte mit SOC 2 CC7.1 oder BSI SYS.2.1.A6 konform ist — und produziert das Nachweis-Artefakt
- **Software Intelligence**: TF-IDF-Fingerprinting und Lift Scoring analysieren, welche Applikationen für jede Gruppe charakteristisch sind — generische Asset-Tools zeigen flache Inventare
- **Enforcement-Policies**: Forbidden/Required/Allowlist-Regeln mit Echtzeit-Violation-Webhooks — nicht nur „diese App existiert", sondern „diese App darf nicht existieren, und hier ist, wen man benachrichtigen muss"
- **EDR-Tiefe**: Sentora nutzt die EDR-API als autoritative Datenquelle — Agent-Version, Online-Status, Gruppenzugehörigkeit, Tags — und baut Compliance-Logik darauf auf

**Multi-EDR-Architektur:** Sentora unterstützt mehrere EDR-Plattformen über ein Source-Adapter-Pattern. SentinelOne ist der erste vollständig implementierte Adapter. CrowdStrike und Defender folgen als nächste. Das kanonische Datenmodell stellt sicher, dass alle Compliance-Checks, Enforcement-Regeln und Reports source-agnostisch arbeiten.

### vs. Breite GRC-Plattformen (Drata, Vanta, Sprinto)

GRC-Plattformen verwalten Ihr gesamtes Compliance-Programm: Policy-Management, Vendor Assessments, Employee Training Tracking, Access Reviews, Cloud Posture. Sentora macht nichts davon.

**Wo Sentora tiefer ist:**

- **Endpoint-Level-Granularität**: GRC-Plattformen prüfen „Haben Sie ein EDR?" (Ja/Nein). Sentora prüft „Ist der EDR-Agent auf Version ≥23.4, online, auf 47.832 von 48.000 Endpoints, und gibt es 3 Agents, die unautorisierte Cryptocurrency-Miner im Berliner Büro betreiben?"
- **10 spezialisierte Check-Typen**: Nicht nur „Control besteht oder nicht", sondern 10 verschiedene Evaluierungsmethoden, speziell für Endpoint- und Applikations-Compliance gebaut
- **Fingerprint Intelligence**: Keine GRC-Plattform bietet TF-IDF-basiertes Software-Fingerprinting oder statistische Anomalie-Erkennung auf Endpoint-Ebene
- **BSI IT-Grundschutz**: Drata und Vanta fokussieren auf SOC 2 und ISO 27001. Sentora liefert 16 BSI-Controls, gemappt auf spezifische Bausteine (SYS.2.1, APP.6, OPS.1.1.3) auf drei Anforderungsstufen

**Wo Sentora schmaler ist:**

- Kein Policy-Dokumenten-Management
- Kein Vendor-Risk-Assessment
- Kein Employee-Training-Tracking
- Keine Cloud-Infrastruktur-Posture (AWS, GCP, Azure)
- Keine Access-Review-Workflows

**Empfohlener Ansatz:** Nutzen Sie Sentora neben Ihrer GRC-Plattform. Sentora liefert die Endpoint-Compliance-Evidence, die in Ihr breiteres Compliance-Programm einfließt.

### vs. Endpoint-Security-Suiten (Qualys, Tanium, Axonius)

Diese Plattformen bieten Vulnerability Management, Asset Discovery und Endpoint-Visibilität über heterogene Umgebungen.

**Wie Sentora diese ergänzt:**

- **EDR-Tiefe statt Breite**: Während Axonius Daten aus Dutzenden Quellen mit jeweils flacher Integration aggregiert, geht Sentora bei EDR-Quellen in die Tiefe — extrahiert Compliance-Intelligence, die ein Verständnis des EDR-Datenmodells erfordert (Groups, Tags, Agent Lifecycle, Application Inventory)
- **Compliance-first**: Qualys fokussiert auf Schwachstellen (CVEs). Sentora fokussiert auf Compliance-Posture (ist die richtige Software installiert, fehlt die falsche Software, ist der Agent aktuell und online)
- **Software-Klassifikation**: Keines dieser Tools bietet TF-IDF-Fingerprinting mit automatischer gruppenbasierter Vorschlags-Generierung
- **Enforcement mit Taxonomie**: Tanium kann Policies durchsetzen, aber Sentoras Taxonomie-basiertes Pattern-Matching bedeutet, dass Regeln sich automatisch an Variationen in App-Bezeichnungen anpassen

**Die ehrliche Position:** Wenn Sie Vulnerability Scanning, Patch Deployment oder plattformübergreifendes Endpoint Management benötigen, ist Sentora kein Ersatz. Es ist die Compliance-Intelligence-Schicht, die auf Ihrem EDR-Deployment aufsetzt und die Frage beantwortet: „Sind unsere Endpoints konform mit Framework X — und wenn nicht, welche, warum, und wie beheben wir es?"

---

## BSI IT-Grundschutz — DACH-Spotlight

### Warum BSI IT-Grundschutz wichtig ist

BSI IT-Grundschutz ist die umfassende Methodik des Bundesamts für Sicherheit in der Informationstechnik zur Umsetzung von Informationssicherheitsmanagement. Für Organisationen in Deutschland, Österreich und der Schweiz dient er als:

- **Regulatorische Baseline**: KRITIS-Betreiber (Kritische Infrastrukturen) in Deutschland sind gesetzlich verpflichtet, IT-Sicherheitsmaßnahmen nachzuweisen — BSI IT-Grundschutz ist die anerkannte Methodik
- **Zertifizierungspfad**: BSI IT-Grundschutz-Zertifizierung (ISO 27001 auf Basis von IT-Grundschutz) wird von Bundes- und Landesbehörden anerkannt und ist zunehmend Voraussetzung in öffentlichen Vergabeverfahren
- **Versicherung und Haftung**: Der Nachweis von BSI-Compliance kann relevant sein für Cyber-Versicherungsprämien und die Reduktion der Geschäftsführerhaftung unter NIS2/IT-Sicherheitsgesetz 2.0
- **Kundenanforderungen**: Große deutsche Unternehmen fordern zunehmend BSI-Compliance von ihren Zulieferern und Dienstleistern

### Sentoras 16 BSI-Controls

Sentora bildet 16 automatisierte Controls auf spezifische BSI-Bausteine über drei Anforderungsstufen ab:

**Basis (MUSS — Verpflichtend)**

| Control-ID             | Baustein          | Was geprüft wird                                                       |
| ---------------------- | ----------------- | ---------------------------------------------------------------------- |
| BSI-SYS.2.1.A6         | Allgemeiner Client | EDR-Agent installiert und aktiv                                       |
| BSI-SYS.2.1.A6-ONLINE  | Allgemeiner Client | Agent erreichbar und an Management-Konsole meldend                     |
| BSI-APP.6.A1           | Allgemeine Software| Software-Inventar vollständig (Classification Coverage ≥70%)           |
| BSI-APP.6.A1-SYNC      | Allgemeine Software| Datenaktualität — Sync innerhalb akzeptablem Fenster abgeschlossen     |
| BSI-APP.6.A4           | Allgemeine Software| Delta-Erkennung — unautorisierte Software-Änderungen geflaggt          |
| BSI-OPS.1.1.3.A15-EDR  | Patch Management   | EDR-Agent auf aktuellem Versionsstand                                  |

**Standard (SOLLTE — Empfohlen)**

| Control-ID        | Baustein           | Was geprüft wird                                              |
| ------------------ | ------------------ | ------------------------------------------------------------- |
| BSI-SYS.2.1.A3    | Allgemeiner Client  | Auto-Update-Mechanismen aktiv                                 |
| BSI-SYS.2.1.A4    | Allgemeiner Client  | Backup-Software vorhanden                                     |
| BSI-APP.6.A2      | Allgemeine Software | Erforderliche Applikationen gemäß Katalog installiert         |
| BSI-APP.6.A5      | Allgemeine Software | Ungenutzte/unautorisierte Software zur Deinstallation markiert|
| BSI-OPS.1.1.3.A1  | Patch Management    | Patch-Management-Prozess validiert                            |

**Erhöhter Schutzbedarf**

| Control-ID                   | Baustein           | Was geprüft wird                                                      |
| ---------------------------- | ------------------ | --------------------------------------------------------------------- |
| BSI-SYS.2.1.A42              | Allgemeiner Client  | Software-Allowlist durchgesetzt — nur freigegebene Applikationen      |
| BSI-SYS.2.1.A42-UNCL         | Allgemeiner Client  | Schwellwert für nicht-klassifizierte Applikationen (Obergrenze)       |
| BSI-APP.6.A1 (erhöht)        | Allgemeine Software | Höhere Classification-Coverage-Anforderung (≥85%)                     |
| Weitere erhöhte Controls     | Diverse             | Erweiterte Schutzmaßnahmen für Hochsicherheitsumgebungen              |

### Warum das ein Alleinstellungsmerkmal ist

- **Wenige Endpoint-Tools automatisieren BSI-Controls**: Die meisten GRC-Plattformen (Drata, Vanta, Sprinto) fokussieren auf SOC 2 und ISO 27001. BSI IT-Grundschutz erfordert deutschlandspezifisches Baustein-Mapping, das internationale Plattformen selten implementieren
- **Baustein-Granularität**: Sentora mappt Controls auf spezifische BSI-Bausteine (SYS.2.1, APP.6, OPS.1.1.3) — nicht generische „Haben Sie Endpoint-Schutz?"-Checkboxen
- **Drei Anforderungsstufen**: Die Basis/Standard/Erhöht-Trennung bildet die tatsächliche BSI-Methodik ab — Ihr Auditor sieht die Struktur, die er erwartet
- **Automatisierte Evidence**: Statt manuell zu dokumentieren „wir haben Virenschutz auf unseren Clients" (SYS.2.1.A6), zeigt Sentora den exakten Abdeckungsgrad über Ihre gesamte Flotte, mit Per-Agent-Detail und historischem Trend

Für DACH-Organisationen, die eine BSI-Zertifizierung anstreben oder KRITIS-Compliance nachweisen müssen, liefert Sentora automatisierte, kontinuierliche Evidence für 16 Endpoint-bezogene Controls — und reduziert die Audit-Vorbereitung von Wochen manueller Evidence-Sammlung auf eine Dashboard-Ansicht mit exportierbaren Ergebnissen.

---

## Typische Use Cases

### 1. CISO bereitet SOC-2-Audit vor

**Problem:** Das SOC-2-Audit ist in 6 Wochen. Der Auditor wird Nachweise verlangen, dass Endpoints aktuelle EDR-Agents haben, keine verbotene Software läuft und Applikations-Inventare klassifiziert sind. Heute lebt diese Evidence in EDR-Exporten, Spreadsheets und Stammwissen.

**Wie Sentora es löst:**

- Verbinden Sie Sentora mit Ihrem EDR-Tenant → initialer Sync in Minuten abgeschlossen
- 15 SOC-2-Controls werden automatisch gegen Live-Daten evaluiert
- Das Compliance-Dashboard zeigt: „SOC 2: 87% — 13 von 15 Controls bestanden"
- Drill-Down in die 2 fehlschlagenden Controls: 47 Agents mit veralteter EDR-Version, 12 Agents mit nicht-klassifizierten Applikationen über dem Schwellwert
- Violations-Feed als CSV exportieren → an das Ops-Team zur Remediation übergeben
- Checks nach Remediation erneut ausführen → Score aktualisiert auf 100%

**Ergebnis:** Audit-Evidence wird kontinuierlich generiert, nicht in Panik zusammengestellt. Der Auditor sieht Echtzeit-Compliance-Posture, nicht einen Point-in-Time-Snapshot, der bereits veraltet ist.

### 2. IT-Ops setzt verbotene Software flottenweit durch

**Problem:** Die Security-Policy verbietet Cryptocurrency-Mining-Software und unautorisierte Remote-Access-Tools. Aktuell durchsucht jemand quartalsweise manuell die EDR-Konsole — und übersieht Installationen zwischen den Prüfungen.

**Wie Sentora es löst:**

- Erstellen Sie eine **Forbidden**-Enforcement-Regel auf die Taxonomie-Kategorie „Cryptocurrency"
- Scoping auf alle Gruppen (oder gezielt auf Hochrisiko-Gruppen über den Group Picker)
- Severity auf **Critical** setzen
- Webhook-Endpoint registrieren, der auf Ihren Slack-Channel oder ServiceNow zeigt
- Jeder Sync triggert die Evaluierung → sobald ein Mining-Tool auf irgendeinem Agent erscheint, feuert `enforcement.violation.new`
- Die Unified Violations View zeigt welcher Agent, welche App, welche Gruppe — mit Remediation-Hinweis

**Ergebnis:** Kontinuierliches Enforcement statt quartalsweiser Stichproben. Violations in Minuten erkannt, nicht in Monaten. Webhook-Integration stellt sicher, dass das richtige Team sofort benachrichtigt wird.

### 3. Compliance-Team weist BSI-IT-Grundschutz-Konformität nach

**Problem:** Ihre Organisation ist KRITIS-Betreiber in Deutschland. Der BSI-Auditor benötigt Nachweise für die IT-Grundschutz-Bausteine SYS.2.1 (Allgemeiner Client) und APP.6 (Allgemeine Software). Aktuell wird diese Evidence manuell aus mehreren Systemen zusammengestellt.

**Wie Sentora es löst:**

- Das BSI-IT-Grundschutz-Framework ist vorkonfiguriert mit 16 Controls, gemappt auf spezifische Bausteine
- Basis-Level (MUSS) Controls prüfen: EDR-Agent aktiv, Agent online, Software-Inventar vollständig, Daten aktuell, keine unautorisierten Änderungen, EDR-Version aktuell
- Standard-Level (SOLLTE) Controls prüfen: Auto-Updates aktiv, Backup-Software vorhanden, erforderliche Applikationen installiert, ungenutzte Software geflaggt, Patch Management validiert
- Das Compliance-Dashboard zeigt Per-Control-Status auf jeder Anforderungsstufe (Basis/Standard/Erhöht)
- Control-Ergebnisse für den Auditor exportieren — jedes Control referenziert seine BSI-Baustein-ID

**Ergebnis:** 16 BSI-Controls werden automatisch gegen Live-Endpoint-Daten evaluiert. Der Auditor sieht die Baustein-Struktur, die er erwartet — mit Per-Agent-Evidence und historischen Compliance-Trends.

### 4. Security-Analyst untersucht Shadow IT

**Problem:** Das Security-Team vermutet, dass unautorisierte Software sich über die Flotte ausbreitet, aber bei 80.000 installierten Applikationen auf 15.000 Agents ist manuelle Überprüfung unmöglich.

**Wie Sentora es löst:**

- Die Fingerprint Engine führt TF-IDF-Analyse über alle Gruppen durch → generiert statistische Profile der erwarteten Software pro Gruppe
- Die Classification Engine flaggt Applikationen, die keinem Fingerprint, Library-Eintrag oder keiner Taxonomie-Kategorie entsprechen
- Anomalie-Erkennung macht Applikationen sichtbar, die in Gruppen auftauchen, in denen sie statistisch nicht existieren sollten
- Der `unclassified_threshold`-Compliance-Check flaggt Agents mit zu vielen unbekannten Applikationen
- Der Analyst prüft Anomalien in der Classification View, akzeptiert oder verwirft Ergebnisse und erstellt Enforcement-Regeln für bestätigte Violations

**Ergebnis:** Von 80.000 Applikationen zu einer priorisierten Liste statistischer Anomalien in Minuten. Shadow-IT-Erkennung wird datengetrieben statt anekdotisch.

### 5. MSSP verwaltet mehrere Kunden-Tenants

**Problem:** Sie sind ein Managed Security Service Provider mit 12 EDR-Kunden-Tenants. Jeder Kunde hat unterschiedliche Compliance-Anforderungen (einige brauchen SOC 2, andere PCI DSS, zwei brauchen BSI). Heute wird jeder Kunde separat verwaltet, ohne einheitliche Sicht.

**Wie Sentora es löst:**

- Multi-Tenant-Architektur: Jeder Kunde erhält eine isolierte Datenbank — kein Datenabfluss zwischen Tenants
- Platform-Level Compliance View aggregiert Scores über alle Tenants
- Per-Tenant-Compliance-Konfiguration: Kunde A erhält SOC 2 + PCI DSS, Kunde B nur BSI IT-Grundschutz
- API-Key-Authentifizierung mit Tenant-Scoping ermöglicht kundenspezifische Automatisierung
- Webhook-Events feuern per Tenant — leiten Sie die Violations jedes Kunden an dessen jeweilige Benachrichtigungskanäle

**Ergebnis:** Einheitliches Compliance-Management über Ihr Kundenportfolio. Eine Sentora-Instanz, 12 Tenants, jeder mit eigenen Compliance-Frameworks, Enforcement-Regeln und Notification-Workflows.
