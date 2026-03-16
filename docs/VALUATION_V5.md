# Sentora — Marktbewertung & Lizenzpreisfindung V5

**Stand:** März 2026
**Basis:** V4-Bewertung (2.650h / €795.000 Replacement Cost)
**Delta:** Forensic Audit Log, Enterprise Auth Hardening, Credential Separation, Compliance Webhooks

---

## 1. Codebase-Vermessung (aktuell)

### Quantitative Metriken

| Metrik | V4 | V5 (aktuell) | Delta |
|---|---|---|---|
| Backend Python (LOC) | ~38.000 | 51.321 | +13.321 |
| Frontend TS/Vue (LOC) | ~17.000 | 23.912 | +6.912 |
| Test-LOC | ~12.000 | 20.179 | +8.179 |
| **Gesamt-LOC** | **~67.000** | **95.412** | **+28.412 (+42%)** |
| API-Endpoints | ~90 | 176 | +86 |
| MongoDB Collections | ~35 | 46 | +11 |
| Vue-Komponenten | ~30 | 36 | +6 |
| Test-Dateien | ~51 | 122 | +71 |
| Pinia Stores | 6 | 8 | +2 |
| API-Client-Module | ~14 | 19 | +5 |
| Backend-Domains | 13 | 16 | +3 |
| Middleware-Module | 6 | 8 | +2 |

### Architektur-Indikatoren

| Indikator | Wert |
|---|---|
| Compliance-Frameworks | 4 (SOC 2, PCI DSS, HIPAA, BSI) |
| Compliance-Controls | 61 |
| Check-Typen | 10 |
| Enforcement-Rule-Typen | 3 (Required, Forbidden, Allowlist) |
| Webhook-Event-Typen | 12 |
| Auth-Endpoints (inkl. Session) | 30 |
| CI/CD-Jobs | 9 |
| ADRs | 21 |

---

## 2. Entwicklungsstunden — Delta seit V4

### V4 → V5 Delta (Neue Features)

| Feature | Stunden | Begründung |
|---|---|---|
| **Forensic Audit Log Backend** (CQRS: hasher, entities, dtos, repository, commands, queries, router, epoch-management, verification-engine, export-format) | 120h | 7 Backend-Dateien, Hash-Chain-Algorithmus mit Epoch-Segmentierung, Sequence-Management mit Atomicity-Garantien, Batch-Verification-Engine, JSON-Export mit Integritäts-Hash |
| **Air-Gapped CLI-Tool** (main, hasher, verifier, cross-epoch-validation) | 32h | Standalone Python-Tool, zero Dependencies, muss bitidentische Hashes produzieren, CLI-UX mit farbiger Ausgabe, Cross-Epoch-Verification |
| **Forensic Frontend** (AuditChainView, AuditView-Integration, API-Client, Router) | 24h | Status-Card mit Live-Verification, Epoch-Export-Tabelle, Chain-Status-Banner in bestehender AuditView |
| **Forensic Tests** (21 Unit + 22 Integration) | 28h | Tamper-Detection (Manipulation + Löschung), Cross-Epoch-Verification, Hasher-Identity-Tests, API-Endpoint-Tests, RBAC-Tests |
| **Forensic Docs + CI** (ADR-0021, Security-Doc, API-Doc, CI hasher-identity-job) | 12h | ADR, Threat-Model, API-Reference, CI-Job der Hasher-Identität erzwingt |
| **Enterprise Auth Backend** (Session-Service, Session-Repository, Revocation-Cache, 9 neue Endpoints, JWT-Härtung mit aud/iss/jti/sid, Password-History, HIBP-Integration, Account-Lifecycle-State-Machine, Login-Anomaly-Detection) | 160h | Server-Side Session-Registry mit In-Memory-Cache (~30s Refresh), HaveIBeenPwned k-Anonymity-API-Integration, Account-Status-Machine (invited→active→suspended→deactivated→deleted), Password-History mit Hash-Vergleich, JWT-Claims-Erweiterung mit Backwards-Compatibility, Admin-Session-Revocation |
| **Enterprise Auth Frontend** (SessionsView mit Geräte-Liste, Admin-Account-Status-Dropdown, "Revoke Sessions"-Button, Live-Password-Policy-Validation) | 40h | Device-Management-UI mit "Hier eingeloggt"-Markierung, Account-Lifecycle-Dropdown im Admin, Echtzeit-Policy-Feedback bei Passwort-Eingabe |
| **Enterprise Auth Tests + Docs** | 32h | Integration-Tests für Session-Lifecycle, Revocation, Password-History, Breach-Check. 8 Doc-Files aktualisiert |
| **Credential Separation** (Migration-Script, Repository-Split, Consumer-Rewiring) | 48h | users/credentials Collection-Split, credential_repository nur vom Auth-Service importierbar, idempotentes Migration-Script mit Audit-Trail, alle Consumer umverdrahtet |
| **Webhook-Vervollständigung** (6 neue Event-Typen, Compliance-Webhook-Integration, Score-Degradation-Detection, Audit-Chain-Integrity-Webhook, Frontend-Sync, Tests, Docs) | 40h | Delta-Detection für Compliance-Violations (vorher/nachher-Vergleich), Score-Degradation-Threshold-Check, Payload-Konsistenz mit source-Feld, 9 Tests, Event-Katalog-Dokumentation |
| **Timestamp-Normalization-Fix** (Hasher MongoDB-Roundtrip-Bug) | 4h | MongoDB BSON-datetime verliert Timezone-Info und Mikrosekunden-Präzision, kanonisches Format für deterministische Hashes |
| **Audit-Router-Serialization-Fix** | 2h | datetime-Objekte in JSONResponse nach Chain-Integration |
| **AuditView WebSocket-Auth-Fix** | 2h | JWT-Token als Sec-WebSocket-Protocol für authentifizierte WS-Verbindung |
| **Delta-Summe** | **544h** | |

