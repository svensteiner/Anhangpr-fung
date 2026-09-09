"""Stellt Text verbessern auf den zentralen Foundry-Layer um.

GitHub-Push nach rephraser ist von hier nicht möglich. Einmal auf dem
Server neben dem Tool-Ordner ausführen (Anwenden.bat). Idempotent.
Gründlich nur bei Foundry – kein stiller Wechsel auf Mistral/Ollama.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "foundry_provider.py"
SHARED = HERE.parent
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from pruefen_tools import (
    BACKUP_NOTE_MARK,
    PARK_DIR_NAME,
    is_launchable_backup,
    leftovers_in_tool,
)

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
    leftover = leftovers_in_tool(tool_root)
    if leftover:
        return False, (
            "Anwenden hat nicht alles umgestellt: "
            + ", ".join(leftover)
            + ". Bitte Pruefen.bat."
        )
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

    streamlit = tool_root / STREAMLIT_REL
    if streamlit.is_file():
        _disable_streamlit(streamlit)
        done.append(str(streamlit))
    pyproject = tool_root / PYPROJECT_REL
    if pyproject.is_file():
        _patch_pyproject(pyproject)
        done.append(str(pyproject))

    launcher = _patch_launcher(tool_root)
    if launcher is not None:
        done.append(str(launcher))

    done.extend(_park_exe(tool_root))
    done.extend(_park_packaging(tool_root))
    done.extend(_park_portable_workflow(tool_root))
    done.extend(_park_build_scripts(tool_root))
    ps1 = _patch_windows_start(tool_root)
    if ps1 is not None:
        done.append(str(ps1))
    done.extend(_write_start_notes(tool_root))
    extra = _patch_leftover_docs(tool_root)
    done.extend(extra)
    done.extend(_park_web_scripts(tool_root))
    done.extend(_neutralize_launchable_backups(tool_root))
    hybrid = tool_root / "app" / "providers" / "hybrid.py"
    if hybrid.is_file():
        _patch_hybrid(hybrid)
        done.append(str(hybrid))
    providers_init = tool_root / "app" / "providers" / "__init__.py"
    if providers_init.is_file():
        _patch_providers_init(providers_init)
        done.append(str(providers_init))
    runtime = tool_root / "app" / "local_runtime.py"
    if runtime.is_file():
        _patch_local_runtime(runtime)
        done.append(str(runtime))
    mistral = tool_root / "app" / "providers" / "mistral_provider.py"
    if mistral.is_file():
        _patch_mistral_provider(mistral)
        done.append(str(mistral))

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

SPEC_REL = Path("packaging") / "TextVerbessern.spec"
WORKFLOW_REL = Path(".github") / "workflows" / "windows-portable.yml"
BUILD_RELS = (
    Path("scripts") / "build_browser_standalone.py",
)
EXE_REL_DIRS = (
    Path("."),
    Path("dist"),
    Path("dist") / "TextVerbessern",
    Path("packaging") / "output",
    Path("release"),
)
STREAMLIT_REL = Path("app") / "ui" / "streamlit_app.py"
STREAMLIT_STUB = (
    "raise SystemExit(\n"
    '    "Bitte Desktop Text verbessern oder '
    '_Gemeinsam\\\\text_verbessern_foundry\\\\Starten.bat. "\n'
    '    "Die Streamlit-Oberflaeche startet nicht. Nur Foundry, kein Mistral."\n'
    ")  # LLP-FOUNDRY-TOR\n"
)
PYPROJECT_REL = Path("pyproject.toml")


def _park_file(path: Path) -> Path | None:
    if not path.is_file():
        return None
    parked = path.with_name(path.name + ".llp-alt")
    if not parked.is_file():
        parked.write_bytes(path.read_bytes())
    path.unlink()
    return parked


def _patch_launcher(tool_root: Path) -> Path | None:
    """Direktklick auf TEXT VERBESSERN.cmd: Foundry-Tor, kein Mistral."""
    cmd = tool_root / LAUNCHER_NAME
    parked = tool_root / f"{LAUNCHER_NAME}.llp-alt"
    if cmd.is_file():
        current = cmd.read_text(encoding="utf-8", errors="replace")
        if LAUNCHER_MARK not in current and not parked.is_file():
            parked.write_text(current, encoding="utf-8")
    _park_file(tool_root / LAUNCHER_BACKUP)
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


NOTE_MARK = "LLP-FOUNDRY-TOR"
SCHNELLSTART_NAME = "SCHNELLSTART.md"
LIESMICH_NAME = "LIESMICH-FOUNDRY.txt"
START_NOTE = """LLP-FOUNDRY-TOR
Text verbessern – nur Foundry (Büro-KI)

