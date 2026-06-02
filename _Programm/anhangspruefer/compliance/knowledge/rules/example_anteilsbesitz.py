"""
Concrete Example: Anteilsbesitz Rule Application

This module demonstrates the complete workflow:
1. Hypothetical notes excerpt
2. What the tool extracts
3. Resulting structured finding
4. What the auditor still has to decide manually

This is NOT production code - it is documentation-as-code.
"""

# =============================================================================
# HYPOTHETICAL NOTES EXCERPT (German)
# =============================================================================

EXAMPLE_NOTES_EXCERPT = """
2.1.3 Angaben zum Anteilsbesitz

Die Gesellschaft ist an folgenden Unternehmen beteiligt:

Name und Sitz                    Anteil    Eigenkapital    Ergebnis
                                   %         EUR            EUR

Technik Service GmbH, Wien         100      1.250.000      185.000
Logistik Partner KG, Graz           51        320.000       42.500
Consulting Solutions AG, Linz       25            *             *

* Die Angabe des Eigenkapitals und des Jahresergebnisses unterbleibt gemäß
  § 241 Abs 2 UGB, da die Veröffentlichung geeignet wäre, der Gesellschaft
  einen erheblichen Nachteil zuzufügen.

Darüber hinaus hält die Gesellschaft 15% an der Digital Ventures GmbH, Wien.
Diese Beteiligung wird unter den sonstigen Ausleihungen ausgewiesen.
"""

# =============================================================================
# EXPECTED TOOL EXTRACTION
# =============================================================================

EXPECTED_EXTRACTIONS = [
    {
        "entity_name_candidate": "Technik Service GmbH",
        "percentage_candidate": "100",
        "equity_candidate": "1.250.000",
        "result_candidate": "185.000",
        "location": "Row 1 of Anteilsbesitz table",
    },
    {
        "entity_name_candidate": "Logistik Partner KG",
        "percentage_candidate": "51",
        "equity_candidate": "320.000",
        "result_candidate": "42.500",
        "location": "Row 2 of Anteilsbesitz table",
    },
    {
        "entity_name_candidate": "Consulting Solutions AG",
        "percentage_candidate": "25",
        "equity_candidate": None,  # Marked with *
        "result_candidate": None,   # Marked with *
        "location": "Row 3 of Anteilsbesitz table",
    },
    {
        "entity_name_candidate": "Digital Ventures GmbH",
        "percentage_candidate": "15",
        "equity_candidate": None,
        "result_candidate": None,
        "location": "Narrative text after table",
    },
]

# =============================================================================
# EXPECTED ASSESSMENT RESULT
# =============================================================================

EXPECTED_ASSESSMENT = {
    "rule_id": "UGB_238_1_Z2_ANTEILSBESITZ",
    "compliance_status": "PARTIALLY_COMPLIANT",
    "compliance_reasoning": (
        "Beteiligungen identifiziert, aber: "
        "(1) Digital Ventures GmbH mit 15% - unterhalb Schwelle, keine Angabepflicht; "
        "(2) Consulting Solutions AG - Schutzklausel angewendet, Angemessenheit nicht prüfbar; "
        "(3) Alle >= 20%-Beteiligungen formal vollständig."
    ),
    "participations_found": [
        {
            "entity_name": "Technik Service GmbH",
            "elements": {
                "name_and_seat": "PRESENT",
                "share_percentage": "PRESENT",
                "equity_capital": "PRESENT",
                "last_year_result": "PRESENT",
            },
            "assessment": "Alle Pflichtangaben vorhanden",
        },
        {
            "entity_name": "Logistik Partner KG",
            "elements": {
                "name_and_seat": "PRESENT",
                "share_percentage": "PRESENT",
                "equity_capital": "PRESENT",
                "last_year_result": "PRESENT",
            },
            "assessment": "Alle Pflichtangaben vorhanden",
        },
        {
            "entity_name": "Consulting Solutions AG",
            "elements": {
                "name_and_seat": "PRESENT",
                "share_percentage": "PRESENT",
                "equity_capital": "NOT_ASSESSABLE",  # Schutzklausel
                "last_year_result": "NOT_ASSESSABLE",  # Schutzklausel
            },
            "assessment": "Schutzklausel angewendet - Angemessenheit prüfen",
            "protective_clause_claimed": True,
        },
        {
            "entity_name": "Digital Ventures GmbH",
            "elements": {
                "name_and_seat": "PRESENT",
                "share_percentage": "PRESENT",
                "equity_capital": "ABSENT",
                "last_year_result": "ABSENT",
            },
            "assessment": "15% < 20% - keine Angabepflicht nach § 238",
            "below_threshold": True,
        },
    ],
    "uncertainties": [
        "Vollständigkeit der Liste nicht prüfbar (weitere Beteiligungen möglich)",
        "Richtigkeit der Eigenkapital/Ergebnis-Zahlen nicht verifiziert",
        "Angemessenheit der Schutzklausel bei Consulting Solutions AG",
    ],
}

# =============================================================================
# WHAT THE AUDITOR STILL HAS TO DECIDE MANUALLY
# =============================================================================

