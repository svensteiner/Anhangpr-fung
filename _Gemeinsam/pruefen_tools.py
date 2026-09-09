"""Share-Check: Foundry und welche Tools daneben liegen – ohne Schlüssel."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from llp_ai.company_ai import describe_status

TOOL_NAMES = {
    "anhang": ("Anhangspruefung", "Anhangpr-fung"),
    "text": ("rephraser", "paraphraser"),
    "pseudo": ("Pseudokrat",),
}


def search_roots(start: Path | None = None) -> list[Path]:
    here = start or HERE
    roots = [here.parent, here.parent.parent]
    seen: list[Path] = []
    for root in roots:
        if root not in seen:
            seen.append(root)
    return seen


def _first_existing(root: Path, names: tuple[str, ...], rel: str) -> Path | None:
    for name in names:
        candidate = root / name / rel
        if candidate.is_file():
            return candidate
    return None


def find_anhang(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["anhang"], "Starten.bat")
        if found is not None:
            return found
        if (root / "Starten.bat").is_file() and (root / "app.py").is_file():
            return root / "Starten.bat"
    return None


def find_text_desktop(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/desktop.py")
        if found is not None:
            return found
    return None


def find_text_cmd(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "TEXT VERBESSERN.cmd")
        if found is not None:
            return found
    return None


def find_text_original_cmd(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "TEXT VERBESSERN.original.cmd")
        if found is not None:
            return found
    return None


def text_cmd_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text:
        return "Foundry-Tor"
    return "noch alt"


EXE_REL_DIRS = (
    Path("."),
    Path("dist"),
    Path("dist") / "TextVerbessern",
    Path("packaging") / "output",
    Path("release"),
)


def find_live_text_exe(roots: list[Path]) -> Path | None:
    for root in roots:
        for name in TOOL_NAMES["text"]:
            base = root / name
            for rel in EXE_REL_DIRS:
                folder = base / rel
                for exe_name in ("TextVerbessern.exe", "TEXT VERBESSERN.exe", "rephraser.exe"):
                    candidate = folder / exe_name
                    if candidate.is_file():
                        return candidate
    return None


def find_local_runtime(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/local_runtime.py")
        if found is not None:
            return found
    return None


def local_runtime_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text and "kein Ollama" in text:
        return "kein Ollama"
    if "11434" in text or "MISTRAL_BASE_URL" in text:
        return "noch Ollama"
    return "nicht erkannt"


def find_mistral_provider(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/providers/mistral_provider.py")
        if found is not None:
            return found
    return None


def mistral_provider_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text and "LocalMistralProvider ist abgeschaltet" in text:
        return "abgeschaltet"
    if "11434" in text or "/api/generate" in text:
        return "noch Ollama"
    return "nicht erkannt"


def find_providers_init(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/providers/__init__.py")
        if found is not None:
            return found
    return None


def providers_init_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LocalMistralProvider" in text or "HybridLocalProvider" in text:
        return "noch Mistral"
    if "FoundryEditorialProvider" in text:
        return "Foundry"
    return "nicht erkannt"


def find_foundry_provider(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/providers/foundry_provider.py")
        if found is not None:
            return found
    return None


def find_streamlit_app(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/ui/streamlit_app.py")
        if found is not None:
            return found
    return None


def streamlit_app_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if (
        "LLP-FOUNDRY-TOR" in text
        and "Streamlit-Oberflaeche startet nicht" in text
        and "import streamlit" not in text
    ):
        return "abgeschaltet"
    if "import streamlit" in text:
        return "noch Streamlit"
    return "nicht erkannt"


def find_text_startskript(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "scripts/start_windows.ps1")
        if found is not None:
            return found
    return None


def text_startskript_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text and "streamlit" not in text.lower():
        return "Foundry-Tor"
    if "streamlit" in text.lower():
        return "noch Streamlit"
    return "nicht erkannt"


def find_text_api(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/main.py")
        if found is not None:
            return found
    return None


def find_text_pipeline(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/pipeline.py")
        if found is not None:
            return found
    return None


def pipeline_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    still_mistral = "return LocalMistralProvider()" in text
    still_hybrid = "return HybridLocalProvider()" in text
    foundry = "FoundryEditorialProvider" in text and "HybridFoundryProvider" in text
    if still_mistral or still_hybrid:
        return "noch Mistral"
    if foundry:
        return "Foundry"
    return "nicht erkannt"


def find_text_hybrid(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/providers/hybrid.py")
        if found is not None:
            return found
    return None


def hybrid_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LocalMistralProvider()" in text:
        return "noch Mistral"
    if "FoundryEditorialProvider" in text:
        return "Foundry"
    return "nicht erkannt"


START_DOC_RELS = ("README.md", "SCHNELLSTART.md", "LIESMICH.txt")
WEB_HTML_RELS = (
    Path("web") / "TextVerbessern-Browser.html",
    Path("web") / "index.html",
)
SPEC_REL = Path("packaging") / "TextVerbessern.spec"
BUILD_REL = Path("scripts") / "build_browser_standalone.py"
WORKFLOW_REL = Path(".github") / "workflows" / "windows-portable.yml"


def web_html_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if (
        "LLP-FOUNDRY-TOR" in text
        and "Offline-Datei startet nicht" in text
        and "<script" not in text.lower()
    ):
        return "abgeschaltet"
    return "noch alt"


def find_live_web_html(roots: list[Path]) -> Path | None:
    for root in roots:
        for name in TOOL_NAMES["text"]:
            for rel in WEB_HTML_RELS:
                candidate = root / name / rel
                if candidate.is_file() and web_html_modus(candidate) == "noch alt":
                    return candidate
    return None


def find_live_spec(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], str(SPEC_REL))
        if found is not None:
            return found
    return None


def find_live_build_script(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], str(BUILD_REL))
        if found is not None:
            return found
    return None


def find_live_portable_workflow(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], str(WORKFLOW_REL))
        if found is not None:
            return found
    return None


def leftover_start_doc_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text:
        return "Foundry"
    low = text.lower()
    if any(
        marker in low
        for marker in (
            "textverbessern.exe",
            "gründlich mit mistral",
            "mistral-bearbeitung",
            "portable windows",
            "streamlit",
            "ollama",
        )
    ):
        return "noch alt"
    return "nicht erkannt"


def start_docs_modus(roots: list[Path] | None = None, tool_root: Path | None = None) -> str:
    modes: list[str] = []
    if tool_root is not None:
        for name in START_DOC_RELS:
            path = tool_root / name
            modes.append(leftover_start_doc_modus(path if path.is_file() else None))
    elif roots is not None:
        for name in START_DOC_RELS:
            found = None
            for root in roots:
                found = _first_existing(root, TOOL_NAMES["text"], name)
                if found is not None:
                    break
            modes.append(leftover_start_doc_modus(found))
    if any(mode == "noch alt" for mode in modes):
        return "noch alt"
    if any(mode == "nicht erkannt" for mode in modes):
        return "nicht erkannt"
    if any(mode == "Foundry" for mode in modes):
        return "Foundry"
    return "nicht gefunden"


def find_text_pyproject(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "pyproject.toml")
        if found is not None:
            return found
    return None


def pyproject_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    raw_uvicorn = "uvicorn>=" in text or '"uvicorn' in text
    raw_streamlit = "streamlit>=" in text or '"streamlit' in text
    marked = "LLP-FOUNDRY-TOR" in text and "kein uvicorn" in text
    if raw_uvicorn:
        return "noch API"
    if raw_streamlit:
        return "noch Streamlit"
    if marked:
        return "abgeschaltet"
    return "nicht erkannt"


def text_api_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text and "uvicorn startet nicht" in text:
        if 'default_provider": "fast-editor"' in text:
            return "noch API"
        if "return run_pipeline(request.text, request.options)" in text:
            return "noch API"
        return "abgeschaltet"
    if "FastAPI" in text or "uvicorn" in text or "default_provider" in text:
        return "noch API"
    return "nicht erkannt"


def find_pseudokrat(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["pseudo"], "START.bat")
        if found is not None:
            return found
    return None


def text_verbessern_modus(desktop: Path | None) -> str:
    if desktop is None:
        return "nicht gefunden"
    text = desktop.read_text(encoding="utf-8", errors="replace")
    foundry = "Gründlich mit Foundry" in text and "rules+foundry" in text
    mistral = "Gründlich mit Mistral" in text or "rules+mistral-local" in text
    if foundry and not mistral:
        return "Foundry"
    if mistral:
        return "noch Mistral"
    return "nicht erkannt"


def report(start: Path | None = None) -> dict[str, object]:
    roots = search_roots(start)
    desktop = find_text_desktop(roots)
    startskript = find_text_startskript(roots)
    cmd = find_text_cmd(roots)
    original_cmd = find_text_original_cmd(roots)
    exe = find_live_text_exe(roots)
    provider = find_foundry_provider(roots)
    runtime = find_local_runtime(roots)
    mistral_provider = find_mistral_provider(roots)
    streamlit_app = find_streamlit_app(roots)
    api = find_text_api(roots)
    pipeline = find_text_pipeline(roots)
    hybrid = find_text_hybrid(roots)
    pyproject = find_text_pyproject(roots)
    providers_init = find_providers_init(roots)
    modus = text_verbessern_modus(desktop)
    start_modus = text_startskript_modus(startskript)
    cmd_modus = text_cmd_modus(cmd)
    runtime_modus = local_runtime_modus(runtime)
    mistral_modus = mistral_provider_modus(mistral_provider)
    streamlit_modus = streamlit_app_modus(streamlit_app)
    api_modus = text_api_modus(api)
    pipeline_mode = pipeline_modus(pipeline)
    hybrid_mode = hybrid_modus(hybrid)
    pyproject_mode = pyproject_modus(pyproject)
    providers_init_mode = providers_init_modus(providers_init)
    docs_mode = start_docs_modus(roots=roots)
    web_html = find_live_web_html(roots)
    spec = find_live_spec(roots)
    build = find_live_build_script(roots)
    workflow = find_live_portable_workflow(roots)
    return {
        "foundry": describe_status(),
        "anhang": find_anhang(roots),
        "text_desktop": desktop,
        "text_modus": modus,
        "text_startskript": startskript,
        "text_start": start_modus,
        "text_cmd": cmd,
        "text_cmd_modus": cmd_modus,
        "text_original_cmd": original_cmd,
        "text_exe": exe,
        "text_provider": provider,
        "text_runtime": runtime,
        "text_runtime_modus": runtime_modus,
        "text_mistral_provider": mistral_provider,
        "text_mistral_modus": mistral_modus,
        "text_streamlit": streamlit_app,
        "text_streamlit_modus": streamlit_modus,
        "text_api": api,
        "text_api_modus": api_modus,
        "text_pipeline": pipeline,
        "text_pipeline_modus": pipeline_mode,
        "text_hybrid": hybrid,
        "text_hybrid_modus": hybrid_mode,
        "text_pyproject": pyproject,
        "text_pyproject_modus": pyproject_mode,
        "text_providers_init": providers_init,
        "text_providers_init_modus": providers_init_mode,
        "text_docs_modus": docs_mode,
        "text_web_html": web_html,
        "text_spec": spec,
        "text_build": build,
        "text_workflow": workflow,
        "pseudokrat": find_pseudokrat(roots),
    }


def format_report(data: dict[str, object]) -> str:
    foundry = data["foundry"]
    assert isinstance(foundry, dict)
    lines = [
        "LLP AI Tools – Status",
        "",
        f"  {foundry['kurz']}",
        f"  Foundry bereit: {'ja' if foundry['bereit'] else 'nein'}",
        f"  {foundry['hinweis']}",
        "",
        "  Anhangspruefer:  "
        + ("gefunden" if data["anhang"] else "nicht gefunden"),
        "  Text verbessern: "
        + (
            f"gefunden, gruendlich = {data['text_modus']}"
            if data["text_desktop"]
            else "nicht gefunden"
        ),
        "  Startskript:     " + str(data["text_start"]),
        "  Startbefehl:     " + str(data["text_cmd_modus"]),
        "  Foundry-Datei:   "
        + ("vorhanden" if data["text_provider"] else "fehlt"),
        "  Ollama-Rest:     " + str(data["text_runtime_modus"]),
        "  Mistral-Client:  " + str(data["text_mistral_modus"]),
        "  Streamlit-Datei: " + str(data["text_streamlit_modus"]),
        "  Alte API:        " + str(data["text_api_modus"]),
        "  Text-Pipeline:   " + str(data["text_pipeline_modus"]),
        "  Hybrid-Weg:      " + str(data["text_hybrid_modus"]),
        "  Paketdatei:      " + str(data["text_pyproject_modus"]),
        "  Provider-Export: " + str(data["text_providers_init_modus"]),
        "  Tool-Anleitung:  " + str(data["text_docs_modus"]),
        "  Offline-HTML:    "
        + ("noch alt – Anwenden.bat" if data["text_web_html"] else "ok oder fehlt"),
        "  Packaging:       "
        + ("noch da – Anwenden.bat" if data["text_spec"] else "beiseite"),
        "  Original-Start:  "
        + ("noch da – Anwenden.bat" if data["text_original_cmd"] else "beiseite"),
        "  Alte EXE:        "
        + ("noch da – Anwenden.bat" if data["text_exe"] else "beiseite"),
        "  Pseudokrat:      "
        + (
            "gefunden (lokal, ohne Foundry)"
            if data["pseudokrat"]
            else "nicht gefunden"
        ),
        "",
    ]
    if data["text_modus"] == "noch Mistral":
        lines.append(
            "  Text verbessern zeigt noch Mistral."
            " Punkt 2 oeffnet dann die Foundry-Seite, nicht Mistral."
        )
    if data["text_start"] == "noch Streamlit":
        lines.append(
            "  start_windows.ps1 startet noch Streamlit."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_cmd_modus"] == "noch alt":
        lines.append(
            "  TEXT VERBESSERN.cmd ist noch das alte Skript."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_exe"] is not None:
        lines.append("  Eine alte TextVerbessern.exe liegt noch im Tool-Ordner.")
    if data["text_desktop"] is not None and data["text_provider"] is None:
        lines.append("  foundry_provider.py fehlt im Tool-Ordner.")
    if data["text_runtime_modus"] == "noch Ollama":
        lines.append(
            "  app/local_runtime.py prueft noch Ollama."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_mistral_modus"] == "noch Ollama":
        lines.append(
            "  mistral_provider.py kann noch Ollama aufrufen."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_streamlit_modus"] == "noch Streamlit":
        lines.append(
            "  streamlit_app.py ist noch die alte Oberflaeche."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_api_modus"] == "noch API":
        lines.append(
            "  app/main.py bietet noch eine FastAPI/uvicorn-Route."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_pipeline_modus"] in {"noch Mistral", "nicht erkannt"}:
        lines.append(
            "  app/pipeline.py leitet noch auf Mistral."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_hybrid_modus"] in {"noch Mistral", "nicht erkannt"}:
        lines.append(
            "  hybrid.py ruft noch Mistral auf."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_pyproject_modus"] in {"noch API", "noch Streamlit", "nicht erkannt"}:
        lines.append(
            "  pyproject.toml zieht noch Streamlit oder uvicorn nach."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_original_cmd"] is not None:
        lines.append(
            "  TEXT VERBESSERN.original.cmd startet noch den alten Weg."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_providers_init_modus"] in {"noch Mistral", "nicht erkannt"}:
        lines.append(
            "  app/providers/__init__.py exportiert noch Mistral."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_docs_modus"] in {"noch alt", "nicht erkannt"}:
        lines.append(
            "  README oder SCHNELLSTART zeigt noch EXE oder Mistral."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_web_html"] is not None:
        lines.append(
            "  web/TextVerbessern-Browser.html ist noch der alte Offline-Start."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    if data["text_spec"] is not None or data["text_build"] is not None or data["text_workflow"] is not None:
        lines.append(
            "  Ein Packaging- oder Build-Rezept liegt noch im Tool-Ordner."
            " Einmal text_verbessern_foundry\\Anwenden.bat."
        )
    lines.append("  Keine Schluessel in dieser Anzeige.")
    lines.append("  Anleitung: ANLEITUNG.txt in diesem Ordner.")
    return "\n".join(lines)


def leftovers_in_tool(tool_root: Path) -> list[str]:
    """Restwege in einem konkreten rephraser-Ordner, unabhängig vom Ordnernamen."""
    reasons: list[str] = []
    desktop = tool_root / "app" / "desktop.py"
    if desktop.is_file() and text_verbessern_modus(desktop) != "Foundry":
        reasons.append("Oberflaeche")
    pipeline = tool_root / "app" / "pipeline.py"
    if pipeline.is_file() and pipeline_modus(pipeline) != "Foundry":
        reasons.append("Pipeline")
    hybrid = tool_root / "app" / "providers" / "hybrid.py"
    if hybrid.is_file() and hybrid_modus(hybrid) != "Foundry":
        reasons.append("Hybrid")
    cmd = tool_root / "TEXT VERBESSERN.cmd"
    if cmd.is_file() and text_cmd_modus(cmd) != "Foundry-Tor":
        reasons.append("Startbefehl")
    original_cmd = tool_root / "TEXT VERBESSERN.original.cmd"
    if original_cmd.is_file():
        reasons.append("Original-CMD")
    ps1 = tool_root / "scripts" / "start_windows.ps1"
    if ps1.is_file() and text_startskript_modus(ps1) != "Foundry-Tor":
        reasons.append("Startskript")
    streamlit = tool_root / "app" / "ui" / "streamlit_app.py"
    if streamlit.is_file() and streamlit_app_modus(streamlit) != "abgeschaltet":
        reasons.append("Streamlit")
    api = tool_root / "app" / "main.py"
    if api.is_file() and text_api_modus(api) != "abgeschaltet":
        reasons.append("API")
    runtime = tool_root / "app" / "local_runtime.py"
    if runtime.is_file() and local_runtime_modus(runtime) != "kein Ollama":
        reasons.append("Ollama")
    mistral = tool_root / "app" / "providers" / "mistral_provider.py"
    if mistral.is_file() and mistral_provider_modus(mistral) != "abgeschaltet":
        reasons.append("Mistral-Client")
    pyproject = tool_root / "pyproject.toml"
    if pyproject.is_file() and pyproject_modus(pyproject) != "abgeschaltet":
        reasons.append("Paketdatei")
    providers_init = tool_root / "app" / "providers" / "__init__.py"
    if providers_init.is_file() and providers_init_modus(providers_init) != "Foundry":
        reasons.append("Provider-Export")
    if start_docs_modus(tool_root=tool_root) not in {"Foundry", "nicht gefunden"}:
        reasons.append("Anleitung")
    for rel in WEB_HTML_RELS:
        html = tool_root / rel
        if html.is_file() and web_html_modus(html) != "abgeschaltet":
            reasons.append("Offline-HTML")
            break
    if (tool_root / SPEC_REL).is_file():
        reasons.append("Packaging-Spec")
    if (tool_root / BUILD_REL).is_file():
        reasons.append("Build-Skript")
    if (tool_root / WORKFLOW_REL).is_file():
        reasons.append("Portable-CI")
    provider = tool_root / "app" / "providers" / "foundry_provider.py"
    if desktop.is_file() and not provider.is_file():
        reasons.append("Foundry-Datei")
    for rel in EXE_REL_DIRS:
        folder = tool_root / rel
        for exe_name in ("TextVerbessern.exe", "TEXT VERBESSERN.exe", "rephraser.exe"):
            if (folder / exe_name).is_file():
                reasons.append("EXE")
                break
        else:
            continue
        break
    return reasons


def text_has_leftovers(
    data: dict[str, object] | None = None, start: Path | None = None
) -> bool:
    """Alter Mistral/Streamlit/EXE-Weg nebenan – unabhängig von Foundry-Status."""
    if data is None:
        data = report(start)
    return (
        data["text_modus"] == "noch Mistral"
        or data["text_start"] == "noch Streamlit"
        or data["text_cmd_modus"] == "noch alt"
        or data["text_original_cmd"] is not None
        or data["text_exe"] is not None
        or data["text_runtime_modus"] == "noch Ollama"
        or data["text_mistral_modus"] == "noch Ollama"
        or data["text_streamlit_modus"] == "noch Streamlit"
        or data["text_api_modus"] == "noch API"
        or data["text_pipeline_modus"] in {"noch Mistral", "nicht erkannt"}
        or data["text_hybrid_modus"] in {"noch Mistral", "nicht erkannt"}
        or data["text_pyproject_modus"] in {"noch API", "noch Streamlit", "nicht erkannt"}
        or data["text_providers_init_modus"] in {"noch Mistral", "nicht erkannt"}
        or data["text_docs_modus"] in {"noch alt", "nicht erkannt"}
        or data["text_web_html"] is not None
        or data["text_spec"] is not None
        or data["text_build"] is not None
        or data["text_workflow"] is not None
        or (data["text_desktop"] is not None and data["text_provider"] is None)
    )


def text_foundry_ok(start: Path | None = None) -> bool:
    data = report(start)
    start_ok = data["text_start"] in {"Foundry-Tor", "nicht gefunden"}
    cmd_ok = data["text_cmd_modus"] in {"Foundry-Tor", "nicht gefunden"}
    original_ok = data["text_original_cmd"] is None
    exe_ok = data["text_exe"] is None
    provider_ok = data["text_provider"] is not None or data["text_desktop"] is None
    runtime_ok = data["text_runtime_modus"] in {"kein Ollama", "nicht gefunden"}
    mistral_ok = data["text_mistral_modus"] in {"abgeschaltet", "nicht gefunden"}
    streamlit_ok = data["text_streamlit_modus"] in {"abgeschaltet", "nicht gefunden"}
    api_ok = data["text_api_modus"] in {"abgeschaltet", "nicht gefunden"}
    pipeline_ok = data["text_pipeline_modus"] in {"Foundry", "nicht gefunden"}
    hybrid_ok = data["text_hybrid_modus"] in {"Foundry", "nicht gefunden"}
    pyproject_ok = data["text_pyproject_modus"] in {"abgeschaltet", "nicht gefunden"}
    init_ok = data["text_providers_init_modus"] in {"Foundry", "nicht gefunden"}
    docs_ok = data["text_docs_modus"] in {"Foundry", "nicht gefunden"}
    web_ok = data["text_web_html"] is None
    pack_ok = data["text_spec"] is None and data["text_build"] is None and data["text_workflow"] is None
    return (
        data["text_modus"] == "Foundry"
        and start_ok
        and cmd_ok
        and original_ok
        and exe_ok
        and provider_ok
        and runtime_ok
        and mistral_ok
        and streamlit_ok
        and api_ok
        and pipeline_ok
        and hybrid_ok
        and pyproject_ok
        and init_ok
        and docs_ok
        and web_ok
        and pack_ok
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--kurz" in args:
        print(describe_status()["kurz"])
        return 0
    if "--rest" in args:
        return 2 if text_has_leftovers() else 0
    if "--text-foundry" in args:
        return 0 if text_foundry_ok() else 1
    data = report()
    print(format_report(data))
    foundry = data["foundry"]
    assert isinstance(foundry, dict)
    if text_has_leftovers(data):
        return 2
    return 0 if foundry["bereit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