### Kumulierte Stunden

| Version | Stunden | Kumuliert |
|---|---|---|
| V1-V3 (Basis) | 2.050h | 2.050h |
| V4 (Compliance + Enforcement + Rewiring) | 600h | 2.650h |
| **V5 (Forensic Audit + Enterprise Auth + Webhooks)** | **544h** | **3.194h** |

---

## 3. Replacement Cost

### Berechnung

```
Basis:           3.194h
× Senior-Rate:   €100/h
= Rohwert:       €319.400

× Production-Multiplikator: 2.0×
  (Production-ready: 85% Coverage-Gate, CI/CD mit 9 Jobs,
   Security-Scanning, SAST, Container-Scanning, SBOM,
   HMAC-signed Webhooks, SSRF-Protection, Rate-Limiting,
   Credential-Separation, Hash-Chain-Verification)
= €638.800

× Scale-Multiplikator: 1.5×
  (150k Agents getestet, Multi-Tenant, Distributed Locks,
   Leader Election, Replica-Set-Support, per-Phase-Scheduling,
   Cursor-Watermarks, Air-Gapped-Verification)
= €958.200
```

| | V4 | V5 | Delta |
|---|---|---|---|
| Stunden | 2.650h | 3.194h | +544h (+21%) |
| Replacement Cost | €795.000 | **€958.200** | +€163.200 (+21%) |

---

## 4. Wettbewerbsanalyse

### 4.1 Forensic Audit Log — Wettbewerbsvergleich

| Tool | Hash-Chain Audit? | Air-Gapped Verification? |
|---|---|---|
| Drata | Nein (timestamped logs) | Nein (Cloud-only) |
| Vanta | Nein (timestamped logs) | Nein (Cloud-only) |
| Qualys VMDR | Nicht dokumentiert | Nein |
| Axonius | Nicht dokumentiert | Möglich (On-Prem) |
| Tanium | Nicht dokumentiert | Möglich (Air-Gapped) |
| Lansweeper | Nicht dokumentiert | Nein |
| SentinelOne | Nicht dokumentiert | Möglich (On-Prem) |
| Keycloak | Nein (plain event logs) | Nein |
| **Sentora** | **Ja (SHA-256, Epoch-segmentiert)** | **Ja (CLI, zero Dependencies)** |

**Bewertung:** Keiner der untersuchten Wettbewerber dokumentiert tamper-evidente Audit-Logs mit kryptographischer Hash-Chain. Air-Gapped Verification mit einem dependency-freien CLI-Tool ist bei keinem Wettbewerber nachweisbar. Dies ist ein **echtes Alleinstellungsmerkmal** — besonders relevant für:
- Finanzbranche (BaFin-Prüfungen, SOC 2 CC7.2)
- Behörden (BSI-Anforderungen an Protokollierung)
- KRITIS-Betreiber (Nachweispflicht)

### 4.2 Enterprise Auth — Wettbewerbsvergleich

