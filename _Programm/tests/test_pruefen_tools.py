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
    assert data["anhang_ollama"] is None
    assert "Anhang-Ollama:   beiseite" in text
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
    assert data["text_pipeline_modus"] == "nicht gefunden"
    assert data["text_hybrid_modus"] == "nicht gefunden"
    assert data["text_pyproject_modus"] == "nicht gefunden"
    blob = module.format_report(data)
    assert "noch Mistral" not in blob
    assert "Foundry-Tor" in blob
    assert "vorhanden" in blob
    assert "Ollama-Rest:" in blob
    assert "Mistral-Client:" in blob
    assert "Streamlit-Datei:" in blob
    assert "Alte API:" in blob
    assert "Alte CLI:" in blob
    assert "Sicherung:" in blob
    assert "Desktop-Fenster:" in blob
    assert "Selbsttest:" in blob
    assert "Regelfassung:" in blob
    assert "Desktop-Pipeline:" in blob
    assert "Bewertung:" in blob
    assert "Text-Pipeline:" in blob
    assert "Hybrid-Weg:" in blob
    assert "Lokal-Regeln:" in blob
    assert "Schnell-Editor:" in blob
    assert "Paketdatei:" in blob
    assert "Original-Start:" in blob
    assert "Provider-Export:" in blob
    assert "Tool-Anleitung:" in blob
    assert "Offline-HTML:" in blob
    assert "Offline-JS:" in blob
    assert "Packaging:" in blob
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


def test_report_foundry_aber_mistral_generate_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "providers" / "mistral_provider.py").write_text(
        "class LocalMistralProvider:\n"
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n"
        '        raise RuntimeError("LocalMistralProvider ist abgeschaltet. Nur Foundry (llp_ai).")  # LLP-FOUNDRY-TOR\n'
        "    def rewrite(self, text):\n"
        '        return self.base_url + "/api/generate"\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_mistral_modus"] == "noch Ollama"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Mistral-Client" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_mistral_port_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "providers" / "mistral_provider.py").write_text(
        "class LocalMistralProvider:\n"
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n"
        '        raise RuntimeError("LocalMistralProvider ist abgeschaltet. Nur Foundry (llp_ai).")  # LLP-FOUNDRY-TOR\n'
        "        self.base_url = 'http://127.0.0.1:11434'\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_mistral_modus"] == "noch Ollama"
    assert module.text_foundry_ok(gemeinsam) is False
    assert "Mistral-Client" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_mistral_base_url_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "providers" / "mistral_provider.py").write_text(
        "class LocalMistralProvider:\n"
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n"
        '        raise RuntimeError("LocalMistralProvider ist abgeschaltet. Nur Foundry (llp_ai).")  # LLP-FOUNDRY-TOR\n'
        "        self.base_url = os.getenv('MISTRAL_BASE_URL', 'http://127.0.0.1:0')\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_mistral_modus"] == "noch Ollama"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Mistral-Client" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_mistral_timeout_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "providers" / "mistral_provider.py").write_text(
        "class LocalMistralProvider:\n"
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n"
        '        raise RuntimeError("LocalMistralProvider ist abgeschaltet. Nur Foundry (llp_ai).")  # LLP-FOUNDRY-TOR\n'
        "        configured_timeout = float(os.getenv('MISTRAL_TIMEOUT_SECONDS', '42'))\n",
        encoding="utf-8",
    )
    (tools / "rephraser" / "app" / "local_runtime.py").write_text(
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return False  # LLP-FOUNDRY-TOR: kein Ollama\n"
        "MISTRAL_PREFLIGHT_TIMEOUT_SECONDS = 0.5\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_mistral_modus"] == "noch Ollama"
    assert data["text_runtime_modus"] == "noch Ollama"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    leftovers = module.leftovers_in_tool(tools / "rephraser")
    assert "Mistral-Client" in leftovers
    assert "Ollama" in leftovers


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
    assert data["text_runtime_modus"] == "noch Ollama"
    assert module.text_foundry_ok(gemeinsam) is False
    assert "Ollama" in module.leftovers_in_tool(tools / "rephraser")
    (tools / "rephraser" / "app" / "local_runtime.py").write_text(
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return False  # LLP-FOUNDRY-TOR: kein Ollama\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_runtime_modus"] == "kein Ollama"
    blob = module.format_report(data)
    assert "Ollama-Rest:     kein Ollama" in blob
    assert "prueft noch Ollama" not in blob
    assert module.text_foundry_ok(gemeinsam) is True
    (tools / "rephraser" / "app" / "local_runtime.py").write_text(
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return False  # LLP-FOUNDRY-TOR: kein Ollama\n"
        "    opener.open(base_url + '/api/tags')\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_runtime_modus"] == "noch Ollama"
    assert "Ollama" in module.leftovers_in_tool(tools / "rephraser")


def test_kurz_gibt_nur_statuszeile() -> None:
    module = _load()
    assert module.main(["--kurz"]) == 0


def _foundry_desktop(tools: Path) -> None:
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True, exist_ok=True)
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
    ps1.parent.mkdir(parents=True, exist_ok=True)
    ps1.write_text(
        "# LLP-FOUNDRY-TOR\nStart-Process text_verbessern_foundry\\Starten.bat\n",
        encoding="utf-8",
    )


