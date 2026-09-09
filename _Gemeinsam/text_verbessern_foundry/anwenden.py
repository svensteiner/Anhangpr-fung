"""Stellt Text verbessern auf den zentralen Foundry-Layer um.

GitHub-Push nach rephraser ist von hier nicht möglich. Einmal auf dem
Server neben dem Tool-Ordner ausführen (Anwenden.bat). Idempotent.
Gründlich nur bei Foundry – kein stiller Wechsel auf Mistral/Ollama.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "foundry_provider.py"

MODE_STRONG_OLD = 'MODE_STRONG = "Gründlich mit Mistral (bis 45 s)"'
MODE_STRONG_NEW = 'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"'
MODE_LABEL_OLD = "Gründlich mit Mistral (bis 45 s)"
MODE_LABEL_NEW = "Gründlich mit Foundry (Büro-KI)"


def _replace_once(text: str, old: str, new: str) -> str:
    if new in text and old not in text:
        return text
    if old not in text:
        raise ValueError(f"Erwartete Stelle fehlt: {old[:80]}")
    return text.replace(old, new, 1)


def _replace_all(text: str, old: str, new: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise ValueError(f"Erwartete Stelle fehlt: {old[:80]}")
    return text.replace(old, new)


def _replace_all_if_present(text: str, old: str, new: str) -> str:
    if old not in text:
        return text
    return text.replace(old, new)


def _ensure_line_after(text: str, marker: str, line: str) -> str:
    if line in text:
        return text
    if marker not in text:
        raise ValueError(f"Marker fehlt: {marker[:80]}")
    return text.replace(marker, marker + "\n" + line, 1)


def find_tool_root(start: Path | None = None) -> Path | None:
    here = start or HERE
    shared = here.parent
    roots = [shared.parent, shared.parent.parent]
    for root in roots:
        for name in ("rephraser", "paraphraser"):
            candidate = root / name
            if (candidate / "app" / "pipeline.py").is_file():
                return candidate
    return None


def apply_foundry(tool_root: Path) -> tuple[bool, str]:
    desktop_path = tool_root / "app" / "desktop.py"
    already = False
    if desktop_path.is_file():
        current = desktop_path.read_text(encoding="utf-8")
        already = (
            MODE_STRONG_NEW in current
            and "rules+foundry" in current
            and "if foundry_ready():" in current
        )
    try:
        apply(tool_root)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return False, str(exc)
    if already:
        return True, "Text verbessern ist bereits auf Foundry umgestellt."
    return True, "Foundry-Anbindung für Text verbessern ist eingerichtet."


def apply(tool_root: Path) -> list[str]:
    done: list[str] = []
    providers = tool_root / "app" / "providers"
    providers.mkdir(parents=True, exist_ok=True)
    dest = providers / "foundry_provider.py"
    shutil.copyfile(SOURCE, dest)
    done.append(str(dest))

    _patch_pipeline(tool_root / "app" / "pipeline.py")
    done.append(str(tool_root / "app" / "pipeline.py"))

    desktop = tool_root / "app" / "desktop.py"
    if desktop.is_file():
        _patch_desktop(desktop)
        done.append(str(desktop))

    streamlit = tool_root / "app" / "ui" / "streamlit_app.py"
    if streamlit.is_file():
        _patch_streamlit(streamlit)
        done.append(str(streamlit))

    launcher = _patch_launcher(tool_root)
    if launcher is not None:
        done.append(str(launcher))

    done.extend(_park_exe(tool_root))
    ps1 = _patch_windows_start(tool_root)
    if ps1 is not None:
        done.append(str(ps1))

    return done


LAUNCHER_NAME = "TEXT VERBESSERN.cmd"
LAUNCHER_BACKUP = "TEXT VERBESSERN.original.cmd"
LAUNCHER_MARK = "LLP-FOUNDRY-TOR"

LAUNCHER_CMD = r"""@echo off
chcp 65001 >nul
rem LLP-FOUNDRY-TOR
title LLP - Text verbessern
cd /d "%~dp0"