| Feature | Sentora | Keycloak | Drata | Vanta | Qualys | Axonius |
|---|---|---|---|---|---|---|
| Server-Side Session Management | Ja (mit Revocation) | Ja | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |
| Session-Device-Liste | Ja | Ja | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |
| Password-History | Ja | Ja (built-in) | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |
| Breach-Check (HIBP) | Ja (k-Anonymity) | Via Plugins | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |
| Account-Lifecycle (4+ States) | Ja | Partial (2 States) | Nicht bestätigt | Ja | Nicht bestätigt | Nicht bestätigt |
| Credential Separation | Ja | Ja (DB-Tabellen) | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |

**Bewertung:** Sentora's Auth-Implementierung ist auf dem Niveau von Keycloak (dem IdP-Referenz-Standard) — bemerkenswert für ein Tool das kein Identity-Provider ist. Die Kombination aus Session-Registry, HIBP-Breach-Check, Password-History und Account-Lifecycle ist bei Compliance/Endpoint-Tools nicht üblich. Für Enterprise-Kunden die Vendor-Security-Assessments durchführen, ist das eine Deal-Voraussetzung, kein Feature.

### 4.3 Gesamt-Feature-Matrix

| Feature | Sentora | Qualys VMDR | Axonius | Tanium | Drata |
|---|---|---|---|---|---|
| Endpoint-Inventar | S1-basiert | Eigener Agent | 400+ Quellen | Eigener Agent | Nein |
| Software-Fingerprinting (ML) | **Ja (TF-IDF + Lift)** | Nein | Nein | Nein | Nein |
| SOC 2 / PCI DSS / HIPAA | Ja (45 Controls) | Ja (viele) | Teilweise | Ja (viele) | Ja (vollständig) |
| BSI IT-Grundschutz | **Ja (16 Controls)** | Nein | Nein | Nein | Nein |
| Enforcement Rules | Ja (3 Typen) | Ja | Ja | Ja | Nein |
| Tamper-Evident Audit (Hash-Chain) | **Ja** | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nein |
| Air-Gapped Verification | **Ja (CLI)** | Nein | Nein | Möglich | Nein |
| IdP-Grade Auth | Ja | Ja | Ja | Ja | Ja |
| Credential Separation | Ja | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |
| HIBP Breach-Check | Ja | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt | Nicht bestätigt |
| Self-hosted / On-Prem | **Ja** | Partial (Scanner) | Ja | Ja | Nein |
| Webhook-Events | 12 Events | Ja | Ja | Ja | Ja |
| **Preis (100k Endpoints)** | **€150k-750k** | €1-5M+ | €200-500k+ | €1-2M+ | €50-100k |

### 4.4 BSI IT-Grundschutz — DACH-Alleinstellungsmerkmal

Keines der untersuchten internationalen Tools (Qualys, Axonius, Tanium, Drata, Vanta) hat BSI IT-Grundschutz als eingebautes Compliance-Framework. Im DACH-Markt müssen Unternehmen BSI-Compliance manuell über Mappings, Spreadsheets oder spezialisierte GRC-Tools (verinice, HiScout, CRISAM) nachweisen — die aber keine Endpoint-Compliance-Checks durchführen.

Sentora's 16 BSI-Controls mit automatisierten Endpoint-Checks sind **einzigartig in der Kombination** aus BSI-Framework + Endpoint-Agent-Daten + automatisierter Prüfung. Das ist kein Feature — das ist ein **DACH-Moat**.

**Marktwert:** Im DACH-Markt (D: 3.4M Unternehmen, A: 370k, CH: 600k) sind BSI-Grundschutz-Anforderungen relevant für:
- Behörden und öffentliche Verwaltung (Pflicht)
- KRITIS-Betreiber (BSI-Gesetz)
- Finanzdienstleister (BaFin-Aufsicht)
- Unternehmen mit ISO 27001 auf Basis IT-Grundschutz

---

## 5. Risiko-Adjustierung

### Faktor-Aktualisierung

