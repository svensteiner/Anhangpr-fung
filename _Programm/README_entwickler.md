# Anhangsprüfer

**Prüfungsunterstützung für den Anhang zum Jahresabschluss nach UGB**

> **WICHTIGER HINWEIS:** Dieses Tool dient ausschließlich der Prüfungsunterstützung
> und ersetzt NICHT die fachliche Beurteilung durch einen qualifizierten
> Wirtschaftsprüfer. Alle automatisch generierten Bewertungen sind vorläufig
> und erfordern manuelle Validierung.

---

## Schnellstart

Das Programm bleibt auf dem Server. Keine EXE kopieren.

1. Einmalig: `Installieren.bat` (legt eine Desktop-Verknüpfung an)
2. Immer: Desktop-Verknüpfung oder `Starten.bat`
3. Browser öffnet sich. Mandant eintragen, Modus wählen.

KI nur über `_Gemeinsam/llp_ai` (Microsoft Foundry). Ohne Foundry: Heuristik.

---

## Überblick

Der Anhangsprüfer ist ein lokales Python-Tool zur strukturierten Überprüfung
von Anhängen zum Jahresabschluss österreichischer Unternehmen nach dem
Unternehmensgesetzbuch (UGB), insbesondere §§ 236-243.

### Funktionen

- **Browser-Oberfläche**: Start über `Starten.bat`. `run_gui.py` / `gui.py` sind abgeschaltet.
- **Dokumentenanalyse**: Parsen von Anhang-PDFs und Extraktion von Textinhalten
- **Anforderungsabgleich**: Automatischer Abgleich mit UGB-Angabepflichten
- **Compliance-Bewertung**: Vorläufige Statusbestimmung pro Prüfungspunkt
- **Evidenz-Extraktion**: Identifikation relevanter Textstellen als Nachweise
- **Protokollerstellung**: Strukturierte Prüfungsprotokolle (Markdown/HTML)

## Installation

### Start für Anwender

`Starten.bat` im Programmordner (oder die Desktop-Verknüpfung).

### Python-Installation (Entwicklung)

Voraussetzungen:
- Python 3.11 oder höher
- Windows-Betriebssystem (getestet)

```bash
# In das Projektverzeichnis wechseln
cd C:\Users\SvenSteiner\Anhangsprüfung\_Programm

# Paket samt Abhängigkeiten installieren (empfohlen)
pip install -e .

# Optional: alle Extras (inkl. RTF-Support, Tests)
pip install -e ".[all,dev]"

# Anwender: Starten.bat  (run_gui.py ist abgeschaltet)
python app.py
```

**Pflicht-Abhängigkeiten** (siehe `pyproject.toml`):
`pypdf`, `pdfplumber`, `openpyxl`, `flask`, `python-docx`

## Verwendung

### Browser (Anwender)

`Starten.bat` oder die Desktop-Verknüpfung. Modus 3: zuerst Gesellschaft
bestätigen, dann Knopf **Teil 2: Rest prüfen**. Kein stilles „unbekannt“.

```bash
python app.py
```

### Kommandozeile

`run_review.py` ist abgeschaltet (alte Keyword-Engine). Anwender: `Starten.bat`.

### CLI-Befehle

```bash
# Anhang prüfen (Gesellschaft ist Pflicht)
python -m anhangspruefer review "Anhang 2024.pdf" --rechtsform gmbh --groessenklasse klein -o checkliste.xlsx

# Standard-Checkliste erstellen
python -m anhangspruefer init -o meine_checkliste.json

# Checkliste aus PDF extrahieren (experimentell)
python -m anhangspruefer parse-checklist checkliste.pdf -o parsed.json
```

### Optionen

| Option | Beschreibung |
|--------|--------------|
| `-c, --checklist` | Pfad zur eigenen Checklisten-Datei (JSON) |
| `-u, --ugb-source` | Pfad zur UGB-Quelldatei |
| `-o, --output` | Ausgabepfad für das Protokoll |
| `--format` | Ausgabeformat: `markdown` (Standard) oder `html` |
| `-v, --verbose` | Ausführliche Ausgabe |

## Projektstruktur