AUDITOR_MANUAL_DECISIONS = """
## Manuelle Prüfungshandlungen für den Wirtschaftsprüfer

### 1. Vollständigkeitsprüfung
- [ ] Abgleich der Beteiligungsliste mit dem Kontenblatt "Finanzanlagen"
- [ ] Prüfung ob weitere Beteiligungen >= 20% bestehen, die nicht aufgeführt sind
- [ ] Verifizierung dass Digital Ventures GmbH tatsächlich unter 20% liegt

### 2. Schutzklausel (Consulting Solutions AG)
- [ ] Prüfung ob die Voraussetzungen des § 241 Abs 2 UGB erfüllt sind:
      - Liegt tatsächlich ein erheblicher Nachteil vor?
      - Ist die Nicht-Angabe verhältnismäßig?
- [ ] Dokumentation der Begründung im Prüfungsakt
- [ ] Ggf. Einholung einer schriftlichen Bestätigung der Geschäftsführung

### 3. Zahlenabstimmung
- [ ] Eigenkapital-Zahlen gegen Jahresabschlüsse der Tochtergesellschaften prüfen
- [ ] Ergebnis-Zahlen gegen Jahresabschlüsse der Tochtergesellschaften prüfen
- [ ] Prüfung ob die Jahresabschlüsse der Beteiligungen aus dem letzten
      abgeschlossenen Geschäftsjahr stammen

### 4. Formale Prüfung
- [ ] Sind Name UND Sitz (Stadt) für alle Beteiligungen angegeben?
- [ ] Sind die Prozentsätze korrekt (direkt vs. indirekt)?

### 5. Grenzfälle
- [ ] Digital Ventures GmbH: Warum werden Eigenkapital/Ergebnis nicht angegeben,
      obwohl keine Schutzklausel angewendet wird?
      → Bei < 20% keine Pflicht, aber Hinweis dass unter "sonstige Ausleihungen"
        ausgewiesen → prüfen ob korrekte Klassifizierung

### Ergebnis der manuellen Prüfung
[ ] Keine Beanstandungen
[ ] Hinweis im Management Letter
[ ] Nachtrag im Anhang erforderlich
[ ] Prüfungsvorbehalt

Geprüft von: __________________ Datum: ______________
"""

# =============================================================================
# RESULTING PROTOCOL EXCERPT
# =============================================================================

PROTOCOL_EXCERPT = """
### Anteilsbesitz (§ 238 Abs 1 Z 2 UGB)

**Status:** [TEILWEISE - LÜCKEN IDENTIFIZIERT]

**Begründung:** Beteiligungen identifiziert, aber Schutzklausel-Anwendung
bei Consulting Solutions AG erfordert manuelle Prüfung der Angemessenheit.

#### Automatisch identifizierte Beteiligungen

Anzahl erkannt: **4** (davon 3 >= 20%)

| Gesellschaft              | Anteil | Eigenkapital | Ergebnis | Status    |
|---------------------------|--------|--------------|----------|-----------|
| Technik Service GmbH      | 100%   | 1.250.000    | 185.000  | ✓ ✓ ✓ ✓  |
| Logistik Partner KG       | 51%    | 320.000      | 42.500   | ✓ ✓ ✓ ✓  |
| Consulting Solutions AG   | 25%    | _-_          | _-_      | ✓ ✓ ? ? (§241) |
| Digital Ventures GmbH     | 15%    | _-_          | _-_      | ✓ ✓ ✗ ✗  |

_Legende: ✓ = erkannt, ✗ = nicht gefunden, ? = nicht beurteilbar, (§241) = Schutzklausel_

#### Identifizierte Lücken

- **Digital Ventures GmbH**: Eigenkapital, Ergebnis
  _Hinweis: 15% < 20% - keine Angabepflicht nach § 238 Abs 1 Z 2_

#### Erforderliche Prüfungshandlungen

1. [ ] Vollständigkeit der Beteiligungsliste gegen Buchhaltung prüfen
2. [ ] Angemessenheit der Schutzklausel bei Consulting Solutions AG prüfen
3. [ ] Richtigkeit der angegebenen Eigenkapital/Ergebnis-Werte verifizieren
4. [ ] Aktualität der Zahlen prüfen (letztes verfügbares Geschäftsjahr)

#### Automatisch nicht prüfbar

- Vollständigkeit der Beteiligungsliste nicht prüfbar
- Richtigkeit der Zahlen nicht verifiziert
- Angemessenheit der Schutzklausel-Anwendung nicht beurteilbar

---

**Prüferkommentar:**
_[Platzhalter für manuelle Beurteilung]_

**Geprüft von:** _______________ **Datum:** _______________
"""

# =============================================================================
# INTEGRATION INTO EXISTING ARCHITECTURE
# =============================================================================

INTEGRATION_NOTES = """
## Integration in bestehende Architektur

### 1. Knowledge Layer (anhangspruefer/knowledge/)
- Neues Modul: rules/anteilsbesitz_238_z2.py
- Enthält: RULE_SCHEMA, REQUIRED_ELEMENTS, ACCEPTABLE_VARIANTS
- Keine Änderung an bestehenden Dateien erforderlich

### 2. Review Logic (anhangspruefer/review/)
- Neues Modul: rules/anteilsbesitz_evaluator.py
- Funktion: evaluate_anteilsbesitz(document) -> RuleEvaluationResult
- Aufruf durch ReviewEngine bei entsprechendem Checklist-Item

### 3. Reporting Layer (anhangspruefer/reporting/)
- Neues Modul: rules/anteilsbesitz_formatter.py
- Funktion: format_anteilsbesitz_finding(result) -> str
- Integration in MarkdownReportGenerator

### 4. Checklist-Integration
- Checklist-Item "chk_xxx" für § 238 Abs 1 Z 2 anlegen
- In ChecklistLoader: Mapping von item_id zu rule_evaluator

### 5. CLI/GUI
- Keine Änderung erforderlich
- Automatische Integration über Checklist-Mechanismus
"""
