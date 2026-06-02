# Verzeichnisstruktur

Diese Datei dokumentiert, was wohin gehört. Bitte halten, nicht zumüllen.

## Top-Level

| Pfad | Zweck |
|------|-------|
| `app.py` | **Kanonische** Web-App (Flask). Eine App, drei Modi: Vorjahresvergleich, Detailzahlenvergleich (Belegprüfung), UGB-Inhaltsprüfung. Plus Mandanten-Fortschrittsübersicht der 3 Stufen. |
| `Anhangspruefer.spec` | PyInstaller-Build-Definition für die eigenständige EXE (kein Python beim Anwender nötig). Bauen: `pyinstaller Anhangspruefer.spec --noconfirm`. |
| `dist/` | Gebaute EXE: `dist\Anhangspruefer.exe` (Doppelklick genügt). Wird per Git ignoriert (regenerierbar). |
| `Starten.bat` | Start für Entwickler (braucht Python). Anwender nutzen die EXE. |
| `Tests_starten.bat` | Führt die Pytest-Tests aus `_Programm/tests/` aus. |
| `ANLEITUNG.txt` | Anwender-Kurzanleitung. |
| `STRUKTUR.md` | Diese Datei. |
| `01_PDFs_hier_ablegen/` | **Inbox**: hier legen Anwender ihre Anhang-PDFs ab. Inhalt wird per Git ignoriert. |
| `Ergebnisse/` | **Outbox**: alle generierten Excel-Berichte und Markdown-Protokolle + Fortschritts-JSON. Inhalt wird per Git ignoriert. |
| `Fachliche Unterlagen/` | Tool-stützende Fachmaterialien: UGB-Gesetzestext, PwC-Anhangscheckliste, `Wissensbasis/` (Kommentare/Guidance), Domänen-Doku. **Nicht** einchecken (Urheberrecht Dritter). |
| `Accilium/` | Mandantendaten (Jahresabschluss, Prüfungsbericht). **VERTRAULICH — niemals einchecken oder pushen** (Verschwiegenheitspflicht). |
| `_Programm/` | Eigentliches Python-Paket + Tests + Entwicklerdoku. |
| `.gitignore` | Git-Ignore. Schließt **Mandantendaten, Beispiel-PDFs, fachliche Fremdunterlagen, Auswertungen** strikt aus. |

## `_Programm/`

| Pfad | Zweck |
|------|-------|
| `anhangspruefer/` | Hauptpaket. Siehe Unterstruktur. |
| `pyproject.toml` | Paketdefinition, Dependencies. |
| `run_gui.py` / `run_review.py` | Entwickler-Einstiegspunkte. |
| `README_entwickler.md` | Entwicklerdoku. |
| `tests/` | Pytest-Tests (Smoke + Unit). |
| `README_entwickler.md` | Entwicklerdoku. |

> Hinweis: Die frühere `sources/`-Wissensbasis liegt jetzt unter `Fachliche Unterlagen/Wissensbasis/`. Der EXE-Build wird über die **Top-Level** `Anhangspruefer.spec` gemacht (die alten `_Programm/build_exe.bat`/`anhangspruefer.spec`/`version_info.txt` wurden entfernt).

## `_Programm/anhangspruefer/`

| Modul | Zweck |
|-------|-------|
| `parsers/` | PDF/RTF-Parser, Section-Detector. |
| `models/` | Domänenmodelle (Document, Checklist, Finding, Enums). |
| `compliance/` | Regel-Engine, Evaluator, Evidence, Knowledge, Rules (Modus 3). |
| `vorjahresvergleich/` | Vergleich Anhang Vorjahr ↔ Berichtsjahr (Modus 1). |
| `pruefung/` | Detailzahlenvergleich (Belegprüfung): Extractor, Comparator, Excel-Report (Modus 2). |
| `gui.py` | Tkinter-GUI (alternativer Anwender-Einstieg). |
| `cli.py` | CLI-Einstiegspunkt. |
| `config.py` | Konfiguration / Konstanten. |

## Die 3 App-Modi (in `app.py`)

| Modus | Code-Modul | HTTP-Route | Output |
|-------|------------|------------|--------|
| 1 · Vorjahresvergleich | `vorjahresvergleich/` | `POST /compare` | `Ergebnisse/vergleich_*.xlsx` |
| 2 · Detailzahlenvergleich | `pruefung/` | `POST /pruefen` (+ `/detect_type`) | `Ergebnisse/pruefung_*.xlsx` |
| 3 · UGB-Inhaltsprüfung | `compliance/` | `POST /ugb_review` | `Ergebnisse/ugb_protokoll_*.md` |

Health-Endpoint: `GET /healthz` → JSON mit Mode-Liste.

## Konventionen

- **Caches und Tempdateien** (`__pycache__/`) werden ignoriert (siehe `.gitignore`).
- **Backups** mit Suffix `.bak`, `.bak_encoding`, … nicht commiten.
- **Output** gehört nach `Ergebnisse/`.
- **Neue Module** ins Paket `_Programm/anhangspruefer/`, *nicht* ins Root.
- **Temp-Dateien** der Web-App verwenden System-Temp (`/tmp` bzw. Windows-Temp), nicht den Projektordner.