def test_report_foundry_desktop_aber_mistral_pipeline_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "pipeline.py").write_text(
        "def get_provider(name):\n"
        "    if name == 'mistral':\n"
        "        return LocalMistralProvider()\n"
        "    if name == 'auto':\n"
        "        return HybridLocalProvider()\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_modus"] == "Foundry"
    assert data["text_pipeline_modus"] == "noch Mistral"
    blob = module.format_report(data)
    assert "pipeline.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True


def test_report_foundry_aber_lokal_provider_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "providers" / "local.py").write_text(
        "class LocalRuleProvider:\n"
        "    def rewrite(self, text):\n"
        "        return text\n",
        encoding="utf-8",
    )
    (tools / "rephraser" / "app" / "providers" / "fast_editor.py").write_text(
        "class FastEditorialProvider:\n"
        "    def rewrite(self, text):\n"
        "        return text\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_local_rules_modus"] == "noch Regeln"
    assert data["text_fast_editor_modus"] == "noch Regeln"
    blob = module.format_report(data)
    assert "local.py" in blob
    assert "fast_editor.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    reasons = module.leftovers_in_tool(tools / "rephraser")
    assert "Lokal-Regeln" in reasons
    assert "Schnell-Editor" in reasons


def test_report_foundry_aber_schnell_editor_regelaufruf_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "providers" / "fast_editor.py").write_text(
        "class FastEditorialProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        "        raise RuntimeError(\n"
        '            "Schnell-Editor ist abgeschaltet. Nur Foundry. '
        'Der Text bleibt unverändert."\n'
        "        )  # LLP-FOUNDRY-TOR\n"
        "        cleaned = LocalRuleProvider().rewrite(text, constraints, options)\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_fast_editor_modus"] == "noch Regeln"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Schnell-Editor" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_desktop_aber_regeln_pipeline_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "pipeline.py").write_text(
        "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider\n"
        "def get_provider(name):\n"
        "    if name == 'rules':\n"
        "        return LocalRuleProvider()\n"
        "    if name == 'foundry':\n"
        "        return FoundryEditorialProvider()\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_pipeline_modus"] == "noch Regeln"
    blob = module.format_report(data)
    assert "pipeline.py" in blob
    assert "Regeln" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Pipeline" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_desktop_aber_regeln_name_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "pipeline.py").write_text(
        "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider\n"
        "def get_provider(name):\n"
        "    return FoundryEditorialProvider()\n"
        "    applied_provider = LocalRuleProvider.name\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_pipeline_modus"] == "noch Regeln"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Pipeline" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_desktop_aber_regel_fallback_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "app" / "pipeline.py").write_text(
        "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider\n"
        "def get_provider(name):\n"
        "    return FoundryEditorialProvider()\n"
        "def run_pipeline(text, options=None):\n"
        "    rewritten = LocalRuleProvider().rewrite(text, semantics, selected)\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_pipeline_modus"] == "noch Regeln"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Pipeline" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_desktop_aber_hybrid_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    hybrid = tools / "rephraser" / "app" / "providers" / "hybrid.py"
    hybrid.write_text(
        "from app.providers.mistral_provider import LocalMistralProvider\n"
        "class HybridLocalProvider:\n"
        "    def __init__(self):\n"
        "        self.mistral = LocalMistralProvider()\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_hybrid_modus"] == "noch Mistral"
    blob = module.format_report(data)
    assert "hybrid.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True


