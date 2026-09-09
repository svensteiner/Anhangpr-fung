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
    (tools / "Pseudokrat" / "START.bat").parent.mkdir(parents=True)
    (tools / "Pseudokrat" / "START.bat").write_text("@echo off\n", encoding="utf-8")
    data = module.report(gemeinsam)
    assert data["text_modus"] == "noch Mistral"
    assert data["pseudokrat"] is not None
    blob = module.format_report(data)
    assert "noch Mistral" in blob
    assert "Foundry-Seite" in blob
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
    data = module.report(gemeinsam)
    assert data["text_modus"] == "Foundry"
    assert "noch Mistral" not in module.format_report(data)
    assert module.text_foundry_ok(gemeinsam) is True


def test_kurz_gibt_nur_statuszeile() -> None:
    module = _load()
    assert module.main(["--kurz"]) == 0