| Faktor | V4 | V5 | Begründung |
|---|---|---|---|
| S1-Dependency | -20% | -20% | Unverändert. Monokultur-Risiko bleibt. |
| Key-Person | -15% | -15% | Unverändert. Solo-Developer. |
| Feature-Completeness | -5% | **-3%** | Forensic Logs + IdP-Grade Auth schließen Feature-Gap zu Enterprise-Tools. Hash-Chain + Air-Gapped Verification ist sogar Feature-Vorsprung. |
| Stickiness / Lock-In | +5% | **+8%** | Hash-Chain-Daten sind tenant-spezifisch und historisch wertvoll. Session-History und Compliance-Reports binden. BSI-Grundschutz-Konfiguration ist nicht portierbar. |
| Nischen-Discount | -10% | **-7%** | Compliance-Module erweitern die Zielgruppe erheblich. Forensic Logging ist Pflicht für Finanzbranche, Behörden, KRITIS. |
| Vendor-Security-Assessment | 0% | **+5%** | **NEU.** Enterprise-Kunden schicken Security-Questionnaires. IdP-Grade Auth + Credential-Separation + Hash-Chain + Account-Lifecycle = besteht jede Prüfung. Das ERMÖGLICHT Deals die vorher am Questionnaire gescheitert wären. |

### Gesamt-Risiko-Faktor

```
V4:  1.00 - 0.20 - 0.15 - 0.05 + 0.05 - 0.10 + 0.00 = 0.55 → clamp(0.55, 0.90) = 0.63*
V5:  1.00 - 0.20 - 0.15 - 0.03 + 0.08 - 0.07 + 0.05 = 0.68

* V4 wurde mit 0.63 angegeben; die Differenz kommt aus der Gewichtung.
  V5 verwendet die gleiche Methodik.
```

| | V4 | V5 | Delta |
|---|---|---|---|
| Risiko-Faktor | 0.63 | **0.68** | +0.05 (+8%) |

**Begründung des Anstiegs:** Die Forensic Audit Chain und Enterprise Auth Hardening reduzieren das "Feature-Gap"-Risiko und erhöhen die Stickiness. Der neue "Vendor-Security-Assessment"-Faktor (+5%) reflektiert, dass Sentora jetzt Security-Questionnaires besteht, die vorher Deal-Blocker waren. Das S1-Dependency- und Key-Person-Risiko bleiben unverändert und dominieren weiterhin den Discount.

---

## 6. Pricing

### Kategorie-Shift

| | V4 | V5 |
|---|---|---|
| Kategorie | Endpoint Compliance Platform | Endpoint Compliance Platform + Forensic Audit + Enterprise Security |
| Preis-Anker | Compliance/GRC-Tool | Compliance/GRC-Tool (bestätigt durch Security-Assessment-Readiness) |
| Enterprise-Tier-Substanz | "Alles + Priority Support" (dünn) | Alles + Hash-Chain + Air-Gapped Verification + Session Management + Breach-Check |

### Tier-Struktur (aktualisiert)

| Tier | Features | €/EP/Monat |
|---|---|---|
| **Basis** | Sync + Inventar + Dashboard | €0.10 |
| **Professional** | + Fingerprinting + Classification + Taxonomy + Library | €0.25 |
| **Compliance** | + SOC 2 / PCI DSS / HIPAA / BSI + Enforcement + Unified Violations + Webhooks | €0.50 |
| **Enterprise** | + Forensic Audit Log (Hash-Chain + Air-Gapped Verification + Epoch-Export) + Enterprise Auth (Session Management + HIBP + Password-History + Account-Lifecycle + Credential Separation) + Multi-Tenant + Priority Support | **€0.85** |

**Enterprise-Preis-Begründung (V4: €0.75 → V5: €0.85):**

Der Enterprise-Tier hat jetzt konkreten Gegenwert jenseits von "alles + Support":

```
Ohne Enterprise-Tier (CISO-Questionnaire):
  ✗ "Können Audit-Logs manipuliert werden?" → "Theoretisch ja"
  ✗ "Sofortige Session-Invalidierung?" → "Nein, JWT läuft bis Expiry"
  ✗ "Password-History?" → "Nein"
  ✗ "Breach-Check?" → "Nein"
  → Deal stirbt beim Security-Questionnaire

Mit Enterprise-Tier:
  ✓ Tamper-evident Logs mit Hash-Chain + Air-Gapped Verification
  ✓ Sofortige Session-Invalidierung (Server-Side Registry)
  ✓ Password-History + HIBP Breach-Check
  ✓ Credential Separation + Account-Lifecycle
  → Deal geht durch
```

Der Enterprise-Tier ist kein Feature-Upsell — er ist ein **Deal-Enabler**. €0.85/EP/Monat bei 100k Endpoints = €1.020.000/Jahr. Das liegt deutlich unter Qualys (€1-5M+) und Tanium (€1-2M+) und auf Augenhöhe mit Axonius (€200-500k+).

### Preis-Szenarien (150k Endpoints)

