"""Anwendertexte: kein EXE-Kopieren, Modus 3 zweistufig, Foundry zentral."""

from pathlib import Path

import docx

ROOT = Path(__file__).resolve().parents[2]


def test_anleitung_kein_exe_copy_und_modus3_pflicht():
    text = (ROOT / "ANLEITUNG.txt").read_text(encoding="utf-8").lower()
    assert "nicht auf den pc kopiert" in text or "nicht" in text and "kopiert" in text
    assert ".exe" not in text
    assert "ohne auswahl startet nichts" in text
    assert "foundry" in text
    assert "pseudokrat bleibt lokal" in text
    assert "pruefen.bat" in text
    assert "bitte pruefen.bat" in text
    assert "vor teil 2" in text
    assert "fachliche unterlagen" in text
    assert "ohne bestaetigung" in text
    assert "teil 1" in text
    assert "teil 2" in text
    assert "unbekannt" in text
    assert "tools_starten.bat" in text
    assert "llp_start" in text
    assert "_gemeinsam\\anleitung.txt" in text or "_gemeinsam/anleitung.txt" in text
    assert "teil 2 rest" in text
    assert "42 von 180 fragen geprueft" not in text
    assert "aendert" in text and "den text nicht" in text
    assert "desktop-selbsttest" in text
    assert "lokale bewertung" in text


def test_installieren_kopiert_keine_exe():
    text = (ROOT / "Installieren.bat").read_text(encoding="utf-8", errors="replace").lower()
    assert "nicht auf den pc kopiert" in text
    assert "anhangspruefer.exe" not in text
    assert "starten.bat" in text
    assert "tools_starten.bat" in text
    assert "llp ai tools" in text
    assert "text verbessern" in text
    assert "foundry" in text
    assert "mistral" in text
    share = text.find("..\\_gemeinsam\\llp_ai")
    lokal = text.find("%~dp0_gemeinsam\\llp_ai")
    assert share != -1 and lokal != -1
    assert share < lokal


def test_struktur_start_ist_server_nicht_exe():
    text = (ROOT / "STRUKTUR.md").read_text(encoding="utf-8").lower()
    assert "start für anwender" in text
    assert "anwender kopieren keine exe" in text
    assert "llp_ai" in text
    assert "/ugb_eingrenzung" in text
    assert "teil 2" in text
    assert "teil 1" in text


