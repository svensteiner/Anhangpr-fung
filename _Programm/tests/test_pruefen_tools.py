"""Share-Check: Foundry-Status und Nachbar-Tools ohne Schlüssel."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "_Gemeinsam"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

MOD = SHARED / "pruefen_tools.py"


def _load():
    spec = importlib.util.spec_from_file_location("pruefen_tools", MOD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_findet_diesen_anhangspruefer() -> None:
    module = _load()
    data = module.report(SHARED)
    assert data["anhang"] is not None
    assert Path(data["anhang"]).name == "Starten.bat"
    text = module.format_report(data)
    assert "Anhangspruefer:  gefunden" in text
    assert "Startskript:" in text
    assert "ANLEITUNG.txt" in text
    assert "Schluessel" in text
    assert "FOUNDRY_API_KEY" not in text
    assert "sk-" not in text
    foundry = data["foundry"]
    assert "kurz" in foundry
    assert "bereit" in foundry


def test_report_erkennt_mistral_bei_text_verbessern(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Mistral (bis 45 s)"\n'
        'return "rules+mistral-local", "substantial"\n',
        encoding="utf-8",
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text('& $venvPython -m streamlit run "app/ui/streamlit_app.py"\n', encoding="utf-8")
    (tools / "Pseudokrat" / "START.bat").parent.mkdir(parents=True)
    (tools / "Pseudokrat" / "START.bat").write_text("@echo off\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_modus"] == "noch Mistral"
    assert data["text_start"] == "noch Streamlit"
    assert data["pseudokrat"] is not None
    blob = module.format_report(data)
    assert "noch Mistral" in blob
    assert "Foundry-Seite" in blob
    assert "noch Streamlit" in blob
    assert "Anwenden.bat" in blob
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_erkennt_foundry_bei_text_verbessern(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_modus"] == "Foundry"
    assert data["text_start"] == "Foundry-Tor"
    assert data["text_cmd_modus"] == "Foundry-Tor"
    assert data["text_provider"] is not None
    assert data["text_exe"] is None
    assert data["text_runtime_modus"] == "nicht gefunden"
    assert data["text_mistral_modus"] == "nicht gefunden"
    assert data["text_streamlit_modus"] == "nicht gefunden"
    assert data["text_api_modus"] == "nicht gefunden"
    blob = module.format_report(data)
    assert "noch Mistral" not in blob
    assert "Foundry-Tor" in blob
    assert "vorhanden" in blob
    assert "Ollama-Rest:" in blob
    assert "Mistral-Client:" in blob
    assert "Streamlit-Datei:" in blob
    assert "Alte API:" in blob
    assert module.text_foundry_ok(gemeinsam) is True


def test_report_foundry_desktop_aber_streamlit_start_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text('streamlit run "app/ui/streamlit_app.py"\n', encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_modus"] == "Foundry"
    assert data["text_start"] == "noch Streamlit"
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_findet_exe_im_dist_ordner(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    dist = tools / "rephraser" / "dist" / "TextVerbessern"
    dist.mkdir(parents=True)
    (dist / "TextVerbessern.exe").write_bytes(b"mz")
    data = module.report(gemeinsam)
    assert data["text_exe"] is not None
    assert data["text_exe"].name == "TextVerbessern.exe"
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_foundry_aber_streamlit_datei_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    ui = tools / "rephraser" / "app" / "ui"
    ui.mkdir(parents=True)
    (ui / "streamlit_app.py").write_text("import streamlit as st\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_streamlit_modus"] == "noch Streamlit"
    blob = module.format_report(data)
    assert "streamlit_app.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_foundry_aber_fastapi_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    (tools / "rephraser" / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "def health() -> dict[str, str]:\n"
        '    return {"status": "ok", "default_provider": "fast-editor"}\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_api_modus"] == "noch API"
    blob = module.format_report(data)
    assert "FastAPI" in blob or "uvicorn" in blob
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_foundry_aber_mistral_client_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "app" / "providers" / "mistral_provider.py").write_text(
        "class LocalMistralProvider:\n"
        "    def rewrite(self, text):\n"
        "        return '/api/generate http://127.0.0.1:11434'\n",
        encoding="utf-8",
    )
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_mistral_modus"] == "noch Ollama"
    blob = module.format_report(data)
    assert "noch Ollama" in blob
    assert "mistral_provider.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_foundry_aber_ollama_probe_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    (tools / "rephraser" / "app" / "local_runtime.py").write_text(
        "MISTRAL_BASE_URL = 'http://127.0.0.1:11434'\n"
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return True\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_modus"] == "Foundry"
    assert data["text_runtime_modus"] == "noch Ollama"
    blob = module.format_report(data)
    assert "noch Ollama" in blob
    assert "Anwenden.bat" in blob
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_erkennt_gepatchten_local_runtime(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"\n'
        'return "rules+foundry", "substantial"\n',
        encoding="utf-8",
    )
    provider = tools / "rephraser" / "app" / "providers" / "foundry_provider.py"
    provider.parent.mkdir(parents=True, exist_ok=True)
    provider.write_text("def foundry_ready():\n    return True\n", encoding="utf-8")
    (tools / "rephraser" / "TEXT VERBESSERN.cmd").write_text(
        "rem LLP-FOUNDRY-TOR\n", encoding="utf-8"
    )
    ps1 = tools / "rephraser" / "scripts" / "start_windows.ps1"
    ps1.parent.mkdir(parents=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )
    (tools / "rephraser" / "app" / "local_runtime.py").write_text(
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return False  # LLP-FOUNDRY-TOR: kein Ollama\n"
        "    return os.getenv('MISTRAL_BASE_URL', 'http://127.0.0.1:11434')\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_runtime_modus"] == "kein Ollama"
    blob = module.format_report(data)
    assert "Ollama-Rest:     kein Ollama" in blob
    assert "prueft noch Ollama" not in blob
    assert module.text_foundry_ok(gemeinsam) is True


def test_kurz_gibt_nur_statuszeile() -> None:
    module = _load()
    assert module.main(["--kurz"]) == 0