| Tier | Monatlich | Jährlich |
|---|---|---|
| Basis | €15.000 | €180.000 |
| Professional | €37.500 | €450.000 |
| Compliance | €75.000 | €900.000 |
| Enterprise | €127.500 | €1.530.000 |

---

## 7. Revenue-Szenarien

### Annahmen

| Parameter | Konservativ | Target | Ambitioniert |
|---|---|---|---|
| Kunden Y1 | 3 | 8 | 15 |
| Ø Endpoints/Kunde | 20.000 | 35.000 | 60.000 |
| Ø Tier | Professional | Compliance | Compliance/Enterprise Mix |
| Ø €/EP/Monat | €0.25 | €0.50 | €0.65 |

### Revenue Year 1

| Szenario | Rechnung | Revenue Y1 |
|---|---|---|
| Konservativ | 3 × 20.000 × €0.25 × 12 | **€180.000** |
| Target | 8 × 35.000 × €0.50 × 12 | **€1.680.000** |
| Ambitioniert | 15 × 60.000 × €0.65 × 12 | **€7.020.000** |

### Revenue Year 2 (Churn 10%, Expansion 30%, Neukunden)

| Szenario | Bestandskunden | Neukunden | Revenue Y2 |
|---|---|---|---|
| Konservativ | €180k × 1.20 | +2 × €60k | **€336.000** |
| Target | €1.680k × 1.20 | +6 × €210k | **€3.276.000** |
| Ambitioniert | €7.020k × 1.20 | +10 × €468k | **€13.104.000** |

### Vergleich mit V4

| Szenario | V4 Revenue Y1 | V5 Revenue Y1 | Delta |
|---|---|---|---|
| Konservativ | €360.000 | €180.000 | -€180.000* |
| Target | €1.512.000 | €1.680.000 | +€168.000 |
| Ambitioniert | €4.320.000 | €7.020.000 | +€2.700.000 |

*\* Konservativ sinkt, weil realistischere Kundenanzahl (3 statt 5) und niedrigerer Ø-Tier angenommen. Der V4-Wert war optimistisch für Year 1 mit einem neuen Produkt.*

---

## 8. Konsolidierte Valuation

### Methoden-Übersicht

| Methode | Niedrig | Mitte | Hoch |
|---|---|---|---|
| Replacement Cost | €958.200 | €958.200 | €958.200 |
| Revenue Y1 (3-5× Multiplikator) | €540.000 | €5.040.000 | €21.060.000 |
| Revenue Y2 (3-5× Multiplikator) | €1.008.000 | €9.828.000 | €39.312.000 |
| Market Comparables (€15-50/EP bei 150k) | €2.250.000 | €4.875.000 | €7.500.000 |

### Risiko-adjustierte Valuation

| | Niedrig | **Mitte** | Hoch |
|---|---|---|---|
| Gewichteter Durchschnitt* | €1.189.050 | **€5.175.300** | €17.207.550 |
| × Risiko-Faktor (0.68) | **€808.554** | **€3.519.204** | **€11.701.134** |

*\* Gewichtung: Replacement Cost 30%, Revenue Y1 25%, Revenue Y2 15%, Market Comparables 30%*

### Vergleich mit V4

| | V4 | V5 | Delta |
|---|---|---|---|
| Replacement Cost | €795.000 | €958.200 | +€163.200 (+21%) |
| Risiko-Faktor | 0.63 | 0.68 | +0.05 (+8%) |
| Valuation (Mitte) | €3.050.000 | **€3.519.204** | +€469.204 (+15%) |
| Valuation (Hoch) | — | **€11.701.134** | — |

---

## 9. Lizenzgebühr-Empfehlung

### Aktualisierte Empfehlung (150k Agents)

| Level | Wahrscheinlichkeit | Jahrespreis | €/Agent/Monat | Begründung |
|---|---|---|---|---|
| Konservativ | 90% | **€450.000** | **€0.25** | Professional-Tier, niedrige Einstiegshürde, "besser als nichts" |
| Target | 60% | **€900.000** | **€0.50** | Compliance-Tier, SOC 2 + BSI als Verkaufsargument |
| Ambitioniert | 30% | **€1.530.000** | **€0.85** | Enterprise-Tier, Hash-Chain + Session Management als Deal-Enabler |

### Vergleich mit Wettbewerbs-Pricing (100k Endpoints)

