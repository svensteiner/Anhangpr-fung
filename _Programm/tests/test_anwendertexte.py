"""Anwendertexte: kein EXE-Kopieren, Modus 3 zweistufig, Foundry zentral."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_anleitung_kein_exe_copy_und_modus3_pflicht():
    text = (ROOT / "ANLEITUNG.txt").read_text(encoding="utf-8").lower()
    assert "nicht auf den pc kopiert" in text or "nicht" in text and "kopiert" in text
    assert ".exe" not in text
    assert "ohne auswahl startet nichts" in text
    assert "foundry" in text
    assert "pseudokrat bleibt lokal" in text
    assert "pruefen.bat" in text
    assert "fachliche unterlagen" in text
    assert "ohne bestaetigung" in text
    assert "unbekannt" in text
    assert "tools_starten.bat" in text
    assert "llp_start" in text


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


def test_struktur_start_ist_server_nicht_exe():
    text = (ROOT / "STRUKTUR.md").read_text(encoding="utf-8").lower()
    assert "start für anwender" in text
    assert "anwender kopieren keine exe" in text
    assert "llp_ai" in text


def test_vorstellung_kein_pc_copy_keine_exe():
    import docx

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


def test_klienten_liesmich_ohne_healthz():
    text = (ROOT / "Klienten" / "_LIESMICH.txt").read_text(encoding="utf-8").lower()
    assert "healthz" not in text
    assert "pruefen.bat" in text
    assert "startseite" in text


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
    assert "tools_starten.bat" in text


def test_tools_starten_ruft_llp_start_auf():
    text = (ROOT / "Tools_starten.bat").read_text(encoding="utf-8")
    assert "LLP_SHARED_AI_ROOT" in text
    assert "llp_start\\Start.bat" in text
    assert ".exe" not in text.lower()


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
    start = (ROOT / "_Gemeinsam" / "llp_start" / "Start.bat").read_text(encoding="utf-8")
    low = start.lower()
    assert "anwenden.py" in low
    assert "foundry_text" in low
    assert "llp_shared_ai_root" in low
    assert "text_verbessern_foundry" in low
    assert "text_verbessern_foundry\" \"starten.bat" in low or "text_verbessern_foundry\\starten.bat" in low
    assert "--text-foundry" in low
    assert "mistral-rephraser wird nicht gestartet" in low