def test_vorstellung_kein_pc_copy_keine_exe():
    doc = docx.Document(str(ROOT / "LLP Anhangspruefer - Vorstellung und Anleitung.docx"))
    blob = "\n".join(p.text for p in doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            blob += "\n" + "\n".join(c.text for c in row.cells)
    low = blob.lower()
    assert "nicht auf den pc kopiert" in low
    assert "auf ihren pc kopiert" not in low
    assert "eine exe. doppelklick" not in low
    assert "keine exe auf den pc kopieren" in low
    assert "foundry" in low
    assert "n. a. (rechtsgrund)" in low
    assert "lokales sprachmodell" not in low
    assert "unbekannt" in low
    assert "bestaetig" in low or "bestätig" in low
    assert "tools_starten.bat" in low
    assert "llp ai tools" in low
    assert "offen – angabe gefunden" in low or "offen - angabe gefunden" in low
    assert "nicht mistral" in low
    assert "teil 1" in low
    assert "teil 2" in low
    assert "rest prüfen" in low or "rest pruefen" in low
    assert "dann starten" not in low
    assert "text verbessern" in low
    assert "anleitung.txt" in low
    assert "foundry-tor" in low or "foundry tor" in low
    assert "daneben" in low
    assert "pruefen.bat" in low
    assert "kein ollama-rest" in low
    assert "keine streamlit-datei" in low
    assert "keine alte offline-html" in low
    assert "kein offline-editor-skript" in low
    assert "keine startbare sicherung" in low
    assert "keine alte kommandozeile" in low
    assert "keinen desktop-selbsttest" in low
    assert "keine lokale bewertung" in low
    assert "bei jedem start" in low
    assert "bitte pruefen.bat" in low
    assert "vor teil 2" in low
    assert "wie viele fragen vom rest" in low
    assert "sagt installieren das klar" in low
    assert "llp_start" in low
    assert "start_windows.ps1" in low
    assert "nicht streamlit" in low
    assert "dieselbe .env" in low or "dieselbe .env wie bisher" in low


def test_share_anleitung_fuer_kollegen():
    text = (ROOT / "_Gemeinsam" / "ANLEITUNG.txt").read_text(encoding="utf-8").lower()
    assert "nicht" in text and "kopiert" in text
    assert ".exe" not in text
    assert "foundry" in text
    assert "pseudokrat" in text and "ohne foundry" in text
    assert "teil 1" in text
    assert "teil 2" in text
    assert "unbekannt" in text
    assert "pruefen.bat" in text
    assert "tools_starten" in text or "llp ai tools" in text
    assert "nicht mistral" in text
    assert "anwenden.bat" in text
    assert "daneben" in text
    assert "kein ollama-rest" in text
    assert "keine streamlit-datei" in text
    assert "keine alte api" in text
    assert "keine mistral-pipeline" in text
    assert "kein mistral-export" in text
    assert "keine exe-anleitung" in text
    assert "keine alte offline-html" in text
    assert "kein offline-editor-skript" in text
    assert "keine startbare sicherung" in text
    assert "keine alte kommandozeile" in text
    assert "keine startbare desktop-oberflaeche" in text
    assert "keinen desktop-selbsttest" in text
    assert "keine lokale bewertung" in text
    assert "vor teil 2" in text
    assert "wie viele fragen vom rest" in text
    assert "bei jedem start" in text
    assert "bitte pruefen.bat" in text
    assert "sagt installieren das klar" in text
    assert "healthz" not in text
    lies = (ROOT / "_Gemeinsam" / "LIESMICH.txt").read_text(encoding="utf-8").lower()
    assert "anleitung.txt" in lies
    assert "bitte pruefen.bat" in lies
    assert "bei jedem start" in lies
    assert "wie gewohnt" not in lies
    assert "heuristik / regeln" not in lies
    assert "text verbessern" in lies
    assert "aendert den text nicht" in lies or "ändert den text nicht" in lies


def test_entwicklerdoku_verweist_auf_browser_nicht_alte_gui():
    text = (ROOT / "_Programm" / "README_entwickler.md").read_text(encoding="utf-8").lower()
    assert "starten.bat" in text
    assert "gui-version (empfohlen)" not in text
    assert "benutzerfreundliche gui" not in text
    assert "run_gui.py" in text
    assert "abgeschaltet" in text
    assert "teil 2: rest prüfen" in text or "teil 2: rest pruefen" in text
    assert "unbekannt" in text


def test_klienten_liesmich_ohne_healthz():
    text = (ROOT / "Klienten" / "_LIESMICH.txt").read_text(encoding="utf-8").lower()
    assert "healthz" not in text
    assert "pruefen.bat" in text
    assert "_gemeinsam\\pruefen.bat" in text
    assert "llp_ai\\pruefen.bat" not in text
    assert "startseite" in text


def test_llp_ai_pruefen_nutzt_den_gemeinsamen_check():
    text = (ROOT / "_Gemeinsam" / "llp_ai" / "Pruefen.bat").read_text(encoding="utf-8")
    assert "pruefen_tools.py" in text
    assert "llp_ai.pruefen" not in text


def test_starten_zeigt_foundry_kurz():
    text = (ROOT / "Starten.bat").read_text(encoding="utf-8")
    assert "--kurz" in text
    assert "--rest" in text
    assert "pruefen_tools.py" in text
    assert "noch ein alter Weg" in text
    assert "Anwenden hat nicht geklappt" in text


def test_starten_wendet_foundry_an():
    text = (ROOT / "Starten.bat").read_text(encoding="utf-8")
    assert "anwenden.py" in text
    assert "--leise" in text
    assert "--rest" in text
    assert "text_verbessern_foundry" in text.lower()
    assert text.find("anwenden.py") < text.find("%PY% app.py")
    assert text.find("--leise") < text.find("--rest")


def test_installieren_wendet_foundry_an():
    text = (ROOT / "Installieren.bat").read_text(encoding="utf-8", errors="replace").lower()
    assert "anwenden.py" in text
    assert "text verbessern auf foundry" in text
    assert "pruefen_tools.py" in text
    assert "if errorlevel 2" in text
    assert "--rest" in text
    assert "noch einen alten weg" in text
    assert text.find("anwenden.py") < text.find("--rest")
    assert text.find("pruefen_tools.py") < text.find("fertig!")
    share = text.find("..\\_gemeinsam\\llp_ai")
    lokal = text.find("%~dp0_gemeinsam\\llp_ai")
    assert share != -1 and lokal != -1
    assert share < lokal


def test_llp_start_setzt_foundry_root():
    text = (ROOT / "_Gemeinsam" / "llp_start" / "Start.bat").read_text(encoding="utf-8")
    assert "LLP_SHARED_AI_ROOT" in text
    low = text.lower()
    assert "foundry" in low
    assert "mistral" in low
    assert "ollama" in low
    lies = (ROOT / "_Gemeinsam" / "llp_start" / "LIESMICH.txt").read_text(encoding="utf-8").lower()
    assert "llp_shared_ai_root" in lies
    assert "pseudokrat bleibt lokal" in lies


def test_werkzeuge_pseudokrat_ohne_foundry():
    text = (ROOT / "_Gemeinsam" / "WERKZEUGE.txt").read_text(encoding="utf-8").lower()
    assert "pseudokrat" in text
    assert "keine" in text and "foundry" in text
    assert "llp_ai" in text
    assert "anwenden.bat" in text
    assert "pruefen.bat" in text
    assert "bitte pruefen.bat" in text
    assert "tools_starten.bat" in text
    assert "foundry-tor" in text
    assert "nicht mistral" in text
    assert "offline-editor" in text
    assert "startbare" in text
    assert "kommandozeile" in text
    assert "selbsttest" in text
    assert "bewertung" in text
    assert "sonst die sichere lokale" not in text
    assert "keine lokale regelfassung" in text
    assert "unveraendert" in text or "unverändert" in text
    assert "knopf gesperrt" in text


def test_tools_starten_ruft_llp_start_auf():
    text = (ROOT / "Tools_starten.bat").read_text(encoding="utf-8")
    assert "LLP_SHARED_AI_ROOT" in text
    assert "llp_start\\Start.bat" in text
    assert ".exe" not in text.lower()
    share = text.lower().find("..\\_gemeinsam\\llp_start")
    lokal = text.lower().find("%~dp0_gemeinsam\\llp_start")
    assert share != -1 and lokal != -1
    assert share < lokal


def test_llp_start_findet_tools_im_eigenen_und_nachbarordner():
    text = (ROOT / "_Gemeinsam" / "llp_start" / "Start.bat").read_text(encoding="utf-8")
    assert '%ROOT%\\app.py' in text or "%ROOT%\\app.py" in text
    assert '%ROOT%\\..\\Pseudokrat' in text or "%ROOT%\\..\\Pseudokrat" in text
    assert 'call :TRY "%ROOT%" "Starten.bat"' in text
    assert "TEXT VERBESSERN.cmd" not in text
    assert "text_verbessern_foundry" in text.lower()


def test_text_verbessern_foundry_kit_liegt_bereit():
    kit = ROOT / "_Gemeinsam" / "text_verbessern_foundry"
    assert (kit / "Anwenden.bat").is_file()
    assert (kit / "Starten.bat").is_file()
    assert (kit / "anwenden.py").is_file()
    assert (kit / "server.py").is_file()
    assert (kit / "foundry_provider.py").is_file()
    lies = (kit / "LIESMICH.txt").read_text(encoding="utf-8").lower()
    assert "foundry" in lies
    assert "mistral" in lies
    assert "ollama" in lies
    assert "start_windows.ps1" in lies
    assert "streamlit" in lies
    assert "schnellstart.md" in lies
    assert "readme.md" in lies
    assert "liesmich-foundry.txt" in lies
    assert "wie gewohnt" not in lies
    assert "foundry-seite" in lies
    assert "startet nicht" in lies
    kit_start = (kit / "Starten.bat").read_text(encoding="utf-8").lower()
    assert "anwenden.py" in kit_start
    assert "--leise" in kit_start
    assert "--rest" in kit_start
    assert "noch ein alter weg" in kit_start
    start = (ROOT / "_Gemeinsam" / "llp_start" / "Start.bat").read_text(encoding="utf-8")
    low = start.lower()
    assert "anwenden.py" in low
    assert "foundry_text" in low
    assert "call :foundry_text leise" in low
    assert "--rest" in low
    assert "noch ein alter weg" in low
    start_pos = start.lower().find("call :foundry_text leise")
    wahl_pos = start.lower().find("set /p wahl")
    assert start_pos != -1 and wahl_pos != -1 and start_pos < wahl_pos
    assert "llp_shared_ai_root" in low
    assert "text_verbessern_foundry" in low
    assert "text_verbessern_foundry\" \"starten.bat" in low or "text_verbessern_foundry\\starten.bat" in low
    assert "text verbessern.cmd" not in low
    assert "mistral-rephraser wird nicht gestartet" in low