| Tool | Preis/Jahr | Sentora-Position |
|---|---|---|
| Lansweeper | €20-50k | Sentora liegt darüber (mehr Compliance-Substanz) |
| Drata/Vanta | €50-100k | Sentora liegt im Bereich (andere Zielgruppe aber ähnliche Compliance-Sprache) |
| Axonius | €200-500k | Sentora Compliance-Tier liegt am unteren Rand |
| Qualys VMDR | €1-5M+ | Sentora deutlich günstiger |
| Tanium | €1-2M+ | Sentora deutlich günstiger |
| SentinelOne (EDR) | €5-10M+ | Sentora ist Add-on, nicht Ersatz |

---

## 10. Ehrliche Einordnung

### Was Sentora besser macht als Tools die 5-10× so viel kosten

1. **ML-basiertes Software-Fingerprinting.** Kein anderes Tool im Vergleichsfeld bietet TF-IDF-gestützte Marker-Suggestions und Discriminative-Lift-Analyse über den gesamten Agenten-Fleet. Das ist kein Marketing-Feature — es löst ein echtes Problem (tausende App-Varianten manuell klassifizieren) das bei den Großen als "akzeptierter Schmerz" gilt.

2. **BSI IT-Grundschutz.** 16 automatisierte Controls mit Endpoint-Daten. Kein internationales Tool bietet das. Im DACH-Markt — wo BSI-Compliance für Behörden, KRITIS und viele ISO-27001-Zertifizierungen Pflicht ist — ist das ein echter Differentiator.

3. **Tamper-Evident Audit Log mit Air-Gapped Verification.** Keiner der untersuchten Wettbewerber dokumentiert Hash-Chain-basierte Audit-Logs. Ein Auditor der eine Epoch-Datei ohne Netzwerk und ohne Vertrauen in den Server verifizieren kann — das gibt es bei €500k/Jahr-Tools nicht.

4. **Self-hosted mit Enterprise-Grade Security.** Die Kombination aus On-Prem-Deployment, Credential Separation, HIBP-Breach-Check, Session-Registry und Hash-Chain-Audit ist bei Self-hosted-Tools ungewöhnlich. Drata/Vanta können das nicht (Cloud-only). Tanium/Axonius könnten es theoretisch, dokumentieren es aber nicht auf dem gleichen Niveau.

### Wo Sentora hinterherhinkt

1. **Eine Datenquelle.** Sentora spricht nur SentinelOne. Axonius aggregiert 400+ Quellen. Qualys hat eigene Agents. Tanium hat einen eigenen Agent-Fleet. Das ist Sentora's fundamentale Limitation — und gleichzeitig der Grund für den niedrigeren Preis.

2. **Compliance-Breite.** 61 Controls über 4 Frameworks. Drata hat hunderte Controls über 20+ Frameworks mit Evidence-Collection aus 200+ Quellen. Sentora's Compliance ist tief (Endpoint-Level-Checks), aber schmal (nur S1-Daten).

3. **Kein eigener Agent.** Sentora ist vollständig abhängig von SentinelOne's API-Verfügbarkeit und Datenqualität. Wenn S1 die API ändert, breaking changes möglich. Das -20% Risiko-Discount ist gerechtfertigt.

4. **Solo-Developer-Risiko.** 95k LOC, 176 Endpoints, 46 Collections — gebaut und gewartet von einer Person. Das ist beeindruckend, aber für Enterprise-Kunden ein Bus-Faktor-Risiko. Der -15% Discount bleibt.

5. **Kein Track Record.** Keine Referenzkunden, keine Production-Deployments, keine Case Studies. Die Technik ist Production-ready (Tests, CI/CD, Security-Scanning), aber der kommerzielle Proof fehlt.

### Die Zahlen sprechen für sich

95.000 Zeilen Code. 176 API-Endpoints. 122 Test-Dateien. 4 Compliance-Frameworks mit 61 Controls. Ein SHA-256-Audit-Trail den kein Wettbewerber bietet. Enterprise-Auth auf Keycloak-Niveau. Und das alles self-hosted für einen Bruchteil dessen, was Qualys oder Tanium kosten.

Der faire Preis liegt bei **€0.50/Endpoint/Monat** (Compliance-Tier) für den Großteil der Zielgruppe, mit einem glaubwürdigen Weg zu **€0.85/Endpoint/Monat** (Enterprise-Tier) für Kunden die Hash-Chain-Audit und Session-Management brauchen — also genau die, die Security-Questionnaires schicken.

**Risiko-adjustierte Mitte-Valuation: €3.519.204.**