def test_report_foundry_desktop_aber_pyproject_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "pyproject.toml").write_text(
        'dependencies = ["fastapi>=0.115", "pydantic>=2.8", "uvicorn>=0.30"]\n'
        'ui = ["streamlit>=1.37"]\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_pyproject_modus"] == "noch API"
    blob = module.format_report(data)
    assert "pyproject.toml" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True


def test_report_foundry_aber_offline_html_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    html = tools / "rephraser" / "web" / "index.html"
    html.parent.mkdir(parents=True)
    html.write_text(
        "<html><body><!-- LLP-FOUNDRY-TOR -->"
        "<p>Kanzlei-Weg text_verbessern_foundry</p>"
        '<script src="./app.js"></script></body></html>\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_web_html"] is not None
    blob = module.format_report(data)
    assert "Offline-HTML" in blob or "index.html" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert "Offline-HTML" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_offline_js_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    js = tools / "rephraser" / "web" / "app.js"
    js.parent.mkdir(parents=True)
    js.write_text("export function startEditor() {}\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_web_js"] is not None
    blob = module.format_report(data)
    assert "Offline-JS" in blob or "app.js" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Offline-JS" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_startbare_sicherung_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    alt = tools / "rephraser" / "web" / "TextVerbessern-Browser.html.llp-alt"
    alt.parent.mkdir(parents=True)
    alt.write_text("<html><body><script>startEditor()</script></body></html>\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_launchable_backup"] is not None
    blob = module.format_report(data)
    assert "Sicherung" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Sicherung-startbar" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_alte_cli_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    main = tools / "rephraser" / "app" / "main.py"
    main.write_text(
        "def cli(argv=None):\n"
        "    result = run_pipeline(text, options)\n"
        "    return 0\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_cli_modus"] == "noch CLI"
    blob = module.format_report(data)
    assert "Kommandozeile" in blob or "CLI" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "CLI" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_bewertung_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    evaluation = tools / "rephraser" / "app" / "evaluation.py"
    evaluation.write_text(
        "from app.pipeline import run_pipeline\n"
        "def evaluate_case(case):\n"
        "    return run_pipeline(case.input)\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_evaluation_modus"] == "noch Bewertung"
    blob = module.format_report(data)
    assert "evaluation.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Bewertung" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_desktop_pipeline_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.write_text(
        desktop.read_text(encoding="utf-8")
        + "\n            result = run_pipeline(source, options)\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_desktop_pipeline"] is not None
    blob = module.format_report(data)
    assert "Pipeline" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Desktop-Pipeline" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_desktop_selbsttest_pipeline_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.write_text(
        desktop.read_text(encoding="utf-8")
        + "\ndef run_self_test() -> dict[str, object]:\n"
        + '    return {"ok": False, "grund": "foundry"}  # LLP-FOUNDRY-TOR: kein Selbsttest\n'
        + '    result = run_pipeline(source, TransformOptions(provider="rules", rewrite_strength="light"))\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_desktop_pipeline"] is not None
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Desktop-Pipeline" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_lokale_desktop_fassung_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.write_text(
        desktop.read_text(encoding="utf-8")
        + "\nFoundry derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt.\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_local_fallback"] is not None
    blob = module.format_report(data)
    assert "Regelfassung" in blob or "lokale Fassung" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Regelfassung" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_desktop_selbsttest_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.write_text(
        desktop.read_text(encoding="utf-8")
        + '\ndef main(argv=None):\n    if "--self-test" in arguments:\n'
        "        report = run_self_test()\n"
        "        return 0\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_self_test"] is not None
    blob = module.format_report(data)
    assert "Selbsttest" in blob
    assert "Regeln" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Selbsttest" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_alte_desktop_run_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    desktop = tools / "rephraser" / "app" / "desktop.py"
    desktop.write_text(
        desktop.read_text(encoding="utf-8")
        + "\nclass DesktopApp:\n    def run(self) -> None:\n        self.root.mainloop()\n",
        encoding="utf-8",
    )
    assert "Oberflaeche" in module.leftovers_in_tool(tools / "rephraser")
    assert module.text_foundry_ok(gemeinsam) is False