if exist "%~dp0..\_Gemeinsam\llp_ai" set "LLP_SHARED_AI_ROOT=%~dp0..\_Gemeinsam"
if not defined LLP_SHARED_AI_ROOT if exist "%~dp0_Gemeinsam\llp_ai" set "LLP_SHARED_AI_ROOT=%~dp0_Gemeinsam"

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY (
    echo  Python wurde nicht gefunden. Bitte die IT rufen.
    pause
    exit /b 1
)

if defined LLP_SHARED_AI_ROOT if exist "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry\anwenden.py" (
    %PY% "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry\anwenden.py"
)

echo  Oeffne Foundry-Seite. Ein Mistral-rephraser wird nicht gestartet.
if defined LLP_SHARED_AI_ROOT if exist "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry\Starten.bat" (
    start "" "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry\Starten.bat"
    exit /b 0
)
echo  Text verbessern (Foundry) nicht gefunden.
echo  Bitte _Gemeinsam\text_verbessern_foundry\Starten.bat doppelklicken.
pause
exit /b 1
"""

EXE_NAMES = (
    "TextVerbessern.exe",
    "TEXT VERBESSERN.exe",
    "rephraser.exe",
)


def _patch_launcher(tool_root: Path) -> Path | None:
    """Direktklick auf TEXT VERBESSERN.cmd: Foundry-Tor, kein Mistral."""
    cmd = tool_root / LAUNCHER_NAME
    backup = tool_root / LAUNCHER_BACKUP
    if cmd.is_file():
        current = cmd.read_text(encoding="utf-8", errors="replace")
        if LAUNCHER_MARK not in current and not backup.is_file():
            backup.write_text(current, encoding="utf-8")
    cmd.write_text(LAUNCHER_CMD, encoding="utf-8")
    return cmd


PS1_NAME = Path("scripts") / "start_windows.ps1"
PS1_MARK = "LLP-FOUNDRY-TOR"
PS1_CMD = r"""# LLP-FOUNDRY-TOR
$ErrorActionPreference = "Stop"
$tool = Split-Path -Parent $PSScriptRoot
$aiTools = Split-Path -Parent $tool
$shared = Join-Path $aiTools "_Gemeinsam"
if (-not (Test-Path -LiteralPath (Join-Path $shared "llp_ai"))) {
    $shared = Join-Path $tool "_Gemeinsam"
}
$start = Join-Path $shared "text_verbessern_foundry\Starten.bat"
Write-Host "Oeffne Foundry-Seite. Ein Mistral-rephraser wird nicht gestartet."
if (Test-Path -LiteralPath $start) {
    Start-Process -FilePath $start
    exit 0
}
Write-Host "Bitte _Gemeinsam\text_verbessern_foundry\Starten.bat doppelklicken."
exit 1
"""


def _patch_windows_start(tool_root: Path) -> Path | None:
    """Streamlit/Mistral-Start über start_windows.ps1 unterbinden."""
    path = tool_root / PS1_NAME
    if not path.is_file():
        return None
    current = path.read_text(encoding="utf-8", errors="replace")
    backup = path.with_name(path.name + ".llp-alt")
    if PS1_MARK not in current and not backup.is_file():
        backup.write_text(current, encoding="utf-8")
    path.write_text(PS1_CMD, encoding="utf-8")
    return path


def _park_exe(tool_root: Path) -> list[str]:
    """Alte Desktop-EXE zur Seite legen, damit Mistral nicht per Doppelklick startet."""
    parked: list[str] = []
    for name in EXE_NAMES:
        exe = tool_root / name
        if not exe.is_file():
            continue
        dest = tool_root / (exe.name + ".llp-alt")
        if dest.exists():
            continue
        exe.rename(dest)
        parked.append(str(dest))
    return parked


def _patch_pipeline(path: Path) -> None:
    pipe = path.read_text(encoding="utf-8")
    pipe = _ensure_line_after(
        pipe,
        "from .providers.mistral_provider import LocalMistralProvider",
        "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider",
    )
    pipe = _ensure_line_after(
        pipe,
        "    if normalized in {\"fast\", \"fast-rules\", \"fast-editor\"}:\n"
        "        return FastEditorialProvider()",
        "    if normalized in {\"foundry\", \"company-ai\"}:\n"
        "        return FoundryEditorialProvider()\n"
        "    if normalized in {\"rules+foundry\"}:\n"
        "        return HybridFoundryProvider()",
    )
    path.write_text(pipe, encoding="utf-8")


def _patch_desktop(path: Path) -> None:
    desk = path.read_text(encoding="utf-8")
    desk = _ensure_line_after(
        desk,
        "from app.pipeline import run_pipeline",
        "from app.providers.foundry_provider import foundry_ready",
    )
    desk = _replace_once(desk, MODE_STRONG_OLD, MODE_STRONG_NEW)
    desk = _replace_once(
        desk,
        '    if mode == MODE_SAFE or not mistral_ready:\n'
        '        return ("rules", "light") if mode == MODE_SAFE else ("fast-editor", "medium")\n'
        '    if mode == MODE_STRONG:\n'
        '        return "rules+mistral-local", "substantial"\n'
        '    return "fast-editor", "medium"',
        '    if mode == MODE_SAFE:\n'
        '        return "rules", "light"\n'
        '    if mode == MODE_STRONG:\n'
        '        return "rules+foundry", "substantial"\n'
        '    return "fast-editor", "medium"',
    )
    desk = _replace_once(
        desk,
        "    if not mistral_ready:\n"
        "        return (MODE_AUTOMATIC, MODE_SAFE)\n"
        "    return (MODE_AUTOMATIC, MODE_SAFE, MODE_STRONG)",
        "    if foundry_ready():\n"
        "        return (MODE_AUTOMATIC, MODE_SAFE, MODE_STRONG)\n"
        "    return (MODE_AUTOMATIC, MODE_SAFE)",
    )
    desk = _replace_once(
        desk,
        '        return "✓ Schnelle lokale Bearbeitung bereit; Mistral beendet noch eine frühere Anfrage."\n'
        "    if mistral_ready:\n"
        '        return "✓ Sofortige Textverbesserung bereit; Mistral ist zusätzlich verfügbar."\n'
        '    return "✓ Sofortige lokale Textverbesserung bereit; Mistral ist optional."',
        '        return "✓ Schnelle lokale Bearbeitung bereit; Foundry beendet noch eine frühere Anfrage."\n'
        "    if foundry_ready():\n"
        '        return "✓ Sofortige Textverbesserung bereit; Foundry (Büro-KI) ist verfügbar."\n'
        '    return "✓ Sofortige lokale Textverbesserung bereit. Gründlich nur mit Foundry."',
    )
    desk = _replace_once(
        desk,
        "        mistral_for_text = local_model_eligible(current_source, self._mistral_can_start())\n"
        "        self.mode_box.configure(values=available_modes(mistral_for_text))\n"
        "        if self.mode.get() == MODE_STRONG and not mistral_for_text:\n"
        "            self.mode.set(MODE_AUTOMATIC)",
        "        thorough_ready = foundry_ready()\n"
        "        self.mode_box.configure(values=available_modes(thorough_ready))\n"
        "        if self.mode.get() == MODE_STRONG and not thorough_ready:\n"
        "            self.mode.set(MODE_AUTOMATIC)",
    )
    desk = _replace_once(
        desk,
        '            self.result_status.configure(text="Lokales Mistral wird kurz geprüft …")\n'
        "            try:\n"
        "                self.root.update_idletasks()\n"
        "            except self.tk.TclError:\n"
        "                return\n"
        "            if not preflight_local_mistral():\n"
        "                self._set_mistral_availability(False)\n"
        '                fallback_kind = "provider_unavailable"',
        '            self.result_status.configure(text="Foundry wird kurz geprüft …")\n'
        "            try:\n"
        "                self.root.update_idletasks()\n"
        "            except self.tk.TclError:\n"
        "                return\n"
        "            if not foundry_ready():\n"
        '                fallback_kind = "provider_unavailable"',
    )
    desk = _replace_all(
        desk,
        'self.processing_active = "mistral" in provider',
        'self.processing_active = "foundry" in provider',
    )
    desk = _replace_all(
        desk,
        'model_request = "mistral" in provider',
        'model_request = "foundry" in provider',
    )
    desk = _replace_all(desk, '"rules+mistral-local"', '"rules+foundry"')
    desk = _replace_all_if_present(
        desk,
        "Mistral derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt",
        "Foundry derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt",
    )
    desk = _replace_all_if_present(
        desk,
        "Das lokale Mistral war vor der Bearbeitung nicht erreichbar",
        "Foundry war vor der Bearbeitung nicht erreichbar",
    )
    path.write_text(desk, encoding="utf-8")


def _patch_streamlit(path: Path) -> None:
    st = path.read_text(encoding="utf-8")
    st = _ensure_line_after(
        st,
        "from app.pipeline import run_pipeline",
        "from app.providers.foundry_provider import foundry_ready",
    )
    st = _replace_all(st, MODE_LABEL_OLD, MODE_LABEL_NEW)
    st = _replace_once(
        st,
        "mistral_ready = cached_local_mistral_ready()",
        "mistral_ready = foundry_ready()",
    )
    st = _replace_all(
        st,
        "Sofortige Textverbesserung bereit; Mistral ist zusätzlich verfügbar.",
        "Sofortige Textverbesserung bereit; Foundry (Büro-KI) ist verfügbar.",
    )
    st = _replace_all(
        st,
        "Sofortige lokale Textverbesserung bereit. Die optionale Mistral-Variante ist nicht verfügbar.",
        "Sofortige lokale Textverbesserung bereit. Gründlich nur mit Foundry (llp_ai).",
    )
    st = _replace_once(
        st,
        "    mistral_for_text = local_model_eligible(st.session_state.source_text, mistral_ready)\n"
        "    mode_choices = (\n"
        f'        ["Schnell verbessern (empfohlen)", "Nur Format bereinigen", "{MODE_LABEL_NEW}"]\n'
        "        if mistral_for_text\n"
        '        else ["Schnell verbessern (empfohlen)", "Nur Format bereinigen"]\n'
        "    )",
        "    mistral_for_text = foundry_ready()\n"
        "    mode_choices = (\n"
        f'        ["Schnell verbessern (empfohlen)", "Nur Format bereinigen", "{MODE_LABEL_NEW}"]\n'
        "        if mistral_for_text\n"
        '        else ["Schnell verbessern (empfohlen)", "Nur Format bereinigen"]\n'
        "    )",
    )
    st = _replace_once(
        st,
        "        with st.spinner(\"Lokales Mistral wird kurz geprüft …\"):\n"
        "            mistral_preflight_failed = not preflight_local_mistral()",
        "        with st.spinner(\"Foundry wird kurz geprüft …\"):\n"
        "            mistral_preflight_failed = not foundry_ready()",
    )
    st = _replace_all(st, 'provider = "rules+mistral-local"', 'provider = "rules+foundry"')
    st = _replace_all(st, '"rules+mistral-local"', '"rules+foundry"')
    st = _replace_all(st, '"mistral" in provider', '"foundry" in provider')
    st = _replace_all(
        st,
        "Gründliche lokale Mistral-Überarbeitung läuft – höchstens 45 Sekunden.",
        "Gründliche Foundry-Überarbeitung läuft.",
    )
    st = _replace_all(
        st,
        "Mistral derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt.",
        "Foundry derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt.",
    )
    st = _replace_all(
        st,
        "Stiloptionen gelten nur für die optionale gründliche Mistral-Bearbeitung.",
        "Stiloptionen gelten nur für die gründliche Foundry-Bearbeitung.",
    )
    path.write_text(st, encoding="utf-8")


def main() -> int:
    try:
        root = find_tool_root()
        if root is None:
            print(
                "Text verbessern nicht gefunden. Bitte Anwenden.bat "
                "im Ordner AI Tools\\_Gemeinsam\\text_verbessern_foundry starten."
            )
            return 2
        ok, msg = apply_foundry(root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc))
        return 2
    print(msg)
    print("Kein stiller Wechsel auf Mistral/Ollama.")
    print("Ordner:", root)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