```
Anhangsprüfer/
├── anhangspruefer/           # Hauptpaket
│   ├── __init__.py           # Paketinitialisierung, Disclaimer
│   ├── cli.py                # Kommandozeilenschnittstelle
│   ├── config.py             # Konfiguration und Konstanten
│   │
│   ├── parsers/              # Dokumentenparser
│   │   ├── base.py           # Abstrakte Basis-Klasse
│   │   ├── pdf_parser.py     # PDF-Extraktion
│   │   ├── rtf_parser.py     # RTF-Extraktion (UGB-Quelle)
│   │   └── section_detector.py # Abschnittserkennung
│   │
│   ├── knowledge/            # Wissensbasis
│   │   ├── ugb_requirements.py    # UGB-Anforderungen
│   │   ├── checklist_loader.py    # Checklisten-Verwaltung
│   │   └── requirement_matcher.py # Anforderungsabgleich
│   │
│   ├── review/               # Prüfungslogik
│   │   ├── engine.py         # Haupt-Engine
│   │   ├── evaluator.py      # Compliance-Bewertung
│   │   └── evidence.py       # Evidenz-Extraktion
│   │
│   ├── reporting/            # Berichtserstellung
│   │   ├── markdown_report.py     # Markdown-Generator
│   │   └── protocol_formatter.py  # Formatierung
│   │
│   ├── models/               # Datenmodelle
│   │   ├── document.py       # Dokumentenmodell
│   │   ├── checklist.py      # Checklistenmodell
│   │   ├── finding.py        # Feststellungsmodell
│   │   └── enums.py          # Status-Enums
│   │
│   └── utils/                # Hilfsfunktionen
│       ├── text_processing.py # Textverarbeitung
│       └── logging_config.py  # Logging
│
├── data/                     # Datendateien
├── output/                   # Ausgabeverzeichnis
├── run_review.py             # Schnellstart-Skript
├── pyproject.toml            # Paketdefinition
└── DOMAIN_KNOWLEDGE_REQUIREMENTS.md  # Fachliche Erweiterungspunkte
```

## Ausgabeformat

Das generierte Prüfungsprotokoll enthält:

1. **Zusammenfassung** - Übersicht über alle Prüfungspunkte
2. **Statusverteilung** - Aggregierte Compliance-Statistik
3. **Detaillierte Feststellungen** - Pro Checklistenpunkt:
   - Status (ENTSPRICHT / TEILWEISE / NICHT ENTSPRECHEND / NICHT BEURTEILBAR)
   - UGB-Referenz
   - Identifizierte Nachweise (Zitate)
   - Technische Begründung
   - Prüferkommentar-Platzhalter
4. **Kritische Feststellungen** - Hervorhebung problematischer Punkte
5. **Anhang** - Bereiche für fachliche Expertise

## Status-Definitionen

| Status | Symbol | Bedeutung |
|--------|--------|-----------|
| ENTSPRICHT | [OK] | Angaben scheinen vorhanden (vorläufig) |
| TEILWEISE ENTSPRECHEND | [TEIL] | Angaben möglicherweise unvollständig |
| NICHT ENTSPRECHEND | [FEHLT] | Keine entsprechenden Angaben gefunden |
| NICHT BEURTEILBAR | [?] | Automatische Beurteilung nicht möglich |
| NICHT ANWENDBAR | [N/A] | Nicht anwendbar auf diesen Abschluss |

## Anpassung und Erweiterung

### Checkliste anpassen

Erstellen Sie eine JSON-Datei mit Ihren Prüfungspunkten:

```json
{
  "name": "Meine Checkliste",
  "version": "2024",
  "items": [
    {
      "item_id": "custom_001",
      "category": "Allgemein",
      "description": "Prüfungsfrage...",
      "ugb_references": ["§ 236"],
      "search_keywords": ["Schlüsselwort1", "Schlüsselwort2"],
      "is_mandatory": true
    }
  ]
}
```

### Weitere Anpassungen

Siehe `DOMAIN_KNOWLEDGE_REQUIREMENTS.md` für eine vollständige Liste der
Bereiche, die fachspezifische Anpassung erfordern.

## Einschränkungen

- **OCR lokal**: Bild-Scans ohne Textebene werden mit EasyOCR erkannt (optional, vollständig lokal, Cache als `*.ocr.json` neben der Datei)
- **Heuristische Erkennung**: Abschnittserkennung kann bei ungewöhnlichen
  Layouts versagen
- **Keine semantische Analyse**: Inhaltliche Korrektheit wird nicht geprüft
- **Deutschsprachig**: Nur für deutsche/österreichische Dokumente optimiert

## Lizenz

Interner Gebrauch / Proprietär

## Haftungsausschluss

**DIESES TOOL FÜHRT KEINE UGB-KONFORME PRÜFUNG DURCH.**

Alle automatisch generierten Bewertungen und Feststellungen sind als vorläufige
Arbeitsergebnisse zu verstehen, die einer manuellen Überprüfung und Validierung
durch den verantwortlichen Prüfer bedürfen.

Die endgültige rechtliche und fachliche Beurteilung obliegt ausschließlich
dem Abschlussprüfer.
