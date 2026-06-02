# Anhangsprüfer

**Prüfungsunterstützung für den Anhang zum Jahresabschluss nach UGB**

> **WICHTIGER HINWEIS:** Dieses Tool dient ausschließlich der Prüfungsunterstützung
> und ersetzt NICHT die fachliche Beurteilung durch einen qualifizierten
> Wirtschaftsprüfer. Alle automatisch generierten Bewertungen sind vorläufig
> und erfordern manuelle Validierung.

---

## Schnellstart für Anfänger (EXE-Version)

**Keine Installation erforderlich!**

1. Doppelklicken Sie auf `dist\Anhangspruefer.exe`
2. Klicken Sie auf "Durchsuchen..." und wählen Sie Ihre Anhang-PDF
3. Klicken Sie auf "▶ Prüfung starten"
4. Das Prüfungsprotokoll wird automatisch erstellt

Die EXE-Datei befindet sich im Ordner `dist\`.

---

## Überblick

Der Anhangsprüfer ist ein lokales Python-Tool zur strukturierten Überprüfung
von Anhängen zum Jahresabschluss österreichischer Unternehmen nach dem
Unternehmensgesetzbuch (UGB), insbesondere §§ 236-243.

### Funktionen

- **Benutzerfreundliche GUI**: Einfache Oberfläche für Anfänger
- **Dokumentenanalyse**: Parsen von Anhang-PDFs und Extraktion von Textinhalten
- **Anforderungsabgleich**: Automatischer Abgleich mit UGB-Angabepflichten
- **Compliance-Bewertung**: Vorläufige Statusbestimmung pro Prüfungspunkt
- **Evidenz-Extraktion**: Identifikation relevanter Textstellen als Nachweise
- **Protokollerstellung**: Strukturierte Prüfungsprotokolle (Markdown/HTML)

## Installation

### Option 1: EXE-Datei (empfohlen für Anfänger)

Keine Installation erforderlich. Starten Sie einfach:
```
dist\Anhangspruefer.exe
```

### Option 2: Python-Installation

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

# GUI starten
python run_gui.py
```

**Pflicht-Abhängigkeiten** (siehe `pyproject.toml`):
`pypdf`, `pdfplumber`, `openpyxl`, `flask`

## Verwendung

### GUI-Version (empfohlen)

Starten Sie die grafische Oberfläche:
```bash
# EXE-Version
dist\Anhangspruefer.exe

# Oder Python-Version
python run_gui.py
```

### Kommandozeile

```bash
# Prüfung mit Standardeinstellungen ausführen
python run_review.py
```

### CLI-Befehle

```bash
# Anhang prüfen
python -m anhangspruefer review "Anhang 2024.pdf" -o protokoll.md

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

- **Keine OCR**: Gescannte PDFs (Bilder) werden nicht unterstützt
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