Das Programm bleibt auf dem Server. Nicht auf den PC kopieren.
Keine EXE, kein Mistral, kein Streamlit.

Start:
  Desktop „Text verbessern“
  oder  _Gemeinsam\\text_verbessern_foundry\\Starten.bat
  oder  Tools_starten.bat, Punkt 2

Nur Microsoft Foundry (llp_ai). Ist Foundry aus,
bleibt der Text unverändert – das Tool sagt Bescheid.

Schlüssel nur in llp_ai\\.env.
"""


def _backup_then_write(path: Path, content: str) -> Path:
    if path.is_file():
        current = path.read_text(encoding="utf-8", errors="replace")
        if NOTE_MARK in current and current == content:
            return path
        backup = path.with_name(path.name + ".llp-alt")
        if NOTE_MARK not in current and not backup.is_file():
            backup.write_text(current, encoding="utf-8")
    path.write_text(content, encoding="utf-8")
    return path


def _write_start_notes(tool_root: Path) -> list[str]:
    """Offizielle SCHNELLSTART.md zeigt sonst EXE/Mistral/Streamlit."""
    written: list[str] = []
    schnell = tool_root / SCHNELLSTART_NAME
    if schnell.is_file() or (tool_root / "TEXT VERBESSERN.cmd").is_file():
        written.append(str(_backup_then_write(schnell, START_NOTE)))
    written.append(str(_backup_then_write(tool_root / LIESMICH_NAME, START_NOTE)))
    lies = tool_root / "LIESMICH.txt"
    if lies.is_file():
        written.append(str(_backup_then_write(lies, START_NOTE)))
    return written


ENV_EXAMPLE = """# LLP-FOUNDRY-TOR
# Schluessel nur in ..\\_Gemeinsam\\llp_ai\\.env (Microsoft Foundry).
# Kein Ollama, kein Mistral, keine eigenen Cloud-Schluessel hier.
"""

def _patch_leftover_docs(tool_root: Path) -> list[str]:
    """README, .env.example und CLI zeigen sonst noch Mistral/Ollama."""
    written: list[str] = []
    env = tool_root / ".env.example"
    if env.is_file():
        written.append(str(_backup_then_write(env, ENV_EXAMPLE)))
    readme = tool_root / "README.md"
    if readme.is_file():
        written.append(str(_backup_then_write(readme, START_NOTE)))
    written.extend(_patch_web_html(tool_root))
    cli = tool_root / "app" / "main.py"
    if cli.is_file():
        text = cli.read_text(encoding="utf-8", errors="replace")
        updated = _replace_all_if_present(
            text,
            'choices=["fast-editor", "rules", "mistral-local"]',
            'choices=["fast-editor", "rules", "foundry"]',
        )
        updated = _disable_fastapi(updated)
        updated = _disable_cli(updated)
        if updated != text:
            bak = cli.with_name(cli.name + ".llp-alt")
            if not bak.is_file():
                bak.write_text(text, encoding="utf-8")
            cli.write_text(updated, encoding="utf-8")
            written.append(str(cli))
    return written


FOUNDRY_UVICORN_HINT = (
    "    raise HTTPException(\n"
    "        status_code=503,\n"
    "        detail=(\n"
    '            "Bitte Desktop Text verbessern oder "\n'
    '            "_Gemeinsam\\\\text_verbessern_foundry\\\\Starten.bat. "\n'
    '            "uvicorn startet nicht. Nur Foundry, kein Mistral."\n'
    "        ),\n"
    "    )  # LLP-FOUNDRY-TOR"
)


def _disable_fastapi(text: str) -> str:
    """uvicorn app.main:app darf keine API mehr anbieten."""
    text = _replace_all_if_present(
        text,
        "def transform(request: TransformRequest) -> TransformResult:\n"
        "    try:\n"
        "        return run_pipeline(request.text, request.options)\n"
        "    except ProviderError as error:\n"
        "        raise HTTPException(status_code=503, detail=str(error)) from error",
        "def transform(request: TransformRequest) -> TransformResult:\n"
        + FOUNDRY_UVICORN_HINT,
    )
    text = _replace_all_if_present(
        text,
        "def transform_text(request: TransformRequest) -> str:\n"
        "    return transform(request).rewritten_text",
        "def transform_text(request: TransformRequest) -> str:\n"
        + FOUNDRY_UVICORN_HINT,
    )
    text = _replace_all_if_present(
        text,
        "def health() -> dict[str, str]:\n"
        '    return {"status": "ok", "default_provider": "fast-editor"}',
        "def health() -> dict[str, str]:\n"
        + FOUNDRY_UVICORN_HINT,
    )
    return text


CLI_STUB = (
    "def cli(argv: list[str] | None = None) -> int:\n"
    "    raise SystemExit(\n"
    '        "Bitte Desktop Text verbessern oder "\n'
    '        "_Gemeinsam\\\\text_verbessern_foundry\\\\Starten.bat. "\n'
    '        "Die alte CLI startet nicht. Nur Foundry, kein Mistral."\n'
    "    )  # LLP-FOUNDRY-TOR\n"
)


def _disable_cli(text: str) -> str:
    """python -m app.main und editorial-transformer dürfen nicht mehr umschreiben."""
    if "Die alte CLI startet nicht" in text:
        return text
    start = text.find("def cli(")
    if start == -1:
        return text
    end = text.find('if __name__ == "__main__":', start)
    if end == -1:
        return text[:start] + CLI_STUB
    return text[:start] + CLI_STUB + "\n\n" + text[end:]


BACKUP_NOTE = (
    "LLP-FOUNDRY-TOR\n"
    f"{BACKUP_NOTE_MARK}.\n"
    "Bitte Desktop Text verbessern oder "
    "_Gemeinsam\\text_verbessern_foundry\\Starten.bat.\n"
    "Nur Foundry, kein Mistral.\n"
)


def _neutralize_launchable_backups(tool_root: Path) -> list[str]:
    """HTML/PS1/CMD/JS-.llp-alt nebenan nicht per Doppelklick startbar lassen."""
    written: list[str] = []
    park_root = tool_root / PARK_DIR_NAME
    for path in sorted(tool_root.rglob("*.llp-alt")):
        if not is_launchable_backup(path):
            continue
        rel = path.relative_to(tool_root)
        dest = park_root / f"{rel.as_posix()}.txt"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file():
            dest.write_bytes(path.read_bytes())
        path.write_text(BACKUP_NOTE, encoding="utf-8")
        written.append(str(path))
    return written


WEB_HTML_NAMES = (
    Path("web") / "TextVerbessern-Browser.html",
    Path("web") / "index.html",
)
WEB_STUB = (
    "<!doctype html>\n"
    '<html lang="de"><head><meta charset="utf-8">'
    "<title>Text verbessern – Foundry</title></head>\n"
    "<body>\n"
    "<!-- LLP-FOUNDRY-TOR -->\n"
    "<p>Bitte Desktop „Text verbessern“ oder "
    "_Gemeinsam\\text_verbessern_foundry\\Starten.bat.</p>\n"
    "<p>Die Offline-Datei startet nicht. Nur Foundry, kein Mistral.</p>\n"
    "</body></html>\n"
)


def _patch_web_html(tool_root: Path) -> list[str]:
    written: list[str] = []
    for rel in WEB_HTML_NAMES:
        path = tool_root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if (
            NOTE_MARK in text
            and "Offline-Datei startet nicht" in text
            and "<script" not in text.lower()
        ):
            continue
        bak = path.with_name(path.name + ".llp-alt")
        if not bak.is_file():
            bak.write_text(text, encoding="utf-8")
        path.write_text(WEB_STUB, encoding="utf-8")
        written.append(str(path))
    return written


def _park_web_scripts(tool_root: Path) -> list[str]:
    """app.js/editor.js würden den Offline-Editor wieder starten, wenn HTML zurückgelegt wird."""
    parked: list[str] = []
    web = tool_root / "web"
    if not web.is_dir():
        return parked
    for path in sorted(web.glob("*.js")):
        dest = _park_file(path)
        if dest is not None:
            parked.append(str(dest))
    return parked


def _park_exe(tool_root: Path) -> list[str]:
    """Alte Desktop-EXE zur Seite legen, damit Mistral nicht per Doppelklick startet."""
    parked: list[str] = []
    for rel in EXE_REL_DIRS:
        folder = tool_root / rel
        for name in EXE_NAMES:
            exe = folder / name
            if not exe.is_file():
                continue
            dest = exe.with_name(exe.name + ".llp-alt")
            if dest.exists():
                continue
            exe.rename(dest)
            parked.append(str(dest))
    return parked


def _park_packaging(tool_root: Path) -> list[str]:
    """PyInstaller-Rezept nicht mehr als Startweg liegen lassen."""
    spec = tool_root / SPEC_REL
    if not spec.is_file():
        return []
    dest = spec.with_name(spec.name + ".llp-alt")
    if dest.exists():
        return []
    spec.rename(dest)
    return [str(dest)]


def _park_portable_workflow(tool_root: Path) -> list[str]:
    """CI-Rezept darf keine neue Mistral-EXE bauen."""
    workflow = tool_root / WORKFLOW_REL
    if not workflow.is_file():
        return []
    dest = workflow.with_name(workflow.name + ".llp-alt")
    if dest.exists():
        return []
    workflow.rename(dest)
    return [str(dest)]


def _park_build_scripts(tool_root: Path) -> list[str]:
    """Offline-Build darf keine neue Mistral-HTML als Startweg erzeugen."""
    parked: list[str] = []
    for rel in BUILD_RELS:
        path = tool_root / rel
        if not path.is_file():
            continue
        dest = path.with_name(path.name + ".llp-alt")
        if dest.exists():
            continue
        path.rename(dest)
        parked.append(str(dest))
    return parked


def _patch_local_runtime(path: Path) -> None:
    """Übrige Aufrufe dürfen Ollama nicht mehr anpingen."""
    text = path.read_text(encoding="utf-8")
    if "LLP-FOUNDRY-TOR" in text and "return False" in text:
        return
    text = _replace_all_if_present(
        text,
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n",
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return False  # LLP-FOUNDRY-TOR: kein Ollama\n",
    )
    text = _replace_all_if_present(
        text,
        "def preflight_local_mistral() -> bool:\n",
        "def preflight_local_mistral() -> bool:\n"
        "    return False  # LLP-FOUNDRY-TOR: kein Ollama\n",
    )
    path.write_text(text, encoding="utf-8")


def _patch_mistral_provider(path: Path) -> None:
    """Direktaufruf darf Ollama nicht mehr erreichen."""
    text = path.read_text(encoding="utf-8")
    if "LLP-FOUNDRY-TOR" in text and "LocalMistralProvider ist abgeschaltet" in text:
        return
    text = _replace_all_if_present(
        text,
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n",
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n"
        '        raise RuntimeError(\n'
        '            "LocalMistralProvider ist abgeschaltet. Nur Foundry (llp_ai)."\n'
        "        )  # LLP-FOUNDRY-TOR\n",
    )
    path.write_text(text, encoding="utf-8")


def _patch_hybrid(path: Path) -> None:
    """Direktaufruf von HybridLocalProvider darf nicht mehr Mistral starten."""
    text = path.read_text(encoding="utf-8")
    text = _replace_all_if_present(
        text,
        "from app.providers.mistral_provider import LocalMistralProvider",
        "from app.providers.foundry_provider import FoundryEditorialProvider",
    )
    text = _replace_all_if_present(text, 'name = "rules+mistral-local"', 'name = "rules+foundry"')
    text = _replace_all_if_present(
        text,
        "self.mistral = LocalMistralProvider()",
        "self.foundry = FoundryEditorialProvider()",
    )
    text = _replace_all_if_present(
        text,
        "self.mistral.rewrite",
        "self.foundry.rewrite",
    )
    text = _replace_all_if_present(
        text,
        "followed by a local Mistral editorial pass.",
        "followed by a Foundry editorial pass.",
    )
    path.write_text(text, encoding="utf-8")


def _patch_pipeline(path: Path) -> None:
    pipe = path.read_text(encoding="utf-8")
    foundry_imp = (
        "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider"
    )
    if foundry_imp not in pipe:
        pipe = _ensure_line_after(
            pipe,
            "from .providers.mistral_provider import LocalMistralProvider",
            foundry_imp,
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
    pipe = _replace_all_if_present(
        pipe,
        "        return LocalMistralProvider()",
        "        return FoundryEditorialProvider()",
    )
    pipe = _replace_all_if_present(
        pipe,
        "        return HybridLocalProvider()",
        "        return HybridFoundryProvider()",
    )
    pipe = _replace_all_if_present(
        pipe,
        "select fast-editor, rules, or mistral-local.",
        "select fast-editor, rules, or foundry.",
    )
    pipe = _replace_all_if_present(
        pipe,
        "    except ProviderError as error:\n"
        '        if "mistral" not in active_provider.name:\n'
        "            raise\n"
        "        provider_failure = error\n",
        "    except ProviderError as error:\n"
        "        raise\n",
    )
    pipe = _replace_all_if_present(
        pipe,
        "from .providers.mistral_provider import LocalMistralProvider\n",
        "",
    )
    pipe = _replace_all_if_present(
        pipe,
        "from .providers.hybrid import HybridLocalProvider\n",
        "",
    )
    path.write_text(pipe, encoding="utf-8")


def _patch_providers_init(path: Path) -> None:
    """from app.providers import LocalMistralProvider darf nicht mehr gehen."""
    text = path.read_text(encoding="utf-8")
    if "FoundryEditorialProvider" in text and "LocalMistralProvider" not in text:
        return
    text = _replace_all_if_present(
        text,
        "from .mistral_provider import LocalMistralProvider\n",
        "from .foundry_provider import FoundryEditorialProvider, HybridFoundryProvider\n",
    )
    text = _replace_all_if_present(
        text,
        "from .hybrid import HybridLocalProvider\n",
        "",
    )
    text = _replace_all_if_present(text, '    "LocalMistralProvider",\n', '    "FoundryEditorialProvider",\n')
    text = _replace_all_if_present(text, '    "HybridLocalProvider",\n', '    "HybridFoundryProvider",\n')
    if "LocalMistralProvider" in text or "HybridLocalProvider" in text:
        raise ValueError(
            "app/providers/__init__.py exportiert noch LocalMistralProvider "
            "oder HybridLocalProvider."
        )
    path.write_text(text, encoding="utf-8")


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
        "self.mistral_ready = local_mistral_ready()",
        "self.mistral_ready = foundry_ready()",
    )
    desk = _replace_all_if_present(
        desk,
        '"mistral_available": local_mistral_ready()',
        '"mistral_available": foundry_ready()',
    )
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
    desk = _replace_all_if_present(
        desk,
        "Text war für Mistral zu lang; vollständig lokal schnell bearbeitet.",
        "Text war für Foundry zu lang; vollständig lokal schnell bearbeitet.",
    )
    desk = _replace_all_if_present(
        desk,
        "Mistral hat die Zeitgrenze erreicht; sichere lokale Fassung angezeigt.",
        "Foundry hat die Zeitgrenze erreicht; sichere lokale Fassung angezeigt.",
    )
    desk = _replace_all_if_present(
        desk,
        "Mistral war nicht verfügbar; sichere lokale Grundbereinigung angezeigt.",
        "Foundry war nicht verfügbar; sichere lokale Grundbereinigung angezeigt.",
    )
    desk = _replace_all_if_present(
        desk,
        "✓ Lokales Mistral ist verfügbar.",
        "✓ Foundry (Büro-KI) ist verfügbar.",
    )
    desk = _replace_all_if_present(
        desk,
        "Schnelle lokale Bearbeitung ist verfügbar; Mistral ist optional.",
        "Schnelle lokale Bearbeitung ist verfügbar; gründlich nur mit Foundry.",
    )
    desk = _replace_desktop_main(desk)
    path.write_text(desk, encoding="utf-8")


DESKTOP_MAIN_HINT = (
    '    print("Bitte Desktop Text verbessern oder '
    "_Gemeinsam\\\\text_verbessern_foundry\\\\Starten.bat.\")\n"
    '    print("Die alte Oberflaeche startet nicht. Nur Foundry, kein Mistral.")\n'
    "    return 2"
)

DESKTOP_MAIN_OLD = (
    "    try:\n"
    "        DesktopApp().run()\n"
    "    except Exception as error:\n"
    '        write_diagnostic_event("desktop_fatal", error)\n'
    "        show_startup_error()\n"
    "        return 1\n"
    "    return 0"
)

DESKTOP_MAIN_BROKEN = "    try:\n" + DESKTOP_MAIN_HINT


def _replace_desktop_main(desk: str) -> str:
    """Alte Oberfläche nicht starten – und kein hängendes try: hinterlassen."""
    if DESKTOP_MAIN_OLD in desk:
        return desk.replace(DESKTOP_MAIN_OLD, DESKTOP_MAIN_HINT, 1)
    if DESKTOP_MAIN_BROKEN in desk:
        return desk.replace(DESKTOP_MAIN_BROKEN, DESKTOP_MAIN_HINT, 1)
    if "DesktopApp().run()" in desk:
        return _replace_all_if_present(
            desk,
            "        DesktopApp().run()\n"
            "    except Exception as error:\n"
            '        write_diagnostic_event("desktop_fatal", error)\n'
            "        show_startup_error()\n"
            "        return 1\n"
            "    return 0",
            DESKTOP_MAIN_HINT,
        )
    return desk


def _disable_streamlit(path: Path) -> None:
    """Streamlit darf keine Oberfläche mehr starten."""
    text = path.read_text(encoding="utf-8")
    if (
        "LLP-FOUNDRY-TOR" in text
        and "Streamlit-Oberflaeche startet nicht" in text
        and "import streamlit" not in text
    ):
        return
    bak = path.with_name(path.name + ".llp-alt")
    if not bak.is_file():
        bak.write_text(text, encoding="utf-8")
    path.write_text(STREAMLIT_STUB, encoding="utf-8")


def _patch_pyproject(path: Path) -> None:
    """pip install darf Streamlit und uvicorn nicht nachziehen."""
    text = path.read_text(encoding="utf-8")
    text = _replace_all_if_present(
        text,
        'ui = ["streamlit>=1.37"]',
        'ui = []  # LLP-FOUNDRY-TOR: kein Streamlit',
    )
    text = _replace_all_if_present(
        text,
        'dependencies = ["fastapi>=0.115", "pydantic>=2.8", "uvicorn>=0.30"]',
        'dependencies = ["pydantic>=2.8"]  # LLP-FOUNDRY-TOR: kein uvicorn',
    )
    text = _replace_all_if_present(
        text,
        'editorial-transformer = "app.main:cli"',
        "# editorial-transformer entfernt  # LLP-FOUNDRY-TOR: keine alte CLI",
    )
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    leise = "--leise" in args
    try:
        root = find_tool_root()
        if root is None:
            if leise:
                return 0
            print(
                "Text verbessern nicht gefunden. Bitte Anwenden.bat "
                "im Ordner AI Tools\\_Gemeinsam\\text_verbessern_foundry starten."
            )
            return 2
        ok, msg = apply_foundry(root)
    except (FileNotFoundError, ValueError, OSError) as exc:
        if not leise:
            print(str(exc))
        return 2
    if leise:
        return 0 if ok else 2
    print(msg)
    print("Kein stiller Wechsel auf Mistral/Ollama.")
    print("Ordner:", root)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