def test_report_foundry_aber_alte_anleitung_sicherung_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    alt = tools / "rephraser" / "README.md.llp-alt"
    alt.write_text("Doppelklick auf TextVerbessern.exe. Gründlich mit Mistral.\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_launchable_backup"] is not None
    assert module.text_has_leftovers(data) is True
    assert "Sicherung-startbar" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_anhang_ollama_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    anhang = tools / "Anhangpr-fung"
    (anhang / "_Programm" / "anhangspruefer" / "compliance" / "knowledge").mkdir(parents=True)
    (anhang / "Starten.bat").write_text("@echo off\n", encoding="utf-8")
    matcher = (
        anhang
        / "_Programm"
        / "anhangspruefer"
        / "compliance"
        / "knowledge"
        / "llm_matcher.py"
    )
    matcher.write_text(
        'req = urllib.request.Request(self.base_url + "/api/generate", body)\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["anhang_ollama"] is not None
    blob = module.format_report(data)
    assert "Anhang-Ollama" in blob
    assert "Ollama-Client" in blob
    assert module.text_has_leftovers(data) is True


def test_report_foundry_aber_anhang_mistral_default_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    anhang = tools / "Anhangpr-fung"
    (anhang / "_Programm" / "anhangspruefer" / "compliance" / "knowledge").mkdir(parents=True)
    (anhang / "Starten.bat").write_text("@echo off\n", encoding="utf-8")
    matcher = (
        anhang
        / "_Programm"
        / "anhangspruefer"
        / "compliance"
        / "knowledge"
        / "llm_matcher.py"
    )
    matcher.write_text('DEFAULT_MODEL = "mistral"\n', encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["anhang_ollama"] is not None
    assert module.text_has_leftovers(data) is True


def test_report_foundry_aber_anhang_ollama_port_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    anhang = tools / "Anhangpr-fung"
    (anhang / "_Programm" / "anhangspruefer" / "compliance" / "knowledge").mkdir(parents=True)
    (anhang / "Starten.bat").write_text("@echo off\n", encoding="utf-8")
    matcher = (
        anhang
        / "_Programm"
        / "anhangspruefer"
        / "compliance"
        / "knowledge"
        / "llm_matcher.py"
    )
    matcher.write_text('DEFAULT_BASE_URL = "http://127.0.0.1:11434"\n', encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["anhang_ollama"] is not None
    assert module.text_has_leftovers(data) is True


def test_report_foundry_aber_fremd_ki_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    openai = tools / "rephraser" / "app" / "providers" / "openai_provider.py"
    openai.parent.mkdir(parents=True, exist_ok=True)
    openai.write_text(
        "class OpenAIProvider:\n"
        "    def rewrite(self, text, constraints, options):\n"
        "        return text\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_cloud"] is not None
    blob = module.format_report(data)
    assert "Fremd-KI" in blob
    assert "OpenAI" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Fremd-KI" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_tests_ci_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    workflow = tools / "rephraser" / ".github" / "workflows" / "tests.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("run: python -m app.evaluation\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_workflow"] is not None
    blob = module.format_report(data)
    assert "CI-Rezept" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "CI-Rezept" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_beliebiges_ci_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    workflow = tools / "rephraser" / ".github" / "workflows" / "release.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Release\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_workflow"] is not None
    assert data["text_workflow"].name == "release.yml"
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "CI-Rezept" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_packaging_spec_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    spec = tools / "rephraser" / "packaging" / "TextVerbessern.spec"
    spec.parent.mkdir(parents=True)
    spec.write_text('name="TextVerbessern"\n', encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_spec"] is not None
    assert module.text_foundry_ok(gemeinsam) is False
    assert "Packaging-Spec" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_alte_readme_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "README.md").write_text(
        "# Text verbessern\n\n"
        "Für einen zweiten PC: TextVerbessern.exe doppelklicken.\n"
        "Vor jeder gründlichen Mistral-Bearbeitung …\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_docs_modus"] == "noch alt"
    blob = module.format_report(data)
    assert "README" in blob or "SCHNELLSTART" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Anleitung" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_mistral_export_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    init = tools / "rephraser" / "app" / "providers" / "__init__.py"
    init.write_text(
        "from .mistral_provider import LocalMistralProvider\n"
        '__all__ = ["LocalMistralProvider"]\n',
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_providers_init_modus"] == "noch Mistral"
    blob = module.format_report(data)
    assert "__init__.py" in blob
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Provider-Export" in module.leftovers_in_tool(tools / "rephraser")


def test_report_foundry_aber_original_cmd_ist_nicht_ok(tmp_path: Path) -> None:
    module = _load()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam"
    gemeinsam.mkdir(parents=True)
    _foundry_desktop(tools)
    (tools / "rephraser" / "TEXT VERBESSERN.original.cmd").write_text(
        "@echo off\r\nstart TextVerbessern.exe\r\n",
        encoding="utf-8",
    )
    data = module.report(gemeinsam)
    assert data["text_original_cmd"] is not None
    blob = module.format_report(data)
    assert "original.cmd" in blob.lower()
    assert module.text_foundry_ok(gemeinsam) is False
    assert module.text_has_leftovers(data) is True
    assert "Original-CMD" in module.leftovers_in_tool(tools / "rephraser")


def test_leftovers_in_tool_unabhaengig_vom_ordnernamen(tmp_path: Path) -> None:
    module = _load()
    tool = tmp_path / "rephraser-kopie"
    desktop = tool / "app" / "desktop.py"
    desktop.parent.mkdir(parents=True)
    desktop.write_text(
        'MODE_STRONG = "Gründlich mit Mistral (bis 45 s)"\n'
        'return "rules+mistral-local", "substantial"\n',
        encoding="utf-8",
    )
    (tool / "app" / "pipeline.py").write_text(
        "        return LocalMistralProvider()\n",
        encoding="utf-8",
    )
    reasons = module.leftovers_in_tool(tool)
    assert "Oberflaeche" in reasons
    assert "Pipeline" in reasons
    assert module.leftovers_in_tool(tmp_path / "leer") == []


def test_rest_ohne_nachbar_ist_ok(tmp_path: Path) -> None:
    module = _load()
    gemeinsam = tmp_path / "_Gemeinsam"
    gemeinsam.mkdir()
    assert module.text_has_leftovers(start=gemeinsam) is False


def test_rest_mit_mistral_ist_nicht_ok(tmp_path: Path) -> None:
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
    assert module.text_has_leftovers(start=gemeinsam) is True


def test_main_rest_ohne_leftover(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "text_has_leftovers", lambda data=None, start=None: False)
    assert module.main(["--rest"]) == 0


def test_main_rest_mit_leftover(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "text_has_leftovers", lambda data=None, start=None: True)
    assert module.main(["--rest"]) == 2
