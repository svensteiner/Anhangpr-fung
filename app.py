"""
LLP Anhangsprüfer – Lokale Web-Oberfläche
==========================================
Eine App, drei Modi:

  1) Vorjahreszahlen-Vergleich
       Vergleicht die Vorjahreswerte im aktuellen Anhang mit den
       Berichtsjahreswerten im Vorjahres-Anhang.

  2) Belegprüfung (Detailzahlen)
       Vergleicht Angaben im Anhang mit hochgeladenen Detailunterlagen
       (Bankgarantien, Personalstand, Kontosalden …).

  3) UGB-Anhangsprüfung
       Prüft, ob die nach §§ 236-243 UGB erforderlichen Angaben im
       Anhang vorhanden sind, und erstellt ein strukturiertes Protokoll.

Vollständig lokal, keine externen Aufrufe.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file

# ---------------------------------------------------------------------------
# Programm- und Datenpfade
# ---------------------------------------------------------------------------
# Im EXE-Betrieb (PyInstaller) zeigt __file__ in ein temporäres Entpack-
# Verzeichnis. Für die Anwender-sichtbaren Ordner (Ergebnisse, Status) muss
# stattdessen der Ordner der EXE verwendet werden, damit die Ergebnisse
# verlässlich NEBEN dem Programm liegen – nicht im Temp.
if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).parent
else:
    HERE = Path(__file__).parent

# Das Paket `anhangspruefer` liegt im Entwicklungsbetrieb unter _Programm/;
# im EXE-Betrieb ist es fest mitgebündelt und braucht diesen Pfad nicht.
PROG_DIR = HERE / "_Programm"
if PROG_DIR.exists() and str(PROG_DIR) not in sys.path:
    sys.path.insert(0, str(PROG_DIR))

# Modus 1: Vorjahresvergleich
from anhangspruefer.vorjahresvergleich.comparator import compare_anhaenge
from anhangspruefer.vorjahresvergleich.excel_report import (
    generate_excel as write_vorjahr_excel,
)

# Modus 2: Belegprüfung
from anhangspruefer.pruefung.comparator import pruefen
from anhangspruefer.pruefung.excel_report import generate_excel as write_pruefung_excel
from anhangspruefer.pruefung.extractor import detect_type

# Dokumenten-Pipelines je Mandant (ein "Hirn", anstöpselbare Plugins)
from anhangspruefer.pipelines import (
    get_pipeline,
    available_pipelines,
    plugin_errors,
    register_plugins,
)

# Mindesttextprüfung: schützt alle drei Modi davor, aus einem Scan ohne
# Texterkennung ein leeres, aber vollständig formatiertes Arbeitspapier zu bauen.
from anhangspruefer.parsers.document_text import pruefe_textausbeute

# Modus 3: UGB-Anhangsprüfung
from anhangspruefer.compliance.engine import ReviewEngine
from anhangspruefer.compliance.reporting.markdown_report import MarkdownReportGenerator


# ---------------------------------------------------------------------------
# Flask-Setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

OUTPUT_DIR = HERE / "Ergebnisse"
OUTPUT_DIR.mkdir(exist_ok=True)
# WICHTIG: System-Temp verwenden, nicht HERE/_tmp_web — sonst Probleme mit
# OneDrive/Cowork-Mounts beim Aufräumen.
TMP_DIR = None  # tempfile fällt auf das System-Default zurück
TOOL_ZIP = HERE / "Anhangspruefer_Tool.zip"

# Modus 3 (UGB-Inhaltsprüfung): erweiterbares Prüfprogramm als Excel.
# Liegt im Fachordner NEBEN der EXE -> jederzeit vom Prüfer in Excel erweiterbar.
# Ist die Datei vorhanden, wird sie statt der Code-Standardliste verwendet.
UGB_FACHORDNER = HERE / "Fachliche Unterlagen" / "UGB-Inhaltsprüfung"


def _find_pruefprogramm():
    """Findet das UGB-Prüfprogramm – bevorzugt die Makro-Version (.xlsm)."""
    for name in ("UGB-Pruefprogramm.xlsm", "UGB-Pruefprogramm.xlsx"):
        p = UGB_FACHORDNER / name
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Mandanten-Plugins anstöpseln
# ---------------------------------------------------------------------------
# Ein Mandantenprofil verrät, WEN wir prüfen – es liegt daher nicht im
# Repository, sondern als Plugin neben dem Programm unter
# Klienten/<Mandant>/pipeline.py. Beim Start werden alle Plugins geladen.
KLIENTEN_DIR = HERE / "Klienten"
_PLUGIN_BEFUND = register_plugins(KLIENTEN_DIR)


# ---------------------------------------------------------------------------
# Mindesttextprüfung (alle drei Modi)
# ---------------------------------------------------------------------------
class LeereUnterlage(Exception):
    """Eine Unterlage trägt keinen lesbaren Text – der Lauf wird abgebrochen.

    Ohne diesen Abbruch liefe die Prüfung fehlerfrei durch und erzeugte ein
    vollständig formatiertes Arbeitspapier ohne inhaltliche Grundlage.
    """


def _neue_warnungen() -> list:
    """Warnliste für einen Lauf – bereits gefüllt mit Plugin-Ladefehlern.

    Ein Mandantenprofil, das nicht geladen werden konnte, muss BEI JEDEM Lauf
    sichtbar sein: der Lauf ist dann mit dem Standardprofil gefahren, was
    fachlich ein anderes Ergebnis bedeutet.
    """
    return [
        f"Mandantenprofil nicht geladen – dieser Lauf verwendet das "
        f"Standardprofil: {f}"
        for f in plugin_errors()
    ]


def _pruefe_lesbarkeit(pfade_mit_namen, warnungen: list) -> None:
    """Prüft je Unterlage, ob überhaupt Text darin steckt.

    Args:
        pfade_mit_namen: Paare (Pfad, Anzeigename für die Meldung).
        warnungen: Liste, in die Warnungen für textarme Unterlagen angehängt
            werden (der Lauf geht dann weiter).

    Raises:
        LeereUnterlage: sobald eine Unterlage praktisch keinen Text enthält.
    """
    for pfad, name in pfade_mit_namen:
        befund = pruefe_textausbeute(pfad, anzeigename=name)
        if befund is None:
            continue          # Format hier nicht lesbar -> Modus entscheidet wie bisher
        if befund.ist_leer:
            raise LeereUnterlage(befund.meldung)
        if befund.ist_textarm:
            warnungen.append(befund.meldung)


# ---------------------------------------------------------------------------
# Prüfungsfortschritt je Mandant (3-Stufen-Übersicht)
# ---------------------------------------------------------------------------
# Persistiert, welche der 3 Prüfungsstufen für einen Mandanten bereits
# gelaufen sind. Liegt als JSON neben den Ergebnissen, damit der Stand auch
# nach Neustart des Tools erhalten bleibt.
STATUS_FILE = OUTPUT_DIR / "_pruefungsfortschritt.json"
_status_lock = threading.Lock()

# Reihenfolge & Beschriftung der 3 Stufen (Single Source of Truth fürs Backend)
STAGES = ("vorjahr", "beleg", "ugb")


def _load_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_status(data: dict) -> None:
    STATUS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _record_stage(mandant: str, stage: str, filename: str, summary: dict) -> None:
    """Trägt einen erfolgreichen Prüflauf in die Fortschrittsübersicht ein."""
    mandant = (mandant or "").strip()
    if not mandant or stage not in STAGES:
        return
    with _status_lock:
        data = _load_status()
        entry = data.setdefault(mandant, {})
        entry[stage] = {
            "done": True,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "file": filename,
            "summary": summary,
        }
        _save_status(data)


# ---------------------------------------------------------------------------
# HTML-Template (eingebettet, keine externen Abhängigkeiten)
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLP · Anhangsprüfer</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --orange:   #E07A1E;
    --gold:     #C8900A;
    --maroon:   #7B1818;
    --maroon-dark: #5E1212;
    --bg:       #FDF8F3;
    --white:    #FFFFFF;
    --text:     #222222;
    --muted:    #666666;
    --border:   #E0D5C8;
    --success:  #2E7D32;
    --error:    #C62828;
    --shadow:   0 2px 12px rgba(0,0,0,0.08);
  }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }

  /* Header */
  header { background: var(--white); border-bottom: 1px solid var(--border); box-shadow: var(--shadow); padding: 0 40px; display: flex; align-items: center; height: 80px; gap: 24px; }
  .logo { display: flex; align-items: center; gap: 0; text-decoration: none; }
  .logo-circles { display: flex; }
  .lc { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 18px; color: #fff; margin-left: -8px; }
  .lc:first-child { margin-left: 0; }
  .c-o { background: var(--orange); } .c-g { background: var(--gold); } .c-m { background: var(--maroon); }
  .logo-text { margin-left: 14px; display: flex; flex-direction: column; line-height: 1.15; }
  .logo-text span { font-size: 9.5px; font-weight: 600; letter-spacing: 2.5px; text-transform: uppercase; color: var(--text); }
  .header-title { margin-left: auto; font-size: 14px; color: var(--muted); letter-spacing: .5px; }
  .header-back { margin-left: 16px; font-size: 13px; color: var(--maroon); text-decoration: none; padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; background: var(--white); }
  .header-back:hover { background: var(--bg); }
  .header-quit { margin-left: 10px; font-size: 13px; color: var(--error); text-decoration: none; padding: 6px 14px; border: 1px solid var(--error); border-radius: 6px; cursor: pointer; background: var(--white); }
  .header-quit:hover { background: var(--error); color: #fff; }
  .quit-screen { max-width: 540px; margin: 80px auto; text-align: center; background: var(--white); border: 2px solid var(--border); border-radius: 14px; padding: 48px 32px; box-shadow: var(--shadow); }
  .quit-screen h2 { font-size: 22px; margin: 0 0 12px; color: var(--maroon); }
  .quit-screen p { color: var(--muted); font-size: 15px; }

  /* Hero */
  .hero { background: linear-gradient(135deg, var(--maroon) 0%, #A52020 50%, var(--orange) 100%); color: #fff; padding: 48px 40px 44px; text-align: center; }
  .hero h1 { font-size: 28px; font-weight: 300; letter-spacing: 1px; margin-bottom: 10px; }
  .hero h1 strong { font-weight: 700; }
  .hero p { font-size: 15px; opacity: .85; max-width: 620px; margin: 0 auto; line-height: 1.6; }

  main { flex: 1; max-width: 900px; margin: 0 auto; padding: 40px 20px 60px; width: 100%; }

  /* Mode picker */
  .mode-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px; }
  @media (max-width: 760px) { .mode-grid { grid-template-columns: 1fr; } }
  .mode-card { background: var(--white); border: 2px solid var(--border); border-radius: 12px; padding: 28px 22px; text-align: center; cursor: pointer; transition: all .25s; box-shadow: var(--shadow); display: flex; flex-direction: column; align-items: center; gap: 10px; }
  .mode-card:hover { border-color: var(--orange); transform: translateY(-3px); box-shadow: 0 6px 20px rgba(224,122,30,0.15); }
  .mode-icon { font-size: 42px; }
  .mode-title { font-size: 16px; font-weight: 700; color: var(--maroon); }
  .mode-desc { font-size: 13px; color: var(--muted); line-height: 1.5; }

  /* Steps */
  .steps { display: flex; gap: 0; margin-bottom: 32px; position: relative; }
  .steps::before { content: ''; position: absolute; top: 20px; left: 60px; right: 60px; height: 2px; background: var(--border); z-index: 0; }
  .step { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px; position: relative; z-index: 1; }
  .step-num { width: 40px; height: 40px; border-radius: 50%; background: var(--border); color: var(--muted); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 16px; transition: all .3s; }
  .step.active .step-num { background: var(--orange); color: #fff; }
  .step.done   .step-num { background: var(--success); color: #fff; }
  .step-label { font-size: 11px; color: var(--muted); text-align: center; font-weight: 500; letter-spacing: .3px; }
  .step.active .step-label { color: var(--orange); font-weight: 600; }
  .step.done   .step-label { color: var(--success); }

  /* Cards */
  .card { background: var(--white); border: 1px solid var(--border); border-radius: 10px; padding: 32px; margin-bottom: 24px; box-shadow: var(--shadow); }
  .card h2 { font-size: 17px; font-weight: 600; color: var(--maroon); margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid var(--border); display: flex; align-items: center; gap: 10px; }
  .card h2 .num { width: 28px; height: 28px; background: var(--maroon); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0; }

  /* Upload areas */
  .upload-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 640px) { .upload-grid { grid-template-columns: 1fr; } }
  .upload-area { border: 2px dashed var(--border); border-radius: 8px; padding: 28px 20px; text-align: center; cursor: pointer; transition: all .25s; position: relative; background: var(--bg); }
  .upload-area:hover, .upload-area.dragover { border-color: var(--orange); background: #FFF5EC; }
  .upload-area.has-file { border-color: var(--success); background: #F1FBF2; }
  .upload-area input { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }
  .upload-icon { font-size: 36px; margin-bottom: 10px; }
  .upload-label { font-size: 12px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--maroon); margin-bottom: 6px; }
  .upload-hint { font-size: 12px; color: var(--muted); }
  .upload-filename { font-size: 12px; color: var(--success); font-weight: 600; word-break: break-all; display: none; margin-top: 6px; }
  .upload-area.has-file .upload-filename { display: block; }
  .upload-area.has-file .upload-hint { display: none; }

  /* Belege */
  .belege-zone { border: 2px dashed var(--border); border-radius: 8px; padding: 24px 20px; min-height: 120px; transition: all .25s; background: var(--bg); position: relative; }
  .belege-zone.dragover { border-color: var(--orange); background: #FFF5EC; }
  .belege-zone input { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%; }
  .belege-empty { text-align: center; color: var(--muted); font-size: 13px; padding: 16px 0; pointer-events: none; }
  .beleg-list { list-style: none; display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
  .beleg-item { display: flex; align-items: center; gap: 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; font-size: 13px; }
  .beleg-badge { font-size: 10px; font-weight: 700; letter-spacing: .5px; padding: 2px 8px; border-radius: 20px; text-transform: uppercase; }
  .badge-bank { background: #E3F2FD; color: #1565C0; }
  .badge-hr   { background: #E8F5E9; color: #2E7D32; }
  .badge-unk  { background: #F5F5F5; color: #888; }
  .beleg-name { flex: 1; word-break: break-all; }
  .beleg-remove { cursor: pointer; color: var(--error); font-size: 16px; font-weight: 700; padding: 0 4px; }
  .belege-add-btn { display: inline-block; margin-top: 12px; padding: 8px 18px; background: var(--white); border: 1.5px solid var(--orange); color: var(--orange); border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .2s; }
  .belege-add-btn:hover { background: var(--orange); color: #fff; }

  /* Buttons */
  .btn-run { display: block; width: 100%; padding: 16px; background: var(--maroon); color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; letter-spacing: .5px; cursor: pointer; transition: background .2s; margin-top: 18px; }
  .btn-run:hover:not(:disabled) { background: var(--maroon-dark); }
  .btn-run:disabled { opacity: .5; cursor: not-allowed; }

  .btn-download { display: inline-flex; align-items: center; gap: 10px; padding: 14px 28px; background: var(--orange); color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; text-decoration: none; transition: background .2s; margin-top: 12px; }
  .btn-download:hover { background: var(--gold); }

  /* Progress / Result / Error */
  .progress-bar-wrap { background: var(--border); border-radius: 100px; height: 8px; overflow: hidden; margin: 16px 0 8px; }
  .progress-bar { height: 100%; background: linear-gradient(90deg, var(--maroon), var(--orange)); border-radius: 100px; width: 0%; transition: width .4s ease; }
  .progress-text { font-size: 13px; color: var(--muted); text-align: center; }

  .result-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; margin-bottom: 14px; }
  .stat-box { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
  .stat-val { font-size: 32px; font-weight: 700; line-height: 1; margin-bottom: 4px; }
  .stat-lbl { font-size: 11px; color: var(--muted); letter-spacing: .5px; text-transform: uppercase; }
  .stat-ok    .stat-val { color: var(--success); }
  .stat-abw   .stat-val { color: var(--error); }
  .stat-total .stat-val { color: var(--maroon); }
  .stat-text  .stat-val { color: var(--orange); }
  .stat-fehlt .stat-val { color: var(--error); }
  .result-note { font-size: 13px; color: var(--muted); background: var(--bg); border-left: 3px solid var(--orange); padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; }
  .result-saved { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
  /* Warnbox: das Ergebnis liegt vor, ist aber nur eingeschränkt verlässlich
     (z.B. textarmes PDF, nicht eingelesene Detailunterlage). */
  .result-warn { font-size: 13px; color: #7A4200; background: #FFF8E6; border: 1px solid #F0D08A;
                 border-left: 3px solid var(--orange); border-radius: 4px; padding: 10px 14px; margin-bottom: 16px; }
  .result-warn strong { display: block; margin-bottom: 6px; }
  .result-warn ul { margin: 0; padding-left: 18px; }
  .result-warn li { margin: 4px 0; line-height: 1.45; }

  .error-box { background: #FFF5F5; border: 1px solid #FFCDD2; border-radius: 8px; padding: 20px; color: var(--error); font-size: 14px; line-height: 1.5; }

  .disclaimer { background: #FFFBF0; border: 1px solid #F0E0A0; border-radius: 8px; padding: 14px 18px; font-size: 12px; color: #7A6010; line-height: 1.5; margin-top: 16px; }
  footer { background: var(--maroon); color: rgba(255,255,255,.7); text-align: center; padding: 18px; font-size: 12px; letter-spacing: .5px; }
  footer strong { color: #fff; }

  /* --- Mandant & 3-Stufen-Fortschritt --- */
  .mandant-card { background: var(--white); border: 2px solid var(--border); border-radius: 12px; padding: 22px 24px; box-shadow: var(--shadow); margin-bottom: 26px; }
  .mandant-card h2 { font-size: 17px; margin: 0 0 14px; display: flex; align-items: center; gap: 10px; }
  .mandant-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
  .mandant-row label { font-weight: 600; font-size: 14px; color: var(--muted); }
  .mandant-input { flex: 1; min-width: 220px; padding: 11px 14px; border: 2px solid var(--border); border-radius: 8px; font-size: 15px; }
  .mandant-input:focus { outline: none; border-color: var(--orange); }
  .fortschritt { width: 100%; border-collapse: collapse; margin-top: 16px; }
  .fortschritt td { padding: 11px 10px; border-top: 1px solid var(--border); vertical-align: middle; }
  .fortschritt tr.clickable { cursor: pointer; }
  .fortschritt tr.clickable:hover td { background: #fff7f0; }
  .fs-stage { font-weight: 600; font-size: 14px; }
  .fs-sub   { font-size: 12px; color: var(--muted); }
  .fs-state { text-align: right; white-space: nowrap; font-size: 13px; }
  .fs-badge { display: inline-block; padding: 3px 11px; border-radius: 20px; font-size: 12px; font-weight: 700; }
  .fs-done { background: #e6f4ea; color: #1e7e34; }
  .fs-open { background: #f1f1f1; color: #888; }
  .fs-date { display: block; font-size: 11px; color: var(--muted); margin-top: 3px; font-weight: 400; }
  .fs-hint { font-size: 13px; color: var(--muted); margin-top: 12px; }
  .hidden { display: none !important; }
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-circles">
      <div class="lc c-o">L</div><div class="lc c-g">L</div><div class="lc c-m">P</div>
    </div>
    <div class="logo-text"><span>Wirtschaftsprüfung</span><span>Steuerberatung</span></div>
  </div>
  <div class="header-title">AI Tools · Prüfungsunterstützung</div>
  <button class="header-back hidden" id="btn-back" onclick="showModePicker()">← Modus wechseln</button>
  <button class="header-quit" id="btn-quit" onclick="quitApp()">⏻ Beenden</button>
</header>

<div class="hero">
  <h1><strong>Anhangsprüfer</strong></h1>
  <p id="hero-sub">Wählen Sie einen Prüfungsmodus. Vollständig lokal – kein Datenversand.</p>
</div>

<main>

  <!-- =========================================================== -->
  <!-- MODUS-AUSWAHL (Landing)                                     -->
  <!-- =========================================================== -->
  <section id="mode-picker">

    <!-- Mandant + 3-Stufen-Fortschritt -->
    <div class="mandant-card">
      <h2>🏢 Mandant &amp; Prüfungsfortschritt</h2>
      <div class="mandant-row">
        <label for="mandant-input">Mandant:</label>
        <input type="text" id="mandant-input" class="mandant-input" list="mandant-list"
               placeholder="Mandantenname eingeben oder auswählen…" oninput="onMandantChange()">
        <datalist id="mandant-list"></datalist>
      </div>
      <table class="fortschritt" id="fortschritt-table"><tbody>
        <tr class="clickable" onclick="pickMode('vorjahr')">
          <td><div class="fs-stage">Stufe 1 · Vorjahresvergleich</div><div class="fs-sub">gegen Vorjahres-Anhang</div></td>
          <td class="fs-state" id="fs-vorjahr"></td>
        </tr>
        <tr class="clickable" onclick="pickMode('beleg')">
          <td><div class="fs-stage">Stufe 2 · Detailprüfung</div><div class="fs-sub">gegen Detailbelege (Bank, Personal …)</div></td>
          <td class="fs-state" id="fs-beleg"></td>
        </tr>
        <tr class="clickable" onclick="pickMode('ugb')">
          <td><div class="fs-stage">Stufe 3 · UGB-Inhaltsprüfung</div><div class="fs-sub">gegen §§ 236-243 UGB</div></td>
          <td class="fs-state" id="fs-ugb"></td>
        </tr>
      </tbody></table>
      <div class="fs-hint" id="fs-hint">Geben Sie einen Mandanten ein, um den Fortschritt der 3 Prüfungsstufen zu sehen.</div>
    </div>

    <div class="mode-grid">
      <div class="mode-card" onclick="pickMode('vorjahr')">
        <div class="mode-icon">📊</div>
        <div class="mode-title">Vorjahresvergleich</div>
        <div class="mode-desc">Vergleicht die im aktuellen Anhang ausgewiesenen Vorjahreswerte mit dem Vorjahres-Anhang.</div>
      </div>
      <div class="mode-card" onclick="pickMode('beleg')">
        <div class="mode-icon">📑</div>
        <div class="mode-title">Detailprüfung</div>
        <div class="mode-desc">Vergleicht Angaben im Anhang mit hochgeladenen Detailunterlagen (Bank, Personal …).</div>
      </div>
      <div class="mode-card" onclick="pickMode('ugb')">
        <div class="mode-icon">⚖️</div>
        <div class="mode-title">UGB Inhaltsprüfung</div>
        <div class="mode-desc">Prüft, ob die nach §§ 236-243 UGB erforderlichen Angaben im Anhang enthalten sind.</div>
      </div>
    </div>
    <div class="disclaimer">
      ⚠ <strong>Haftungsausschluss:</strong> Dieses Tool dient ausschließlich der Prüfungsunterstützung und ersetzt nicht die fachliche Beurteilung durch einen qualifizierten Wirtschaftsprüfer. Alle Ergebnisse sind manuell zu validieren.
    </div>
  </section>

  <!-- =========================================================== -->
  <!-- MODUS 1 — VORJAHRESVERGLEICH                                -->
  <!-- =========================================================== -->
  <section id="mode-vorjahr" class="hidden">
    <div class="steps">
      <div class="step active" id="vj-step1"><div class="step-num">1</div><div class="step-label">Dateien auswählen</div></div>
      <div class="step"        id="vj-step2"><div class="step-num">2</div><div class="step-label">Vergleich läuft</div></div>
      <div class="step"        id="vj-step3"><div class="step-num">3</div><div class="step-label">Ergebnis laden</div></div>
    </div>
    <div class="card" id="vj-upload">
      <h2><span class="num">1</span>Anhänge hochladen (PDF oder Word)</h2>
      <div class="upload-grid">
        <div class="upload-area" id="vj-area-current"
             ondragover="dragOn(event,'vj-area-current')" ondragleave="dragOff('vj-area-current')"
             ondrop="dropPdf(event,'vj-area-current','vj-file-current','vjCurrent','vj-name-current')">
          <input type="file" id="vj-file-current" accept=".pdf,.docx" onchange="vjSelect('current')">
          <div class="upload-icon">📄</div>
          <div class="upload-label">Aktueller Anhang</div>
          <div class="upload-hint">z.B. Anhang 2025 · PDF oder Word</div>
          <div class="upload-filename" id="vj-name-current"></div>
        </div>
        <div class="upload-area" id="vj-area-prior"
             ondragover="dragOn(event,'vj-area-prior')" ondragleave="dragOff('vj-area-prior')"
             ondrop="dropPdf(event,'vj-area-prior','vj-file-prior','vjPrior','vj-name-prior')">
          <input type="file" id="vj-file-prior" accept=".pdf,.docx" onchange="vjSelect('prior')">
          <div class="upload-icon">📂</div>
          <div class="upload-label">Vorjahres-Anhang</div>
          <div class="upload-hint">z.B. Anhang 2024 · PDF oder Word</div>
          <div class="upload-filename" id="vj-name-prior"></div>
        </div>
      </div>
      <button class="btn-run" id="vj-btn" disabled onclick="vjRun()">▶ Vergleich starten</button>
    </div>
    <div class="card hidden" id="vj-progress">
      <h2><span class="num">2</span>Vergleich läuft…</h2>
      <div class="progress-bar-wrap"><div class="progress-bar" id="vj-bar"></div></div>
      <div class="progress-text" id="vj-text">PDFs werden eingelesen…</div>
    </div>
    <div class="card hidden" id="vj-error">
      <h2><span class="num">✕</span>Fehler</h2>
      <div class="error-box" id="vj-err-text"></div>
    </div>
    <div class="card hidden" id="vj-result">
      <h2><span class="num">3</span>Ergebnis</h2>
      <div class="result-stats">
        <div class="stat-box stat-ok"><div class="stat-val" id="vj-ok">—</div><div class="stat-lbl">Übereinstimmend</div></div>
        <div class="stat-box stat-abw"><div class="stat-val" id="vj-abw">—</div><div class="stat-lbl">Abweichungen</div></div>
        <div class="stat-box stat-total"><div class="stat-val" id="vj-tot">—</div><div class="stat-lbl">Geprüfte Posten</div></div>
        <div class="stat-box stat-fehlt"><div class="stat-val" id="vj-textfehlt">—</div><div class="stat-lbl">Fehlende Textteile</div></div>
        <div class="stat-box stat-text"><div class="stat-val" id="vj-textneu">—</div><div class="stat-lbl">Neue Textteile</div></div>
      </div>
      <div class="result-note">Zwei Bereiche im Bericht: <strong>Zahlenvergleich</strong> (Vorjahreszahlen ↔ Vorjahresbericht) und <strong>Textvergleich</strong> (Absätze aktuell ↔ Vorjahr, Vollständigkeit — Blatt „Textvergleich").</div>
      <div class="result-warn hidden" id="vj-warn"></div>
      <div class="result-saved" id="vj-saved"></div>
      <button class="btn-download" id="vj-dl" onclick="openResults()">📂 Ergebnis-Ordner öffnen</button>
    </div>
  </section>

  <!-- =========================================================== -->
  <!-- MODUS 2 — BELEGPRÜFUNG                                      -->
  <!-- =========================================================== -->
  <section id="mode-beleg" class="hidden">
    <div class="steps">
      <div class="step active" id="bg-step1"><div class="step-num">1</div><div class="step-label">Dateien auswählen</div></div>
      <div class="step"        id="bg-step2"><div class="step-num">2</div><div class="step-label">Prüfung läuft</div></div>
      <div class="step"        id="bg-step3"><div class="step-num">3</div><div class="step-label">Ergebnis laden</div></div>
    </div>
    <div class="card" id="bg-upload">
      <h2><span class="num">1</span>Anhang auswählen (PDF)</h2>
      <div class="upload-area" id="bg-area-anhang"
           ondragover="dragOn(event,'bg-area-anhang')" ondragleave="dragOff('bg-area-anhang')"
           ondrop="dropPdf(event,'bg-area-anhang','bg-file-anhang','bgAnhang','bg-name-anhang')">
        <input type="file" id="bg-file-anhang" accept=".pdf" onchange="bgAnhangSelect()">
        <div class="upload-icon">📄</div>
        <div class="upload-label">Anhang zum Jahresabschluss</div>
        <div class="upload-hint">z.B. Anhang 2025</div>
        <div class="upload-filename" id="bg-name-anhang"></div>
      </div>

      <h2 style="margin-top:28px"><span class="num">2</span>Detailunterlagen hinzufügen (PDF / Excel)</h2>
      <div class="belege-zone" id="bg-belege-zone"
           ondragover="dragOn(event,'bg-belege-zone')" ondragleave="dragOff('bg-belege-zone')"
           ondrop="bgBelegeDrop(event)">
        <input type="file" id="bg-belege-input" accept=".pdf,.xlsx" multiple onchange="bgBelegeAdded(this.files)">
        <div class="belege-empty" id="bg-belege-empty">📂 Detailunterlagen hier ablegen<br><small>Bankgarantien, Personalstand, Kontosalden …</small></div>
        <ul class="beleg-list" id="bg-list"></ul>
      </div>
      <button class="belege-add-btn" onclick="document.getElementById('bg-belege-input').click()">+ Dateien hinzufügen</button>

      <button class="btn-run" id="bg-btn" disabled onclick="bgRun()">▶ Prüfung starten</button>
    </div>
    <div class="card hidden" id="bg-progress">
      <h2><span class="num">2</span>Prüfung läuft…</h2>
      <div class="progress-bar-wrap"><div class="progress-bar" id="bg-bar"></div></div>
      <div class="progress-text" id="bg-text">Dateien werden eingelesen…</div>
    </div>
    <div class="card hidden" id="bg-error">
      <h2><span class="num">✕</span>Fehler</h2>
      <div class="error-box" id="bg-err-text"></div>
    </div>
    <div class="card hidden" id="bg-result">
      <h2><span class="num">3</span>Prüfungsergebnis</h2>
      <div class="result-stats">
        <div class="stat-box stat-ok"><div class="stat-val" id="bg-ok">—</div><div class="stat-lbl">Übereinstimmend</div></div>
        <div class="stat-box stat-abw"><div class="stat-val" id="bg-abw">—</div><div class="stat-lbl">Abweichungen</div></div>
        <div class="stat-box stat-total"><div class="stat-val" id="bg-tot">—</div><div class="stat-lbl">Geprüfte Positionen</div></div>
      </div>
      <div id="bg-erkannt" style="font-size:13px;color:var(--muted);margin-bottom:12px"></div>
      <div class="result-warn hidden" id="bg-warn"></div>
      <div class="result-saved" id="bg-saved"></div>
      <button class="btn-download" id="bg-dl" onclick="openResults()">📂 Ergebnis-Ordner öffnen</button>
    </div>
  </section>

  <!-- =========================================================== -->
  <!-- MODUS 3 — UGB-INHALTSPRÜFUNG                                -->
  <!-- =========================================================== -->
  <section id="mode-ugb" class="hidden">
    <div class="steps">
      <div class="step active" id="ug-step1"><div class="step-num">1</div><div class="step-label">Anhang auswählen</div></div>
      <div class="step"        id="ug-step2"><div class="step-num">2</div><div class="step-label">Prüfung läuft</div></div>
      <div class="step"        id="ug-step3"><div class="step-num">3</div><div class="step-label">Protokoll laden</div></div>
    </div>
    <div class="card" id="ug-upload">
      <h2><span class="num">1</span>Anhang hochladen (PDF)</h2>
      <div class="upload-area" id="ug-area"
           ondragover="dragOn(event,'ug-area')" ondragleave="dragOff('ug-area')"
           ondrop="dropPdf(event,'ug-area','ug-file','ugFile','ug-name')">
        <input type="file" id="ug-file" accept=".pdf" onchange="ugSelect()">
        <div class="upload-icon">⚖️</div>
        <div class="upload-label">Anhang zum Jahresabschluss</div>
        <div class="upload-hint">wird gegen §§ 236-243 UGB geprüft</div>
        <div class="upload-filename" id="ug-name"></div>
      </div>
      <div class="mandant-row">
        <label for="ug-rechtsform">Rechtsform:</label>
        <select id="ug-rechtsform" class="mandant-input" style="flex:0 0 200px;">
          <option value="unbekannt">unbekannt</option>
          <option value="gmbh">GmbH</option>
          <option value="ag">AG</option>
        </select>
        <label for="ug-groessenklasse">Größenklasse § 221 UGB:</label>
        <select id="ug-groessenklasse" class="mandant-input" style="flex:0 0 200px;">
          <option value="unbekannt">unbekannt</option>
          <option value="klein">klein</option>
          <option value="mittel">mittel</option>
          <option value="gross">groß</option>
        </select>
      </div>
      <div class="result-note">„unbekannt" bedeutet: größenabhängige Erleichterungen werden NICHT gefiltert (jeder Punkt gilt als möglicherweise relevant).</div>
      <button class="btn-run" id="ug-btn" disabled onclick="ugRun()">▶ Inhaltsprüfung starten</button>
    </div>
    <div class="card hidden" id="ug-progress">
      <h2><span class="num">2</span>Prüfung läuft…</h2>
      <div class="progress-bar-wrap"><div class="progress-bar" id="ug-bar"></div></div>
      <div class="progress-text" id="ug-text">Anhang wird eingelesen…</div>
    </div>
    <div class="card hidden" id="ug-error">
      <h2><span class="num">✕</span>Fehler</h2>
      <div class="error-box" id="ug-err-text"></div>
    </div>
    <div class="card hidden" id="ug-result">
      <h2><span class="num">3</span>Prüfungsprotokoll</h2>
      <div class="result-stats">
        <div class="stat-box stat-text"><div class="stat-val" id="ug-bestaetigen">—</div><div class="stat-lbl">Zu bestätigen (Angabe gefunden)</div></div>
        <div class="stat-box stat-abw"><div class="stat-val" id="ug-keinhinweis">—</div><div class="stat-lbl">Kein Hinweis gefunden</div></div>
        <div class="stat-box stat-fehlt"><div class="stat-val" id="ug-fehl">—</div><div class="stat-lbl">Fehlt</div></div>
        <div class="stat-box stat-total"><div class="stat-val" id="ug-na">—</div><div class="stat-lbl">n. a.</div></div>
      </div>
      <div class="result-warn hidden" id="ug-warn"></div>
      <div class="result-saved" id="ug-saved"></div>
      <button class="btn-download" id="ug-dl" onclick="openResults()">📂 Ergebnis-Ordner öffnen</button>
    </div>
  </section>

</main>

<footer>
  <strong>LLP</strong> · Anhangsprüfer · Lokale Prüfungsunterstützung · Kein Datenversand
</footer>

<script>
/* ===================================================================
   GEMEINSAME HILFSFUNKTIONEN
   =================================================================== */
function show(id)  { document.getElementById(id).classList.remove('hidden'); }
function hide(id)  { document.getElementById(id).classList.add('hidden'); }
function setStep(prefix, n) {
  for (let i=1; i<=3; i++) {
    const el = document.getElementById(prefix + '-step' + i);
    if (!el) continue;
    el.classList.remove('active','done');
    if (i < n) el.classList.add('done');
    if (i === n) el.classList.add('active');
  }
}
function dragOn(e, id) { e.preventDefault(); document.getElementById(id).classList.add('dragover'); }
function dragOff(id)   { document.getElementById(id).classList.remove('dragover'); }

function dropPdf(e, areaId, inputId, varName, nameId) {
  e.preventDefault();
  document.getElementById(areaId).classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (!f) return;
  const dt = new DataTransfer(); dt.items.add(f);
  document.getElementById(inputId).files = dt.files;
  document.getElementById(inputId).dispatchEvent(new Event('change'));
}

function pickMode(m) {
  hide('mode-picker');
  document.getElementById('btn-back').classList.remove('hidden');
  if (m === 'vorjahr') { show('mode-vorjahr'); document.getElementById('hero-sub').textContent = 'Vergleich der Vorjahreszahlen mit dem Vorjahres-Anhang.'; }
  if (m === 'beleg')   { show('mode-beleg');   document.getElementById('hero-sub').textContent = 'Vergleich der Anhang-Werte mit hochgeladenen Detailunterlagen.'; }
  if (m === 'ugb')     { show('mode-ugb');     document.getElementById('hero-sub').textContent = 'Inhaltliche Prüfung gegen §§ 236-243 UGB.'; }
}
function showModePicker() {
  hide('mode-vorjahr'); hide('mode-beleg'); hide('mode-ugb');
  show('mode-picker');
  document.getElementById('btn-back').classList.add('hidden');
  document.getElementById('hero-sub').textContent = 'Wählen Sie einen Prüfungsmodus. Vollständig lokal – kein Datenversand.';
  loadStatus();
}

/* ===================================================================
   MANDANT & 3-STUFEN-FORTSCHRITT
   =================================================================== */
let currentMandant = '';
let statusData = {};
const STAGE_DEFS = [
  ['vorjahr', 'fs-vorjahr'],
  ['beleg',   'fs-beleg'],
  ['ugb',     'fs-ugb'],
];

async function loadStatus() {
  try {
    const r = await fetch('/status');
    const j = await r.json();
    statusData = j.mandanten || {};
  } catch (e) { statusData = {}; }
  const dl = document.getElementById('mandant-list');
  dl.innerHTML = Object.keys(statusData).sort()
    .map(m => '<option value="' + m.replace(/"/g, '&quot;') + '">').join('');
  renderFortschritt();
}

function onMandantChange() {
  currentMandant = document.getElementById('mandant-input').value.trim();
  try { localStorage.setItem('llp_mandant', currentMandant); } catch (e) {}
  renderFortschritt();
}

function renderFortschritt() {
  const entry = statusData[currentMandant] || {};
  const hint = document.getElementById('fs-hint');
  if (!currentMandant) {
    hint.textContent = 'Geben Sie einen Mandanten ein, um den Fortschritt der 3 Prüfungsstufen zu sehen.';
  } else {
    const done = STAGE_DEFS.filter(([s]) => entry[s] && entry[s].done).length;
    hint.textContent = (done === 3)
      ? '✓ Alle 3 Prüfungsstufen für „' + currentMandant + '" abgeschlossen.'
      : done + ' von 3 Stufen erledigt für „' + currentMandant + '".';
  }
  STAGE_DEFS.forEach(([stage, cellId]) => {
    const cell = document.getElementById(cellId);
    const s = entry[stage];
    if (s && s.done) {
      cell.innerHTML = '<span class="fs-badge fs-done">✓ erledigt</span>'
        + '<span class="fs-date">' + (s.date || '') + '</span>';
    } else {
      cell.innerHTML = '<span class="fs-badge fs-open">offen</span>';
    }
  });
}

// Nach erfolgreichem Lauf den Status neu laden (Backend hat ihn gespeichert)
async function refreshStatusAfterRun() { await loadStatus(); }

/* ===================================================================
   MODUS 1 — VORJAHRESVERGLEICH
   =================================================================== */
let vjCurrent = null, vjPrior = null;
function vjSelect(which) {
  const id = which === 'current' ? 'vj-file-current' : 'vj-file-prior';
  const f  = document.getElementById(id).files[0];
  if (!f) return;
  if (which === 'current') vjCurrent = f; else vjPrior = f;
  const areaId = which === 'current' ? 'vj-area-current' : 'vj-area-prior';
  const nameId = which === 'current' ? 'vj-name-current' : 'vj-name-prior';
  document.getElementById(areaId).classList.add('has-file');
  document.getElementById(nameId).textContent = f.name;
  document.getElementById('vj-btn').disabled = !(vjCurrent && vjPrior);
}
async function vjRun() {
  if (!vjCurrent || !vjPrior) return;
  hide('vj-upload'); hide('vj-error'); hide('vj-result'); show('vj-progress');
  setStep('vj', 2);
  const bar = document.getElementById('vj-bar'), txt = document.getElementById('vj-text');
  let pct = 0, mi = 0;
  const msgs = [[15,'PDFs werden eingelesen…'],[40,'Posten werden extrahiert…'],[65,'Vorjahreszahlen werden verglichen…'],[88,'Excel-Bericht wird erstellt…']];
  const iv = setInterval(() => {
    if (mi < msgs.length && pct >= msgs[mi][0]) { txt.textContent = msgs[mi][1]; mi++; }
    if (pct < 90) { pct += 1; bar.style.width = pct + '%'; }
  }, 120);
  const fd = new FormData();
  fd.append('current', vjCurrent); fd.append('prior', vjPrior);
  fd.append('mandant', currentMandant);
  try {
    const resp = await fetch('/compare', { method:'POST', body:fd });
    clearInterval(iv); bar.style.width = '100%';
    if (!resp.ok) { const e = await resp.json(); vjError(e.error || 'Unbekannter Fehler'); return; }
    const data = await resp.json();
    setTimeout(() => vjShowResult(data), 400);
  } catch (e) { clearInterval(iv); vjError('Verbindungsfehler: ' + e.message); }
}
function vjShowResult(data) {
  hide('vj-progress'); show('vj-result'); setStep('vj', 3);
  document.getElementById('vj-ok').textContent  = data.ok;
  document.getElementById('vj-abw').textContent = data.abweichungen;
  document.getElementById('vj-tot').textContent = data.gesamt;
  document.getElementById('vj-textfehlt').textContent = (data.text_fehlt != null ? data.text_fehlt : '—');
  document.getElementById('vj-textneu').textContent = (data.text_neu != null ? data.text_neu : '—');
  showWarnungen('vj', data.warnungen);
  resultReady('vj', data.filename);
  refreshStatusAfterRun();
}
function vjError(msg) {
  hide('vj-progress'); show('vj-error'); show('vj-upload');
  document.getElementById('vj-err-text').textContent = msg;
  setStep('vj', 1);
}

/* ===================================================================
   MODUS 2 — BELEGPRÜFUNG (Detailzahlenvergleich)
   =================================================================== */
let bgAnhang = null;
let bgBelege = [];
function bgAnhangSelect() {
  const f = document.getElementById('bg-file-anhang').files[0];
  if (!f) return;
  bgAnhang = f;
  document.getElementById('bg-area-anhang').classList.add('has-file');
  document.getElementById('bg-name-anhang').textContent = f.name;
  bgUpdateBtn();
}
function bgBelegeAdded(files) {
  for (const f of files) bgBelege.push({ file: f, type: 'unknown' });
  bgRenderList();
  bgUpdateBtn();
  // automatische Typ-Erkennung im Hintergrund
  bgBelege.forEach((b, idx) => {
    if (b.type !== 'unknown') return;
    const fd = new FormData(); fd.append('file', b.file);
    fetch('/detect_type', { method:'POST', body:fd })
      .then(r => r.json())
      .then(j => { b.type = j.type || 'unknown'; bgRenderList(); })
      .catch(() => {});
  });
}
function bgBelegeDrop(e) {
  e.preventDefault();
  document.getElementById('bg-belege-zone').classList.remove('dragover');
  bgBelegeAdded(e.dataTransfer.files);
}
function bgRenderList() {
  const ul = document.getElementById('bg-list');
  const empty = document.getElementById('bg-belege-empty');
  ul.innerHTML = '';
  if (bgBelege.length === 0) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';
  bgBelege.forEach((b, idx) => {
    const li = document.createElement('li');
    li.className = 'beleg-item';
    let badge, label;
    if      (b.type === 'bank_guarantees') { badge = 'badge-bank'; label = 'Bank'; }
    else if (b.type === 'hr_employees')    { badge = 'badge-hr';   label = 'HR';   }
    else                                    { badge = 'badge-unk';  label = '?';    }
    li.innerHTML = `<span class="beleg-badge ${badge}">${label}</span>
      <span class="beleg-name">${b.file.name}</span>
      <span class="beleg-remove" onclick="bgRemove(${idx})">✕</span>`;
    ul.appendChild(li);
  });
}
function bgRemove(idx) { bgBelege.splice(idx, 1); bgRenderList(); bgUpdateBtn(); }
function bgUpdateBtn() {
  // Detailunterlagen sind optional: ohne sie läuft der interne Abgleich
  // (Detailzahlen im vorderen Teil des Abschlusses ↔ Angaben im Anhang).
  document.getElementById('bg-btn').disabled = !bgAnhang;
}
async function bgRun() {
  if (!bgAnhang) return;
  hide('bg-upload'); hide('bg-error'); hide('bg-result'); show('bg-progress');
  setStep('bg', 2);
  const bar = document.getElementById('bg-bar'), txt = document.getElementById('bg-text');
  let pct = 0, mi = 0;
  const msgs = [[15,'Anhang wird eingelesen…'],[40,'Belege werden analysiert…'],[70,'Positionen werden verglichen…'],[88,'Excel-Bericht wird erstellt…']];
  const iv = setInterval(() => {
    if (mi < msgs.length && pct >= msgs[mi][0]) { txt.textContent = msgs[mi][1]; mi++; }
    if (pct < 90) { pct += 1; bar.style.width = pct + '%'; }
  }, 120);
  const fd = new FormData();
  fd.append('anhang', bgAnhang);
  fd.append('mandant', currentMandant);
  bgBelege.forEach(b => fd.append('belege', b.file));
  try {
    const resp = await fetch('/pruefen', { method:'POST', body:fd });
    clearInterval(iv); bar.style.width = '100%';
    if (!resp.ok) { const e = await resp.json(); bgError(e.error || 'Unbekannter Fehler'); return; }
    const data = await resp.json();
    setTimeout(() => bgShowResult(data), 400);
  } catch (e) { clearInterval(iv); bgError('Verbindungsfehler: ' + e.message); }
}
function bgShowResult(data) {
  hide('bg-progress'); show('bg-result'); setStep('bg', 3);
  document.getElementById('bg-ok').textContent  = data.ok;
  document.getElementById('bg-abw').textContent = data.abweichungen;
  document.getElementById('bg-tot').textContent = data.gesamt;
  const hinweise = [];
  if (data.erkannte_belege && data.erkannte_belege.length) {
    hinweise.push('Erkannte Belegtypen: ' + data.erkannte_belege.join(' · '));
  }
  if ((data.intern_ok || 0) + (data.intern_abweichungen || 0) > 0) {
    hinweise.push('Interner Abgleich (Detailzahlen ↔ Anhang): '
      + data.intern_ok + ' stimmig, ' + data.intern_abweichungen + ' abweichend');
  }
  if (hinweise.length) document.getElementById('bg-erkannt').textContent = hinweise.join('  |  ');
  showWarnungen('bg', data.warnungen);
  resultReady('bg', data.filename);
  refreshStatusAfterRun();
}
function bgError(msg) {
  hide('bg-progress'); show('bg-error'); show('bg-upload');
  document.getElementById('bg-err-text').textContent = msg;
  setStep('bg', 1);
}

/* ===================================================================
   MODUS 3 — UGB-INHALTSPRÜFUNG
   =================================================================== */
let ugFile = null;
function ugSelect() {
  const f = document.getElementById('ug-file').files[0];
  if (!f) return;
  ugFile = f;
  document.getElementById('ug-area').classList.add('has-file');
  document.getElementById('ug-name').textContent = f.name;
  document.getElementById('ug-btn').disabled = false;
}
async function ugRun() {
  if (!ugFile) return;
  hide('ug-upload'); hide('ug-error'); hide('ug-result'); show('ug-progress');
  setStep('ug', 2);
  const bar = document.getElementById('ug-bar'), txt = document.getElementById('ug-text');
  let pct = 0, mi = 0;
  const msgs = [[15,'Anhang wird eingelesen…'],[40,'Sektionen werden erkannt…'],[70,'UGB-Anforderungen werden geprüft…'],[88,'Protokoll wird erstellt…']];
  const iv = setInterval(() => {
    if (mi < msgs.length && pct >= msgs[mi][0]) { txt.textContent = msgs[mi][1]; mi++; }
    if (pct < 90) { pct += 1; bar.style.width = pct + '%'; }
  }, 120);
  const fd = new FormData(); fd.append('anhang', ugFile);
  fd.append('mandant', currentMandant);
  fd.append('rechtsform', document.getElementById('ug-rechtsform').value);
  fd.append('groessenklasse', document.getElementById('ug-groessenklasse').value);
  try {
    const resp = await fetch('/ugb_review', { method:'POST', body:fd });
    clearInterval(iv); bar.style.width = '100%';
    if (!resp.ok) { const e = await resp.json(); ugError(e.error || 'Unbekannter Fehler'); return; }
    const data = await resp.json();
    setTimeout(() => ugShowResult(data), 400);
  } catch (e) { clearInterval(iv); ugError('Verbindungsfehler: ' + e.message); }
}
function ugShowResult(data) {
  hide('ug-progress'); show('ug-result'); setStep('ug', 3);
  document.getElementById('ug-bestaetigen').textContent = data.zu_bestaetigen;
  document.getElementById('ug-keinhinweis').textContent = data.kein_hinweis;
  document.getElementById('ug-fehl').textContent = data.fehlend;
  document.getElementById('ug-na').textContent   = data.nicht_anwendbar;
  showWarnungen('ug', data.warnungen);
  resultReady('ug', data.filename);
  refreshStatusAfterRun();
}
function ugError(msg) {
  hide('ug-progress'); show('ug-error'); show('ug-upload');
  document.getElementById('ug-err-text').textContent = msg;
  setStep('ug', 1);
}

/* ===================================================================
   WARNUNGEN ZUR VERLÄSSLICHKEIT DES ERGEBNISSES
   =================================================================== */
/* Das Ergebnis liegt vor, ist aber eingeschränkt: textarmes PDF, nicht
   eingelesene Detailunterlage, übersprungener Prüfschritt. Bewusst per DOM
   aufgebaut und nicht per innerHTML – die Texte enthalten Dateinamen. */
function showWarnungen(prefix, list) {
  const box = document.getElementById(prefix + '-warn');
  if (!box) return;
  box.textContent = '';
  if (!list || !list.length) { box.classList.add('hidden'); return; }
  const head = document.createElement('strong');
  head.textContent = list.length === 1
    ? '⚠ Hinweis zur Verlässlichkeit dieses Ergebnisses:'
    : '⚠ Hinweise zur Verlässlichkeit dieses Ergebnisses:';
  box.appendChild(head);
  const ul = document.createElement('ul');
  list.forEach(function (t) {
    const li = document.createElement('li');
    li.textContent = t;
    ul.appendChild(li);
  });
  box.appendChild(ul);
  box.classList.remove('hidden');
}

/* ===================================================================
   ERGEBNIS-ORDNER ÖFFNEN
   =================================================================== */
let lastResultFile = '';
function resultReady(prefix, filename) {
  lastResultFile = filename || '';
  const saved = document.getElementById(prefix + '-saved');
  if (saved) saved.textContent = 'Gespeichert im Ordner „Ergebnisse" als: ' + (filename || '');
}
async function openResults() {
  try {
    const fd = new FormData();
    if (lastResultFile) fd.append('file', lastResultFile);
    await fetch('/open_results', { method: 'POST', body: fd });
  } catch (e) {}
}

/* ===================================================================
   BEENDEN
   =================================================================== */
async function quitApp() {
  if (!confirm('Anhangsprüfer wirklich beenden?')) return;
  try { await fetch('/shutdown', { method: 'POST' }); } catch (e) {}
  document.body.innerHTML =
    '<div class="quit-screen">'
    + '<h2>✓ Anhangsprüfer wurde beendet</h2>'
    + '<p>Sie können dieses Browserfenster jetzt schließen.</p>'
    + '</div>';
}

/* ===================================================================
   INIT
   =================================================================== */
(function init() {
  try {
    const saved = localStorage.getItem('llp_mandant');
    if (saved) {
      currentMandant = saved;
      document.getElementById('mandant-input').value = saved;
    }
  } catch (e) {}
  loadStatus();
})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/healthz")
def healthz():
    return jsonify({
        "status": "ok",
        "modes": ["vorjahr", "beleg", "ugb"],
        # Nur die Profilnamen, keine Mandantenschlüssel.
        "pipelines": available_pipelines(),
        "plugin_fehler": plugin_errors(),
    })


@app.route("/status")
def status_route():
    """Liefert den Prüfungsfortschritt aller Mandanten für die 3-Stufen-Übersicht."""
    return jsonify({"mandanten": _load_status(), "stages": list(STAGES)})


@app.route("/open_results", methods=["POST"])
def open_results_route():
    """Öffnet den Ergebnisse-Ordner im Windows-Explorer (lokales Tool).

    Wenn ein Dateiname übergeben wird, wird die Datei im Explorer markiert,
    sonst nur der Ordner geöffnet. So landen Ergebnisse nicht im Downloads-
    Wirrwarr, sondern im festen Ergebnis-Ordner.
    """
    fname = (request.form.get("file") or "").strip()
    try:
        target = OUTPUT_DIR / Path(fname).name if fname else None
        if target is not None and target.exists():
            subprocess.Popen(f'explorer /select,"{target}"')
        else:
            os.startfile(str(OUTPUT_DIR))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})


@app.route("/shutdown", methods=["POST"])
def shutdown_route():
    """Beendet das Programm sauber (für den 'Beenden'-Knopf in der Oberfläche).

    Da die EXE ohne Konsolenfenster läuft, ist dies der vorgesehene Weg zum
    Stoppen. Antwort wird gesendet, dann beendet sich der Prozess kurz darauf.
    """
    def _kill() -> None:
        import os
        import time
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_kill, daemon=True).start()
    return jsonify({"ok": True})


# ---------- Modus 1: Vorjahresvergleich ----------
@app.route("/compare", methods=["POST"])
def compare_route():
    cur = request.files.get("current")
    pri = request.files.get("prior")
    if not cur or not pri:
        return jsonify({"error": "Beide PDF-Dateien müssen hochgeladen werden."}), 400

    mandant = request.form.get("mandant", "")
    pipeline = get_pipeline(mandant)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Dateiendung erhalten: Der Anhang darf als PDF ODER Word (.docx) kommen;
        # der Konnektor (parsers.document_text) wählt den Reader anhand des
        # Suffix. Ein forciertes ".pdf" würde einen Word-Anhang unlesbar machen.
        cur_suffix = Path(cur.filename or "").suffix.lower()
        pri_suffix = Path(pri.filename or "").suffix.lower()
        cur_p = tmp_path / ("current" + (cur_suffix if cur_suffix in (".pdf", ".docx") else ".pdf"))
        pri_p = tmp_path / ("prior" + (pri_suffix if pri_suffix in (".pdf", ".docx") else ".pdf"))
        cur.save(str(cur_p))
        pri.save(str(pri_p))

        warnungen: list[str] = _neue_warnungen()
        try:
            _pruefe_lesbarkeit(
                [(cur_p, f"Aktueller Anhang – {cur.filename or cur_p.name}"),
                 (pri_p, f"Vorjahres-Anhang – {pri.filename or pri_p.name}")],
                warnungen,
            )
        except LeereUnterlage as e:
            return jsonify({"error": str(e)}), 400

        try:
            result = compare_anhaenge(cur_p, pri_p, pipeline=pipeline)
        except Exception as e:
            return jsonify({"error": f"Fehler bei der Analyse: {e}"}), 500

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(cur.filename or "anhang").stem[:40]
        out_fname = f"vergleich_{stem}_{ts}.xlsx"
        out_path = OUTPUT_DIR / out_fname
        try:
            write_vorjahr_excel(result, out_path)
        except Exception as e:
            return jsonify({"error": f"Fehler beim Excel-Export: {e}"}), 500

    ok_count  = sum(1 for r in result.rows if r.status == "OK")
    abw_count = sum(1 for r in result.rows if r.status == "ABWEICHUNG")
    text_fehlt = sum(1 for t in result.text_rows if t.status == "FEHLT")
    text_neu = sum(1 for t in result.text_rows if t.status == "NEU")
    summary = {
        "ok": ok_count,
        "abweichungen": abw_count,
        "gesamt": len(result.rows),
        "text_fehlt": text_fehlt,
        "text_neu": text_neu,
        "pipeline": pipeline.name,
    }
    _record_stage(mandant, "vorjahr", out_fname, summary)
    return jsonify({**summary, "filename": out_fname, "warnungen": warnungen})


# ---------- Modus 2: Belegprüfung / Detailzahlenvergleich ----------
@app.route("/detect_type", methods=["POST"])
def detect_type_route():
    f = request.files.get("file")
    if not f:
        return jsonify({"type": "unknown"})
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / (f.filename or "file.bin")
        f.save(str(p))
        return jsonify({"type": detect_type(p)})


@app.route("/pruefen", methods=["POST"])
def pruefen_route():
    anhang_file = request.files.get("anhang")
    beleg_files = request.files.getlist("belege")
    if not anhang_file:
        return jsonify({"error": "Anhang-PDF fehlt."}), 400
    # Detailunterlagen sind OPTIONAL: ohne sie wird der interne Abgleich
    # gefahren (Detailzahlen im vorderen Teil ↔ Angaben im Anhang).

    mandant = request.form.get("mandant", "")
    pipeline = get_pipeline(mandant)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anhang_p = tmp_path / (anhang_file.filename or "anhang.pdf")
        anhang_file.save(str(anhang_p))

        warnungen: list[str] = _neue_warnungen()
        try:
            _pruefe_lesbarkeit(
                [(anhang_p, f"Anhang – {anhang_file.filename or anhang_p.name}")],
                warnungen,
            )
        except LeereUnterlage as e:
            return jsonify({"error": str(e)}), 400

        beleg_paths: list[Path] = []
        for bf in beleg_files:
            bp = tmp_path / (bf.filename or "beleg.bin")
            bf.save(str(bp))
            beleg_paths.append(bp)

        # Belegerkennung über die (mandantenspezifische) Pipeline. Auch die
        # Beschriftungen kommen von dort – die App kennt die Belegtypen ihrer
        # Mandanten nicht, sie sind Teil des jeweiligen Plugins.
        labels = pipeline.beleg_type_labels
        erkannte = sorted({labels.get(pipeline.detect_beleg_type(bp), "Unbekannt")
                           for bp in beleg_paths})

        try:
            result = pruefen(anhang_p, beleg_paths, pipeline=pipeline)
        except Exception as e:
            return jsonify({"error": f"Fehler bei der Analyse: {e}"}), 500

        # Interner Abgleich: Detailzahlen im vorderen Teil des Abschlusses
        # gegen die Angaben im Anhang – braucht keine externen Belege.
        intern_ok = intern_abw = 0
        try:
            from anhangspruefer.pruefung.comparator import PruefRow
            from anhangspruefer.pruefung.intern_abgleich import abgleich_intern

            # Bilanz/GuV können im selben Dokument stehen ODER als eigene
            # Datei(en) hochgeladen sein – beides wird berücksichtigt.
            abgleich = abgleich_intern(anhang_p, detail_dokumente=beleg_paths)
            for hinweis in abgleich.uebersprungene_dateien:
                warnungen.append(
                    f"Detailunterlage nicht eingelesen – ihre Zahlen sind NICHT "
                    f"abgeglichen: {hinweis}")
            for z in abgleich.zeilen:
                result.rows.append(PruefRow(
                    section="Intern: Detailzahlen ↔ Anhang",
                    label=z.label,
                    anhang_value=z.wert_anhang,
                    beleg_value=z.wert_vorne,
                    difference=z.differenz,
                    status=z.status,
                    page_anhang=z.seite_anhang,
                    note=f"Detailzahl auf Seite {z.seite_vorne} des Abschlusses",
                ))
                if z.status == "OK":
                    intern_ok += 1
                else:
                    intern_abw += 1
        except Exception as e:
            # Die Belegprüfung darf daran nicht scheitern – aber verschweigen
            # darf sie es auch nicht: der interne Abgleich hat dann NICHT
            # stattgefunden, und der Bericht sähe trotzdem vollständig aus.
            warnungen.append(
                f"Interner Abgleich (Detailzahlen ↔ Anhang) nicht durchgeführt: {e}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(anhang_file.filename or "anhang").stem[:35]
        out_fname = f"pruefung_{stem}_{ts}.xlsx"
        out_path = OUTPUT_DIR / out_fname
        try:
            write_pruefung_excel(result, out_path)
        except Exception as e:
            return jsonify({"error": f"Fehler beim Excel-Export: {e}"}), 500

    summary = {
        "ok": result.count_ok,
        "abweichungen": result.count_abweichung,
        "gesamt": len(result.rows),
        "pipeline": pipeline.name,
        "intern_ok": intern_ok,
        "intern_abweichungen": intern_abw,
    }
    _record_stage(mandant, "beleg", out_fname, summary)
    return jsonify({**summary, "filename": out_fname, "erkannte_belege": erkannte,
                    "warnungen": warnungen})


# ---------- Modus 3: UGB-Inhaltsprüfung ----------
@app.route("/ugb_review", methods=["POST"])
def ugb_review_route():
    anhang_file = request.files.get("anhang")
    if not anhang_file:
        return jsonify({"error": "Anhang-PDF fehlt."}), 400

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        anhang_p = tmp_path / (anhang_file.filename or "anhang.pdf")
        anhang_file.save(str(anhang_p))

        # Mindesttextprüfung ZUERST: bei textlosem Anhang würde jede Pflicht-
        # angabe als "nicht anwendbar" oder "Fehlt" gewertet und das Arbeits-
        # papier sähe vollständig geprüft aus.
        warnungen: list[str] = _neue_warnungen()
        try:
            _pruefe_lesbarkeit(
                [(anhang_p, f"Anhang – {anhang_file.filename or anhang_p.name}")],
                warnungen,
            )
        except LeereUnterlage as e:
            return jsonify({"error": str(e)}), 400

        # Prüfprogramm laden: bevorzugt das erweiterbare Excel im Fachordner,
        # sonst die Code-Standardliste.
        from anhangspruefer.compliance.knowledge.checklist_loader import ChecklistLoader
        loader = ChecklistLoader()
        try:
            pp = _find_pruefprogramm()
            if pp is not None:
                checklist = loader.load_from_xlsx(pp)
            else:
                checklist = loader.load_default_checklist()
        except Exception:
            checklist = loader.load_default_checklist()

        try:
            engine = ReviewEngine()
            review_result = engine.review(notes_path=anhang_p, checklist=checklist)
        except Exception as e:
            return jsonify({"error": f"Fehler bei der UGB-Prüfung: {e}"}), 500

        # Rechtsform/Größenklasse aus der UI (Pflicht-Auswahl vor dem Start).
        # "unbekannt" => keine größenabhängige Filterung (konservativ).
        _rechtsform_raw = (request.form.get("rechtsform", "unbekannt") or "unbekannt").strip().lower()
        _groessenklasse_raw = (request.form.get("groessenklasse", "unbekannt") or "unbekannt").strip().lower()
        _legal_form = _rechtsform_raw if _rechtsform_raw in ("gmbh", "ag") else None
        _size_class = _groessenklasse_raw if _groessenklasse_raw in ("klein", "mittel", "gross") else None
        if _legal_form is None or _size_class is None:
            warnungen.append(
                "Ohne Rechtsform/Größenklasse bleiben größenabhängige Erleichterungen ungefiltert."
            )

        # Relevanz-Filter: Angaben zu nicht vorhandenen Bilanz-/GuV-Positionen
        # -> "NICHT ANWENDBAR" (Angabe nur nötig, wenn die Position vorliegt).
        try:
            from anhangspruefer.compliance.knowledge.relevance import apply_relevance
            import pdfplumber
            with pdfplumber.open(str(anhang_p)) as _pdf:
                _doc_text = "\n".join((p.extract_text() or "") for p in _pdf.pages)
            apply_relevance(review_result, checklist, _doc_text,
                            legal_form=_legal_form, size_class=_size_class)
        except Exception:
            pass  # optional – ohne Filter bleibt das bisherige Verhalten

        # Fundstellen + ehrliches Verdikt (Heuristik, OHNE LLM): je Prüfpunkt die
        # beste Anhang-Textstelle; Verdikt Fehlt nur bei bewiesener Abwesenheit,
        # sonst Offen — der Prüfer bestätigt "Ja" per Dropdown in der Excel.
        # (Der lokale Mistral war als Ja/Nein-Auswähler unzuverlässig — siehe
        # Council-Analyse; er bleibt als Modul erhalten, aber standardmäßig aus.)
        ki_info = None
        try:
            from anhangspruefer.compliance.knowledge.llm_matcher import (
                extract_paragraphs, apply_heuristic_fundstellen,
            )
            apply_heuristic_fundstellen(review_result, checklist, extract_paragraphs(anhang_p))
        except Exception:
            pass  # optional – Prüfung darf nie an der Fundstellensuche scheitern

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(anhang_file.filename or "anhang").stem[:35]
        # Doku = die KPMG-Checkliste selbst, ausgefüllt (Excel-Arbeitspapier).
        out_fname = f"UGB-Checkliste_{stem}_{ts}.xlsx"
        out_path = OUTPUT_DIR / out_fname
        try:
            from anhangspruefer.compliance.reporting.checklist_excel import generate_checklist_xlsx
            generate_checklist_xlsx(checklist, review_result, out_path,
                                    legal_form=_legal_form, size_class=_size_class)
        except Exception as e:
            return jsonify({"error": f"Fehler beim Bericht-Export: {e}"}), 500

    # Zählung nach ComplianceStatus; "Offen" (NICHT BEURTEILBAR) wird anhand
    # von technical_reasoning weiter aufgesplittet (Angabe gefunden -> zu
    # bestätigen; sonst -> kein Hinweis gefunden).
    findings = getattr(review_result, "findings", []) or []
    def _n(*vals):
        return sum(1 for f in findings if getattr(getattr(f, "status", None), "value", "") in vals)
    def _offen_mit(praefix):
        return sum(1 for f in findings
                   if getattr(getattr(f, "status", None), "value", "") == "NICHT BEURTEILBAR"
                   and (getattr(f, "technical_reasoning", "") or "").startswith(praefix))
    summary = {
        "zu_bestaetigen": _offen_mit("Angabe gefunden"),
        "kein_hinweis": _offen_mit("Kein Hinweis"),
        "fehlend": _n("NICHT ENTSPRECHEND"),
        "nicht_anwendbar": _n("NICHT ANWENDBAR"),
        "gesamt": len(findings),
        "rechtsform": _legal_form or "unbekannt",
        "groessenklasse": _size_class or "unbekannt",
        "ki": ki_info,
    }
    _record_stage(request.form.get("mandant", ""), "ugb", out_fname, summary)
    return jsonify({**summary, "filename": out_fname, "warnungen": warnungen})


# ---------- Downloads ----------
@app.route("/download/<path:filename>")
def download_route(filename):
    safe = Path(filename).name
    p = OUTPUT_DIR / safe
    if not p.exists():
        return "Datei nicht gefunden.", 404
    return send_file(str(p), as_attachment=True, download_name=safe)


@app.route("/download-tool")
def download_tool_route():
    if not TOOL_ZIP.exists():
        return "Tool-ZIP nicht gefunden.", 404
    return send_file(str(TOOL_ZIP), as_attachment=True, download_name=TOOL_ZIP.name)


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
def _free_port(default: int) -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", default))
        s.close()
        return default
    except OSError:
        s.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port


def _open_browser(port: int) -> None:
    """Öffnet den Browser, sobald der Server WIRKLICH erreichbar ist.

    Statt stur 1,2 s zu warten (was beim ersten EXE-Start zu kurz ist, weil
    PyInstaller sich erst entpacken muss), wird aktiv gepollt, bis der Port
    Verbindungen annimmt – erst dann wird der Browser aufgerufen. Zusätzlich
    mehrere Öffnungsmethoden als Fallback (Windows: os.startfile).
    """
    import os
    import time

    url = f"http://localhost:{port}"

    # 1) Warten bis der Server lauscht (max. 60 s – deckt langsame Erststarts ab)
    deadline = 60.0
    waited = 0.0
    while waited < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.4)
            waited += 0.4

    # 2) Browser öffnen – robust über mehrere Wege
    time.sleep(0.3)  # dem Server kurz Luft geben, die erste Seite zu liefern
    for _ in range(3):
        opened = False
        try:
            opened = webbrowser.open(url, new=2)
        except Exception:
            opened = False
        if not opened:
            try:
                os.startfile(url)  # type: ignore[attr-defined]  # Windows-Fallback
                opened = True
            except Exception:
                opened = False
        if opened:
            return
        time.sleep(1.0)


def _main() -> None:
    port = _free_port(5555)
    print("=" * 64)
    print("   LLP ANHANGSPRUEFER")
    print("=" * 64)
    print()
    print("   Das Tool wird gestartet - BITTE WARTEN.")
    print("   (Beim ersten Mal vom Netzlaufwerk kann das bis zu 1 Minute")
    print("    dauern. Der Browser oeffnet sich dann AUTOMATISCH.)")
    print()
    print(f"   Falls der Browser nicht aufgeht: {('http://localhost:%d' % port)}")
    print()
    print("   Dieses Fenster BITTE OFFEN LASSEN, solange Sie arbeiten.")
    print("   Zum Beenden: dieses Fenster schliessen.")
    print("=" * 64)
    # Mandantenprofile: der Anwender muss sehen, was angestöpselt ist – und
    # vor allem, wenn ein Profil NICHT geladen wurde.
    print(f"   Mandantenprofile: {', '.join(available_pipelines())}")
    for _f in plugin_errors():
        print(f"   !! MANDANTENPROFIL NICHT GELADEN: {_f}")
        print("      Der Lauf verwendet das Standardprofil.")
    if plugin_errors():
        print("=" * 64)
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    # Da die EXE ohne Konsolenfenster läuft, ist bei einem Startfehler nichts
    # sichtbar. Deshalb wird jeder Fehler in eine Log-Datei NEBEN der EXE
    # geschrieben, damit er diagnostizierbar bleibt.
    try:
        _main()
    except Exception:
        import traceback
        try:
            log = HERE / "_Startfehler.log"
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("Anhangsprüfer konnte nicht starten:\n\n")
                fh.write(traceback.format_exc())
        except Exception:
            pass
        raise