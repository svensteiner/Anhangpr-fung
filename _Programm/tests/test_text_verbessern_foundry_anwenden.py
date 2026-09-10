"""Share-Patch: Text verbessern auf Foundry umstellen, ohne Ollama/Mistral."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ANWENDEN = (
    Path(__file__).resolve().parents[2]
    / "_Gemeinsam"
    / "text_verbessern_foundry"
    / "anwenden.py"
)

PIPELINE_MAIN = '''from .providers.fast_editor import FastEditorialProvider
from .providers.local import LocalRuleProvider
from .providers.mistral_provider import LocalMistralProvider
from .providers.hybrid import HybridLocalProvider


def get_provider(name: str):
    normalized = name.casefold()
    if normalized in {"local", "rules", "rule-based"}:
        return LocalRuleProvider()
    if normalized in {"fast", "fast-rules", "fast-editor"}:
        return FastEditorialProvider()
    if normalized in {"mistral", "mistral-local", "ollama"}:
        return LocalMistralProvider()
    if normalized in {"auto", "hybrid", "rules+mistral-local"}:
        return HybridLocalProvider()
    if normalized in {"openai", "anthropic"}:
        raise RuntimeError(f"Remote provider '{name}' is disabled; select fast-editor, rules, or mistral-local.")
    raise RuntimeError(f"Unknown provider: {name}")


def run_pipeline(text, options=None, provider=None):
    try:
        rewritten = text
    except ProviderError as error:
        if "mistral" not in active_provider.name:
            raise
        provider_failure = error
        rewritten = LocalRuleProvider().rewrite(text, semantics, selected)
    elif ("mistral" in active_provider.name or active_provider.name == "fast-editor") and warnings:
        rewritten = LocalRuleProvider().rewrite(text, semantics, selected)
    return rewritten
'''

DESKTOP_MAIN = '''from app.local_runtime import (
    LOCAL_MODEL_MAX_CHARACTERS,
    local_mistral_ready,
    local_model_eligible,
    preflight_local_mistral,
)
from app.pipeline import run_pipeline
from app.providers.base import ProviderError

MODE_AUTOMATIC = "Schnell verbessern (empfohlen)"
MODE_SAFE = "Nur Format bereinigen"
MODE_STRONG = "Gründlich mit Mistral (bis 45 s)"


def processing_settings(mode: str, mistral_ready: bool) -> tuple[str, str]:
    """Map user-facing choices to safe internal provider settings."""
    if mode == MODE_SAFE or not mistral_ready:
        return ("rules", "light") if mode == MODE_SAFE else ("fast-editor", "medium")
    if mode == MODE_STRONG:
        return "rules+mistral-local", "substantial"
    return "fast-editor", "medium"


def available_modes(mistral_ready: bool) -> tuple[str, ...]:
    """Expose only choices that are actually available on this computer."""
    if not mistral_ready:
        return (MODE_AUTOMATIC, MODE_SAFE)
    return (MODE_AUTOMATIC, MODE_SAFE, MODE_STRONG)


def system_status_text(mistral_ready: bool, model_request_inflight: bool = False) -> str:
    """Describe only local capabilities that can be used right now."""
    if model_request_inflight:
        return "✓ Schnelle lokale Bearbeitung bereit; Mistral beendet noch eine frühere Anfrage."
    if mistral_ready:
        return "✓ Sofortige Textverbesserung bereit; Mistral ist zusätzlich verfügbar."
    return "✓ Sofortige lokale Textverbesserung bereit; Mistral ist optional."


class App:
    def __init__(self) -> None:
        self.mistral_ready = local_mistral_ready()

    def _refresh_mistral_controls(self, source: str | None = None) -> None:
        current_source = source if source is not None else ""
        mistral_for_text = local_model_eligible(current_source, self._mistral_can_start())
        self.mode_box.configure(values=available_modes(mistral_for_text))
        if self.mode.get() == MODE_STRONG and not mistral_for_text:
            self.mode.set(MODE_AUTOMATIC)

    def start(self) -> None:
        selected_mode = self.mode.get()
        fallback_kind: str | None = None
        if selected_mode == MODE_STRONG:
            # Availability may have changed since startup.  This short local-only
            # preflight sends no document text and avoids an avoidable long wait.
            self.result_status.configure(text="Lokales Mistral wird kurz geprüft …")
            try:
                self.root.update_idletasks()
            except self.tk.TclError:
                return
            if not preflight_local_mistral():
                self._set_mistral_availability(False)
                fallback_kind = "provider_unavailable"
        provider, strength = processing_settings(self.mode.get(), self.mistral_ready)
        self.processing_active = "mistral" in provider
        model_request = "mistral" in provider
        if fallback_kind is not None:
            result.audit.requested_provider = "rules+mistral-local"
            result.audit.options["requested_provider"] = "rules+mistral-local"
            self.result_status.configure(
                text="Mistral derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt …"
            )
        unused = model_request
        diagnostics = {"mistral_available": local_mistral_ready()}

    def _worker(self, source, options):
            result = run_pipeline(source, options)
            unused = result


def run_self_test() -> dict[str, object]:
    result = run_pipeline("Gruesse", TransformOptions(provider="rules", rewrite_strength="light"))
    return {"ok": True, "text": result.rewritten_text}


def main(argv=None):
    arguments = argv if argv is not None else []
    if "--self-test" in arguments:
        report = run_self_test()
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["ok"] else 1
    try:
        DesktopApp().run()
    except Exception as error:
        write_diagnostic_event("desktop_fatal", error)
        show_startup_error()
        return 1
    return 0


class DesktopApp:
    def run(self) -> None:
        self.root.mainloop()
'''

STREAMLIT_MAIN = '''import streamlit as st
from app.local_runtime import (
    LOCAL_MODEL_MAX_CHARACTERS,
    local_mistral_ready,
    local_model_eligible,
    preflight_local_mistral,
)
from app.pipeline import run_pipeline
from app.providers.base import ProviderError

st.set_page_config(page_title="Text verbessern", page_icon="✍️", layout="centered")


@st.cache_data(ttl=10, show_spinner=False)
def cached_local_mistral_ready() -> bool:
    return local_mistral_ready()


mistral_ready = cached_local_mistral_ready()
if mistral_ready:
    st.success("Sofortige Textverbesserung bereit; Mistral ist zusätzlich verfügbar.", icon="✅")
else:
    st.info(
        "Sofortige lokale Textverbesserung bereit. Die optionale Mistral-Variante ist nicht verfügbar.",
        icon="ℹ️",
    )

with st.expander("Bearbeitung anpassen"):
    mistral_for_text = local_model_eligible(st.session_state.source_text, mistral_ready)
    mode_choices = (
        ["Schnell verbessern (empfohlen)", "Nur Format bereinigen", "Gründlich mit Mistral (bis 45 s)"]
        if mistral_for_text
        else ["Schnell verbessern (empfohlen)", "Nur Format bereinigen"]
    )
    mode_label = st.radio("Bearbeitung", mode_choices, horizontal=True)
    if mistral_ready and mode_label == "Gründlich mit Mistral (bis 45 s)":
        tone_label = st.selectbox("Stil", ["Stil beibehalten"])
    else:
        st.caption("Stiloptionen gelten nur für die optionale gründliche Mistral-Bearbeitung.")

if run:
    requested_thorough_mode = mode_label == "Gründlich mit Mistral (bis 45 s)" and mistral_ready
    mistral_preflight_failed = False
    if requested_thorough_mode:
        with st.spinner("Lokales Mistral wird kurz geprüft …"):
            mistral_preflight_failed = not preflight_local_mistral()
    if mode_label == "Nur Format bereinigen":
        provider, strength = "rules", "light"
    elif requested_thorough_mode and not mistral_preflight_failed:
        provider = "rules+mistral-local"
        strength = "substantial"
    else:
        provider, strength = "fast-editor", "medium"
    message = (
        "Gründliche lokale Mistral-Überarbeitung läuft – höchstens 45 Sekunden."
        if "mistral" in provider
        else "Mistral derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt."
        if mistral_preflight_failed
        else "Text wird sofort lokal verbessert."
    )
    if mistral_preflight_failed:
        st.session_state.result.audit.requested_provider = "rules+mistral-local"
    st.warning("Mistral hat die Zeitgrenze erreicht. Das sicher bereinigte Ergebnis wird angezeigt.")
    st.warning("Mistral war nicht verfügbar. Die sichere lokale Grundbereinigung wird angezeigt.")
'''


def _load_anwenden():
    spec = importlib.util.spec_from_file_location("text_verbessern_foundry_anwenden", ANWENDEN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_rephraser(tmp_path: Path) -> Path:
    tool = tmp_path / "rephraser"
    (tool / "app" / "providers").mkdir(parents=True)
    (tool / "app" / "ui").mkdir(parents=True)
    (tool / "app" / "pipeline.py").write_text(PIPELINE_MAIN, encoding="utf-8")
    (tool / "app" / "desktop.py").write_text(DESKTOP_MAIN, encoding="utf-8")
    (tool / "app" / "evaluation.py").write_text(
        "from app.pipeline import run_pipeline\n"
        "def evaluate_case(case):\n"
        "    return run_pipeline(case.input, TransformOptions(provider=case.provider))\n"
        "def main() -> int:\n"
        "    return 0\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    (tool / "app" / "ui" / "streamlit_app.py").write_text(STREAMLIT_MAIN, encoding="utf-8")
    (tool / "TEXT VERBESSERN.cmd").write_text(
        "@echo off\r\nstart TextVerbessern.exe\r\n",
        encoding="utf-8",
    )
    scripts = tool / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "start_windows.ps1").write_text(
        'Write-Host "Text verbessern wird gestartet ..."\n'
        '& $venvPython -m streamlit run "app/ui/streamlit_app.py"\n',
        encoding="utf-8",
    )
    (tool / "SCHNELLSTART.md").write_text(
        "# Text verbessern\n\n"
        "Doppelklicke auf TextVerbessern.exe.\n"
        "Gründlich mit Mistral ist optional.\n",
        encoding="utf-8",
    )
    (tool / ".env.example").write_text(
        "MISTRAL_BASE_URL=http://127.0.0.1:11434\nMISTRAL_MODEL=mistral\n",
        encoding="utf-8",
    )
    (tool / "README.md").write_text(
        "# Text verbessern\n\nDoppelklick auf TextVerbessern.exe. Ollama/Mistral.\n",
        encoding="utf-8",
    )
    web = tool / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "TextVerbessern-Browser.html").write_text(
        "<html><body><p>Offline, kein Mistral-Modell.</p></body></html>\n",
        encoding="utf-8",
    )
    (web / "index.html").write_text(
        "<html><body><p>kein Mistral-Modell</p></body></html>\n",
        encoding="utf-8",
    )
    (web / "app.js").write_text("export function startEditor() {}\n", encoding="utf-8")
    (web / "editor.js").write_text("export function bindEditor() {}\n", encoding="utf-8")
    pack = tool / "packaging"
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "TextVerbessern.spec").write_text(
        'name="TextVerbessern"\nanalysis = Analysis(["app/desktop.py"])\n',
        encoding="utf-8",
    )
    (tool / "pyproject.toml").write_text(
        "dependencies = [\"fastapi>=0.115\", \"pydantic>=2.8\", \"uvicorn>=0.30\"]\n"
        "[project.optional-dependencies]\nui = [\"streamlit>=1.37\"]\n"
        "[project.scripts]\neditorial-transformer = \"app.main:cli\"\n",
        encoding="utf-8",
    )
    wf = tool / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "windows-portable.yml").write_text(
        "name: portable\n  TextVerbessern.exe\n",
        encoding="utf-8",
    )
    (wf / "tests.yml").write_text(
        "name: Tests\n        run: python -m app.evaluation\n",
        encoding="utf-8",
    )
    (wf / "pages.yml").write_text(
        "name: Browser edition\n        run: node --test tests/web_editor.test.mjs\n",
        encoding="utf-8",
    )
    dist = tool / "dist" / "TextVerbessern"
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "TextVerbessern.exe").write_bytes(b"mz-dist")
    (tool / "app" / "main.py").write_text(
        'parser.add_argument("--provider", choices=["fast-editor", "rules", "mistral-local"])\n'
        "def health() -> dict[str, str]:\n"
        '    return {"status": "ok", "default_provider": "fast-editor"}\n'
        "def transform(request: TransformRequest) -> TransformResult:\n"
        "    try:\n"
        "        return run_pipeline(request.text, request.options)\n"
        "    except ProviderError as error:\n"
        "        raise HTTPException(status_code=503, detail=str(error)) from error\n"
        "def transform_text(request: TransformRequest) -> str:\n"
        "    return transform(request).rewritten_text\n"
        "def cli(argv=None):\n"
        "    result = run_pipeline(text, options)\n"
        "    return 0\n",
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "__init__.py").write_text(
        "from .mistral_provider import LocalMistralProvider\n"
        "from .hybrid import HybridLocalProvider\n"
        "__all__ = [\n"
        '    "LocalMistralProvider",\n'
        '    "HybridLocalProvider",\n'
        "]\n",
        encoding="utf-8",
    )
    (tool / "scripts" / "build_browser_standalone.py").write_text(
        "OUTPUT_PATH = WEB_ROOT / 'TextVerbessern-Browser.html'\n",
        encoding="utf-8",
    )
    (tool / "app" / "local_runtime.py").write_text(
        "def local_mistral_ready(timeout: float = 0.8) -> bool:\n"
        "    return True  # http://127.0.0.1:11434\n"
        "    raw = opener.open(base_url + '/api/tags')\n"
        "    model = os.getenv('MISTRAL_MODEL', 'mistral')\n"
        "MISTRAL_PREFLIGHT_TIMEOUT_SECONDS = 0.5\n\n"
        "def preflight_local_mistral() -> bool:\n"
        "    return True\n",
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "mistral_provider.py").write_text(
        "class LocalMistralProvider:\n"
        "    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:\n"
        "        self.base_url = os.getenv('MISTRAL_BASE_URL', 'http://127.0.0.1:11434')\n"
        "        self.model = os.getenv('MISTRAL_MODEL', 'mistral')\n"
        "        self.timeout = float(os.getenv('MISTRAL_TIMEOUT_SECONDS', '42'))\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        "        request = self.base_url + '/api/generate'\n"
        "        return text\n",
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "openai_provider.py").write_text(
        "class OpenAIProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        '        raise ProviderError("The cloud OpenAI adapter is intentionally disabled.")\n',
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "anthropic_provider.py").write_text(
        "class AnthropicProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        '        raise ProviderError("The cloud Anthropic adapter is intentionally disabled.")\n',
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "local.py").write_text(
        "class LocalRuleProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        "        return text.replace('  ', ' ')\n",
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "fast_editor.py").write_text(
        "class FastEditorialProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        "        cleaned = LocalRuleProvider().rewrite(text, constraints, options)\n"
        "        return text + '!'\n",
        encoding="utf-8",
    )
    (tool / "app" / "providers" / "hybrid.py").write_text(
        "from app.providers.mistral_provider import LocalMistralProvider\n\n"
        "class HybridLocalProvider:\n"
        '    name = "rules+mistral-local"\n'
        "    def __init__(self):\n"
        "        self.mistral = LocalMistralProvider()\n"
        "    def rewrite(self, text, constraints, options):\n"
        "        return self.mistral.rewrite(text, constraints, options)\n",
        encoding="utf-8",
    )
    return tool


def test_anwenden_stellt_text_verbessern_auf_foundry_um(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert "Foundry-Anbindung" in msg
    assert module.leftovers_in_tool(tool) == []
    assert (tool / "app" / "providers" / "foundry_provider.py").is_file()
    provider = (tool / "app" / "providers" / "foundry_provider.py").read_text(encoding="utf-8")
    assert "ask_ai" in provider
    assert "ollama" in provider.lower()
    assert "No silent switch" in provider or "kein stiller" in provider.lower()

    pipeline = (tool / "app" / "pipeline.py").read_text(encoding="utf-8")
    assert "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider" in pipeline
    assert "from .providers.mistral_provider import LocalMistralProvider" not in pipeline
    assert "from .providers.hybrid import HybridLocalProvider" not in pipeline
    assert '"foundry", "company-ai"' in pipeline
    assert '"rules+foundry"' in pipeline
    assert "return FoundryEditorialProvider()" in pipeline
    assert "return HybridFoundryProvider()" in pipeline
    assert "return LocalMistralProvider()" not in pipeline
    assert "return HybridLocalProvider()" not in pipeline
    assert "return LocalRuleProvider()" not in pipeline
    assert "return FastEditorialProvider()" not in pipeline
    assert "LocalRuleProvider().rewrite" not in pipeline
    assert "FastEditorialProvider().rewrite" not in pipeline
    assert "LocalRuleProvider" not in provider
    assert "Der Text bleibt unverändert" in provider
    assert "or foundry." in pipeline
    assert "or mistral-local." not in pipeline
    assert 'if "mistral" not in active_provider.name:' not in pipeline
    assert "except ProviderError as error:\n        raise\n" in pipeline

    runtime = (tool / "app" / "local_runtime.py").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in runtime
    assert "kein Ollama" in runtime
    assert "11434" not in runtime
    assert "MISTRAL_BASE_URL" not in runtime
    assert "/api/tags" not in runtime
    assert "MISTRAL_MODEL" not in runtime
    assert "MISTRAL_PREFLIGHT_TIMEOUT_SECONDS" not in runtime
    assert "MISTRAL_TIMEOUT_SECONDS" not in runtime
    assert runtime.count("return False") >= 2
    lines = [ln.strip() for ln in runtime.splitlines() if ln.strip()]
    ready_idx = lines.index("def local_mistral_ready(timeout: float = 0.8) -> bool:")
    assert lines[ready_idx + 1] == "return False  # LLP-FOUNDRY-TOR: kein Ollama"
    assert runtime.count("return False  # LLP-FOUNDRY-TOR: kein Ollama") == 2

    mistral = (tool / "app" / "providers" / "mistral_provider.py").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in mistral
    assert "LocalMistralProvider ist abgeschaltet" in mistral
    assert "Nur Foundry" in mistral
    assert "/api/generate" not in mistral
    assert "11434" not in mistral
    assert "MISTRAL_BASE_URL" not in mistral
    assert "MISTRAL_MODEL" not in mistral
    assert "MISTRAL_TIMEOUT_SECONDS" not in mistral
    lines = [ln.rstrip() for ln in mistral.splitlines()]
    init_idx = next(i for i, ln in enumerate(lines) if "def __init__" in ln)
    assert "raise RuntimeError" in lines[init_idx + 1]

    hybrid = (tool / "app" / "providers" / "hybrid.py").read_text(encoding="utf-8")
    assert "FoundryEditorialProvider" in hybrid
    assert 'name = "rules+foundry"' in hybrid
    assert "LocalMistralProvider" not in hybrid
    local_rules = (tool / "app" / "providers" / "local.py").read_text(encoding="utf-8")
    assert "Lokale Regeln sind abgeschaltet" in local_rules
    assert "LLP-FOUNDRY-TOR" in local_rules
    fast_editor = (tool / "app" / "providers" / "fast_editor.py").read_text(encoding="utf-8")
    assert "Schnell-Editor ist abgeschaltet" in fast_editor
    assert "LLP-FOUNDRY-TOR" in fast_editor
    assert "LocalRuleProvider().rewrite" not in fast_editor

    assert "LocalRuleProvider" not in hybrid
    assert "self.foundry" in hybrid
    assert "self.rules" not in hybrid

    desktop = (tool / "app" / "desktop.py").read_text(encoding="utf-8")
    assert 'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"' in desktop
    assert "from app.providers.foundry_provider import foundry_ready" in desktop
    assert 'return "rules+foundry", "substantial"' in desktop
    assert "if foundry_ready():" in desktop
    assert "if not mistral_ready:" not in desktop
    assert "thorough_ready = foundry_ready()" in desktop
    assert "self.mistral_ready = foundry_ready()" in desktop
    assert "DesktopApp().run()" not in desktop
    assert "self.root.mainloop()" not in desktop
    assert "alte Oberflaeche startet nicht" in desktop
    assert "Nur Foundry, kein Mistral" in desktop
    ast.parse(desktop)
    assert "    try:\n    print(" not in desktop
    assert not (tool / "packaging" / "TextVerbessern.spec").is_file()
    assert (tool / "packaging" / "TextVerbessern.spec.llp-alt").is_file()
    assert "self.mistral_ready = local_mistral_ready()" not in desktop
    assert '"mistral_available": foundry_ready()' in desktop
    assert "local_mistral_ready()" not in desktop
    assert "local_model_eligible(current_source, self._mistral_can_start())" not in desktop
    assert "preflight_local_mistral()" not in desktop
    assert "if not foundry_ready():" in desktop
    assert '"mistral" in provider' not in desktop
    assert '"foundry" in provider' in desktop
    assert "rules+mistral-local" not in desktop
    assert "report = run_self_test()" not in desktop
    assert "Kein Selbsttest mit Regeln oder Modellwahl" in desktop
    assert "LLP-FOUNDRY-TOR: kein Selbsttest" in desktop
    assert "sichere lokale" not in desktop.lower()
    assert "lokale textverbesserung" not in desktop.lower()
    assert "schnelle lokale bearbeitung" not in desktop.lower()
    assert "der Text bleibt unverändert" in desktop
    assert "run_pipeline(source, options)" not in desktop
    assert "run_pipeline(" not in desktop

    evaluation = (tool / "app" / "evaluation.py").read_text(encoding="utf-8")
    assert "Keine lokale Bewertung" in evaluation
    assert "run_pipeline(" not in evaluation
    assert "LLP-FOUNDRY-TOR" in evaluation

    streamlit = (tool / "app" / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    ast.parse(streamlit)
    assert "LLP-FOUNDRY-TOR" in streamlit
    assert "Streamlit-Oberflaeche startet nicht" in streamlit
    assert "import streamlit" not in streamlit
    assert "Gründlich mit Mistral" not in streamlit
    stub_note = (tool / "app" / "ui" / "streamlit_app.py.llp-alt").read_text(encoding="utf-8")
    assert "Sicherung. Nicht starten" in stub_note
    stub_bak = (
        tool / "_llp_parked" / "app" / "ui" / "streamlit_app.py.llp-alt.txt"
    ).read_text(encoding="utf-8")
    assert "import streamlit" in stub_bak
    pyproject = (tool / "pyproject.toml").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in pyproject
    assert "kein Streamlit" in pyproject
    assert "kein uvicorn" in pyproject
    assert "streamlit>=" not in pyproject
    assert "uvicorn>=" not in pyproject
    assert "fastapi>=" not in pyproject
    assert "keine alte CLI" in pyproject
    assert "editorial-transformer" not in pyproject or "entfernt" in pyproject
    assert 'editorial-transformer = "app.main:cli"' not in pyproject
    assert not (tool / "dist" / "TextVerbessern" / "TextVerbessern.exe").is_file()
    assert (tool / "dist" / "TextVerbessern" / "TextVerbessern.exe.llp-alt").is_file()
    assert not (tool / ".github" / "workflows" / "windows-portable.yml").is_file()
    assert (tool / ".github" / "workflows" / "windows-portable.yml.llp-alt").is_file()
    assert not (tool / ".github" / "workflows" / "tests.yml").is_file()
    assert (tool / ".github" / "workflows" / "tests.yml.llp-alt").is_file()
    assert not (tool / ".github" / "workflows" / "pages.yml").is_file()
    assert (tool / ".github" / "workflows" / "pages.yml.llp-alt").is_file()
    openai = (tool / "app" / "providers" / "openai_provider.py").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in openai
    assert "Fremd-KI" in openai
    anthropic = (tool / "app" / "providers" / "anthropic_provider.py").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in anthropic
    assert "Fremd-KI" in anthropic

    launcher = (tool / "TEXT VERBESSERN.cmd").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in launcher
    assert "mistral-rephraser wird nicht gestartet" in launcher.lower()
    assert "TEXT VERBESSERN.original.cmd" not in launcher
    assert "TextVerbessern.exe" not in launcher
    assert "from app.desktop import main" not in launcher
    assert "app\\desktop.py" not in launcher
    assert "text_verbessern_foundry" in launcher.lower()
    assert not (tool / "TEXT VERBESSERN.original.cmd").is_file()
    backup = (tool / "TEXT VERBESSERN.cmd.llp-alt").read_text(encoding="utf-8")
    assert "Sicherung. Nicht starten" in backup
    cmd_parked = (tool / "_llp_parked" / "TEXT VERBESSERN.cmd.llp-alt.txt").read_text(
        encoding="utf-8"
    )
    assert "TextVerbessern.exe" in cmd_parked
    assert "LLP-FOUNDRY-TOR" not in cmd_parked

    ps1 = (tool / "scripts" / "start_windows.ps1").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in ps1
    assert "streamlit" not in ps1.lower()
    assert "mistral-rephraser wird nicht gestartet" in ps1.lower()
    assert "text_verbessern_foundry" in ps1.lower()
    assert "foundry-seite" in ps1.lower()
    ps1_note = (tool / "scripts" / "start_windows.ps1.llp-alt").read_text(encoding="utf-8")
    assert "Sicherung. Nicht starten" in ps1_note
    ps1_bak = (tool / "_llp_parked" / "scripts" / "start_windows.ps1.llp-alt.txt").read_text(
        encoding="utf-8"
    )
    assert "streamlit" in ps1_bak.lower()
    assert "LLP-FOUNDRY-TOR" not in ps1_bak

    note = (tool / "LIESMICH-FOUNDRY.txt").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in note
    assert "kein mistral" in note.lower()
    assert "kein streamlit" in note.lower()
    schnell = (tool / "SCHNELLSTART.md").read_text(encoding="utf-8")
    assert schnell == note
    assert "textverbessern.exe" not in schnell.lower()
    schnell_note = (tool / "SCHNELLSTART.md.llp-alt").read_text(encoding="utf-8")
    assert "Sicherung. Nicht starten" in schnell_note
    schnell_bak = (
        tool / "_llp_parked" / "SCHNELLSTART.md.llp-alt.txt"
    ).read_text(encoding="utf-8")
    assert "Gründlich mit Mistral" in schnell_bak
    assert "LLP-FOUNDRY-TOR" not in schnell_bak

    env = (tool / ".env.example").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in env
    assert "MISTRAL_BASE_URL" not in env
    assert "llp_ai" in env
    env_bak = (tool / ".env.example.llp-alt").read_text(encoding="utf-8")
    assert "MISTRAL_BASE_URL" in env_bak
    readme = (tool / "README.md").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in readme
    assert "kein Mistral" in readme
    assert "kein Streamlit" in readme
    assert "TextVerbessern.exe" not in readme
    assert "streamlit run" not in readme.lower()
    readme_note = (tool / "README.md.llp-alt").read_text(encoding="utf-8")
    assert "Sicherung. Nicht starten" in readme_note
    readme_bak = (tool / "_llp_parked" / "README.md.llp-alt.txt").read_text(encoding="utf-8")
    assert "TextVerbessern.exe" in readme_bak
    assert "LLP-FOUNDRY-TOR" not in readme_bak
    html = (tool / "web" / "TextVerbessern-Browser.html").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in html
    assert "Offline-Datei startet nicht" in html
    assert "<script" not in html.lower()
    assert "text_verbessern_foundry" in html
    html_note = (tool / "web" / "TextVerbessern-Browser.html.llp-alt").read_text(encoding="utf-8")
    assert "Sicherung. Nicht starten" in html_note
    assert "<script" not in html_note.lower()
    html_bak = (
        tool / "_llp_parked" / "web" / "TextVerbessern-Browser.html.llp-alt.txt"
    ).read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" not in html_bak
    index = (tool / "web" / "index.html").read_text(encoding="utf-8")
    assert "Offline-Datei startet nicht" in index
    assert "<script" not in index.lower()
    assert not (tool / "web" / "app.js").is_file()
    assert not (tool / "web" / "editor.js").is_file()
    assert (tool / "web" / "app.js.llp-alt").is_file()
    assert (tool / "web" / "editor.js.llp-alt").is_file()
    assert "Sicherung. Nicht starten" in (tool / "web" / "app.js.llp-alt").read_text(
        encoding="utf-8"
    )
    assert "startEditor" in (
        tool / "_llp_parked" / "web" / "app.js.llp-alt.txt"
    ).read_text(encoding="utf-8")
    cli = (tool / "app" / "main.py").read_text(encoding="utf-8")
    assert 'choices=["fast-editor", "rules", "foundry"]' in cli
    assert "mistral-local" not in cli
    assert "uvicorn startet nicht" in cli
    assert "LLP-FOUNDRY-TOR" in cli
    assert "return run_pipeline(request.text, request.options)" not in cli
    assert 'return {"status": "ok", "default_provider": "fast-editor"}' not in cli
    assert "return transform(request).rewritten_text" not in cli
    assert "Die alte CLI startet nicht" in cli
    assert "result = run_pipeline" not in cli
    providers_init = (tool / "app" / "providers" / "__init__.py").read_text(encoding="utf-8")
    assert "FoundryEditorialProvider" in providers_init
    assert "LocalMistralProvider" not in providers_init
    assert "HybridLocalProvider" not in providers_init
    assert "LocalRuleProvider" not in providers_init
    assert "FastEditorialProvider" not in providers_init
    assert not (tool / "scripts" / "build_browser_standalone.py").is_file()
    assert (tool / "scripts" / "build_browser_standalone.py.llp-alt").is_file()

    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "bereits auf Foundry" in msg2
    assert not (tool / "TEXT VERBESSERN.original.cmd").is_file()
    backup2 = (tool / "TEXT VERBESSERN.cmd.llp-alt").read_text(encoding="utf-8")
    assert backup2 == backup
    ps1_again = (tool / "scripts" / "start_windows.ps1").read_text(encoding="utf-8")
    assert ps1_again == ps1
    assert (tool / "scripts" / "start_windows.ps1.llp-alt").read_text(encoding="utf-8") == ps1_note
    runtime2 = (tool / "app" / "local_runtime.py").read_text(encoding="utf-8")
    assert runtime2.count("return False  # LLP-FOUNDRY-TOR: kein Ollama") == 2


def test_anwenden_ohne_windows_startskript_bleibt_ok(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    (tool / "scripts" / "start_windows.ps1").unlink()
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert not (tool / "scripts" / "start_windows.ps1").is_file()


def test_replace_desktop_main_repariert_haengendes_try() -> None:
    module = _load_anwenden()
    broken = "def main():\n    try:\n" + module.DESKTOP_MAIN_HINT + "\n"
    fixed = module._replace_desktop_main(broken)
    ast.parse(fixed)
    assert "    try:\n    print(" not in fixed
    assert "alte Oberflaeche startet nicht" in fixed
    assert module._replace_desktop_main(fixed) == fixed


def test_anwenden_legt_alte_exe_beiseite(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    exe = tool / "TextVerbessern.exe"
    exe.write_bytes(b"mz-fake")
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert not exe.is_file()
    parked = tool / "TextVerbessern.exe.llp-alt"
    assert parked.is_file()
    assert parked.read_bytes() == b"mz-fake"
    launcher = (tool / "TEXT VERBESSERN.cmd").read_text(encoding="utf-8")
    assert "TextVerbessern.exe" not in launcher


def test_anwenden_findet_geschwisterordner(tmp_path: Path) -> None:
    module = _load_anwenden()
    tools = tmp_path / "AI Tools"
    gemeinsam = tools / "_Gemeinsam" / "text_verbessern_foundry"
    gemeinsam.mkdir(parents=True)
    _fake_rephraser(tools)
    found = module.find_tool_root(gemeinsam)
    assert found is not None
    assert found.name == "rephraser"


def test_anwenden_ohne_tool_gibt_hinweis(tmp_path: Path) -> None:
    module = _load_anwenden()
    leer = tmp_path / "_Gemeinsam" / "text_verbessern_foundry"
    leer.mkdir(parents=True)
    assert module.find_tool_root(leer) is None


def test_anwenden_entfernt_ollama_probe_url(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    runtime = tool / "app" / "local_runtime.py"
    assert "11434" in runtime.read_text(encoding="utf-8")
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = runtime.read_text(encoding="utf-8")
    assert "11434" not in text
    assert "MISTRAL_BASE_URL" not in text
    assert "/api/tags" not in text
    assert "MISTRAL_MODEL" not in text
    assert module.leftovers_in_tool(tool) == []
    runtime.write_text(
        text + "\nMISTRAL_BASE_URL = 'http://127.0.0.1:11434'\n",
        encoding="utf-8",
    )
    assert "Ollama" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert "11434" not in runtime.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_entfernt_ollama_generate(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "/api/generate" in (tool / "app" / "providers" / "mistral_provider.py").read_text(
        encoding="utf-8"
    )
    assert "Mistral-Client" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    mistral = (tool / "app" / "providers" / "mistral_provider.py").read_text(encoding="utf-8")
    assert "/api/generate" not in mistral
    assert "/api/abgeschaltet" in mistral
    assert module.leftovers_in_tool(tool) == []
    path = tool / "app" / "providers" / "mistral_provider.py"
    path.write_text(mistral.replace("/api/abgeschaltet", "/api/generate"), encoding="utf-8")
    assert "Mistral-Client" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert "/api/generate" not in path.read_text(encoding="utf-8")
    assert "11434" not in path.read_text(encoding="utf-8")
    assert "MISTRAL_BASE_URL" not in path.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_entfernt_mistral_base_url(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "MISTRAL_BASE_URL" in (tool / "app" / "providers" / "mistral_provider.py").read_text(
        encoding="utf-8"
    )
    assert "Mistral-Client" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    path = tool / "app" / "providers" / "mistral_provider.py"
    text = path.read_text(encoding="utf-8")
    assert "MISTRAL_BASE_URL" not in text
    assert "FOUNDRY_OFF_BASE_URL" in text
    assert module.leftovers_in_tool(tool) == []
    path.write_text(
        text + "\n        self.base_url = os.getenv('MISTRAL_BASE_URL', 'http://127.0.0.1:0')\n",
        encoding="utf-8",
    )
    assert "Mistral-Client" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "MISTRAL_BASE_URL" not in path.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_entfernt_mistral_timeout(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "MISTRAL_TIMEOUT_SECONDS" in (
        tool / "app" / "providers" / "mistral_provider.py"
    ).read_text(encoding="utf-8")
    assert "MISTRAL_PREFLIGHT_TIMEOUT_SECONDS" in (
        tool / "app" / "local_runtime.py"
    ).read_text(encoding="utf-8")
    assert "Mistral-Client" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    mistral = tool / "app" / "providers" / "mistral_provider.py"
    runtime = tool / "app" / "local_runtime.py"
    assert "MISTRAL_TIMEOUT_SECONDS" not in mistral.read_text(encoding="utf-8")
    assert "MISTRAL_PREFLIGHT_TIMEOUT_SECONDS" not in runtime.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []
    mistral.write_text(
        mistral.read_text(encoding="utf-8")
        + "\n        configured_timeout = float(os.getenv('MISTRAL_TIMEOUT_SECONDS', '42'))\n",
        encoding="utf-8",
    )
    assert "Mistral-Client" in module.leftovers_in_tool(tool)
    runtime.write_text(
        runtime.read_text(encoding="utf-8") + "\nMISTRAL_PREFLIGHT_TIMEOUT_SECONDS = 0.5\n",
        encoding="utf-8",
    )
    assert "Ollama" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "MISTRAL_TIMEOUT_SECONDS" not in mistral.read_text(encoding="utf-8")
    assert "MISTRAL_PREFLIGHT_TIMEOUT_SECONDS" not in runtime.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_scheitert_wenn_mistral_export_bleibt(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    init = tool / "app" / "providers" / "__init__.py"
    init.write_text(
        "from app.providers.mistral_provider import LocalMistralProvider as LocalMistralProvider\n"
        "NAMES = ('LocalMistralProvider',)\n",
        encoding="utf-8",
    )
    ok, msg = module.apply_foundry(tool)
    assert ok is False
    assert "LocalMistralProvider" in msg or "exportiert" in msg


def test_anwenden_entfernt_regeln_export(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    init = tool / "app" / "providers" / "__init__.py"
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = init.read_text(encoding="utf-8")
    assert "LocalRuleProvider" not in text
    assert "FastEditorialProvider" not in text
    assert module.leftovers_in_tool(tool) == []
    init.write_text(
        text
        + "\nfrom .local import LocalRuleProvider\n"
        + '    "LocalRuleProvider",\n',
        encoding="utf-8",
    )
    assert "Provider-Export" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    leftover = init.read_text(encoding="utf-8")
    assert "LocalRuleProvider" not in leftover
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_stellt_bewertung_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    evaluation = tool / "app" / "evaluation.py"
    assert "run_pipeline(" in evaluation.read_text(encoding="utf-8")
    assert "Bewertung" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = evaluation.read_text(encoding="utf-8")
    assert "run_pipeline(" not in text
    assert "Keine lokale Bewertung" in text
    evaluation.write_text(
        "from app.pipeline import run_pipeline\n"
        "def evaluate_case(case):\n"
        "    return run_pipeline(case.input)\n",
        encoding="utf-8",
    )
    assert "Bewertung" in module.leftovers_in_tool(tool)


def test_anwenden_stellt_fremd_ki_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "Fremd-KI" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert module.leftovers_in_tool(tool) == []
    openai = tool / "app" / "providers" / "openai_provider.py"
    openai.write_text(
        "class OpenAIProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        "        return text\n",
        encoding="utf-8",
    )
    assert "Fremd-KI" in module.leftovers_in_tool(tool)


def test_anwenden_parkt_ci_rezepte(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "CI-Rezept" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert module.leftovers_in_tool(tool) == []
    (tool / ".github" / "workflows" / "tests.yml").write_text(
        "run: python -m app.evaluation\n", encoding="utf-8"
    )
    assert "CI-Rezept" in module.leftovers_in_tool(tool)
    (tool / ".github" / "workflows" / "tests.yml").unlink()
    (tool / ".github" / "workflows" / "release.yml").write_text(
        "name: Release\n        run: python -m app.evaluation\n",
        encoding="utf-8",
    )
    assert "CI-Rezept" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert not (tool / ".github" / "workflows" / "release.yml").is_file()
    assert (tool / ".github" / "workflows" / "release.yml.llp-alt").is_file()
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_stellt_desktop_pipeline_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    desktop = tool / "app" / "desktop.py"
    assert "run_pipeline(source, options)" in desktop.read_text(encoding="utf-8")
    assert "run_pipeline(" in desktop.read_text(encoding="utf-8")
    assert "Desktop-Pipeline" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = desktop.read_text(encoding="utf-8")
    assert "run_pipeline(source, options)" not in text
    assert "run_pipeline(" not in text
    assert "Die alte Oberflaeche startet nicht" in text
    text = text.replace(module.DESKTOP_PIPELINE_STUB, module.DESKTOP_PIPELINE_OLD, 1)
    desktop.write_text(text, encoding="utf-8")
    assert "Desktop-Pipeline" in module.leftovers_in_tool(tool)


def test_anwenden_entfernt_desktop_selbsttest_pipeline(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    desktop = tool / "app" / "desktop.py"
    assert 'run_pipeline("Gruesse", TransformOptions(provider="rules"' in desktop.read_text(
        encoding="utf-8"
    )
    assert "Desktop-Pipeline" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = desktop.read_text(encoding="utf-8")
    assert "run_pipeline(" not in text
    assert module.leftovers_in_tool(tool) == []
    desktop.write_text(
        text
        + '\n    result = run_pipeline(source, TransformOptions(provider="rules", rewrite_strength="light"))\n'
        + '    fast_result = run_pipeline(fast_source, TransformOptions(provider="fast-editor"))\n',
        encoding="utf-8",
    )
    assert "Desktop-Pipeline" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "run_pipeline(" not in desktop.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_stellt_lokal_provider_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "Lokal-Regeln" in module.leftovers_in_tool(tool)
    assert "Schnell-Editor" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    local_rules = tool / "app" / "providers" / "local.py"
    assert "Lokale Regeln sind abgeschaltet" in local_rules.read_text(encoding="utf-8")
    fast_editor = tool / "app" / "providers" / "fast_editor.py"
    assert "Schnell-Editor ist abgeschaltet" in fast_editor.read_text(encoding="utf-8")
    assert "LocalRuleProvider().rewrite" not in fast_editor.read_text(encoding="utf-8")
    local_rules.write_text(
        "class LocalRuleProvider:\n"
        "    def rewrite(self, text: str, constraints: SemanticConstraints, "
        "options: TransformOptions) -> str:\n"
        "        return text\n",
        encoding="utf-8",
    )
    assert "Lokal-Regeln" in module.leftovers_in_tool(tool)


def test_anwenden_entfernt_schnell_editor_regelaufruf(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "LocalRuleProvider().rewrite" in (tool / "app" / "providers" / "fast_editor.py").read_text(
        encoding="utf-8"
    )
    assert "Schnell-Editor" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    path = tool / "app" / "providers" / "fast_editor.py"
    text = path.read_text(encoding="utf-8")
    assert "LocalRuleProvider().rewrite" not in text
    assert "Lokale Regeln sind abgeschaltet" in text
    assert module.leftovers_in_tool(tool) == []
    path.write_text(
        text + "\n        cleaned = LocalRuleProvider().rewrite(text, constraints, options)\n",
        encoding="utf-8",
    )
    assert "Schnell-Editor" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "LocalRuleProvider().rewrite" not in path.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_entfernt_lokale_desktop_fassung(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    desktop = tool / "app" / "desktop.py"
    assert "sichere lokale" in desktop.read_text(encoding="utf-8").lower()
    assert "Regelfassung" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = desktop.read_text(encoding="utf-8")
    assert "sichere lokale" not in text.lower()
    text = text + "\nFoundry derzeit nicht erreichbar – sichere lokale Fassung wird sofort erstellt.\n"
    desktop.write_text(text, encoding="utf-8")
    assert "Regelfassung" in module.leftovers_in_tool(tool)


def test_anwenden_stellt_desktop_selbsttest_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    desktop = tool / "app" / "desktop.py"
    raw = desktop.read_text(encoding="utf-8")
    assert "report = run_self_test()" in raw
    assert "Selbsttest" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = desktop.read_text(encoding="utf-8")
    assert "report = run_self_test()" not in text
    assert "Kein Selbsttest mit Regeln oder Modellwahl" in text
    assert "return 2  # LLP-FOUNDRY-TOR" in text
    text = text.replace(module.SELF_TEST_STUB, module.SELF_TEST_OLD, 1)
    desktop.write_text(text, encoding="utf-8")
    assert "Selbsttest" in module.leftovers_in_tool(tool)


def test_anwenden_stellt_desktop_run_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    desktop = tool / "app" / "desktop.py"
    assert "self.root.mainloop()" in desktop.read_text(encoding="utf-8")
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = desktop.read_text(encoding="utf-8")
    assert "self.root.mainloop()" not in text
    assert "Die alte Oberflaeche startet nicht" in text
    text = text.replace(
        "raise SystemExit(\n"
        '            "Die alte Oberflaeche startet nicht. Nur Foundry, kein Mistral."\n'
        "        )  # LLP-FOUNDRY-TOR",
        "self.root.mainloop()",
        1,
    )
    desktop.write_text(text, encoding="utf-8")
    assert "Oberflaeche" in module.leftovers_in_tool(tool)


def test_anwenden_legt_startbare_sicherung_still(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    html_alt = tool / "web" / "TextVerbessern-Browser.html.llp-alt"
    html_alt.write_text(
        "<html><body><script>startEditor()</script></body></html>\n",
        encoding="utf-8",
    )
    assert "Sicherung-startbar" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert "Sicherung. Nicht starten" in html_alt.read_text(encoding="utf-8")
    assert "<script" not in html_alt.read_text(encoding="utf-8").lower()
    parked = tool / "_llp_parked" / "web" / "TextVerbessern-Browser.html.llp-alt.txt"
    assert parked.is_file()
    assert "startEditor" in parked.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_stellt_alte_cli_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    main = tool / "app" / "main.py"
    assert "result = run_pipeline" in main.read_text(encoding="utf-8")
    assert "CLI" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = main.read_text(encoding="utf-8")
    assert "Die alte CLI startet nicht" in text
    assert "result = run_pipeline" not in text
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_parkt_offline_js(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "Offline-JS" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert not (tool / "web" / "app.js").is_file()
    assert not (tool / "web" / "editor.js").is_file()
    assert (tool / "web" / "app.js.llp-alt").is_file()
    assert (tool / "web" / "editor.js.llp-alt").is_file()
    assert "Sicherung. Nicht starten" in (tool / "web" / "app.js.llp-alt").read_text(
        encoding="utf-8"
    )
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_ersetzt_banner_html_durch_stub(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    html = tool / "web" / "index.html"
    html.write_text(
        "<html><body>\n<!-- LLP-FOUNDRY-TOR -->\n"
        "<p>Kanzlei-Weg text_verbessern_foundry</p>\n"
        '<script src="./app.js"></script>\n</body></html>\n',
        encoding="utf-8",
    )
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = html.read_text(encoding="utf-8")
    assert "Offline-Datei startet nicht" in text
    assert "<script" not in text.lower()
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_stellt_liesmich_im_tool_um(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    lies = tool / "LIESMICH.txt"
    lies.write_text("Doppelklick auf TextVerbessern.exe. Gründlich mit Mistral.\n", encoding="utf-8")
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = lies.read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in text
    assert "TextVerbessern.exe" not in text
    assert (tool / "LIESMICH.txt.llp-alt").is_file()
    assert "Sicherung. Nicht starten" in (tool / "LIESMICH.txt.llp-alt").read_text(
        encoding="utf-8"
    )
    assert "TextVerbessern.exe" in (
        tool / "_llp_parked" / "LIESMICH.txt.llp-alt.txt"
    ).read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_legt_original_cmd_beiseite(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    live = tool / "TEXT VERBESSERN.original.cmd"
    live.write_text("@echo off\r\nstart TextVerbessern.exe\r\n", encoding="utf-8")
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert not live.is_file()
    parked = tool / "TEXT VERBESSERN.original.cmd.llp-alt"
    assert parked.is_file()
    assert "Sicherung. Nicht starten" in parked.read_text(encoding="utf-8")
    original = (
        tool / "_llp_parked" / "TEXT VERBESSERN.original.cmd.llp-alt.txt"
    ).read_text(encoding="utf-8")
    assert "TextVerbessern.exe" in original
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_ersetzt_einzelnen_regel_return(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    pipe = tool / "app" / "pipeline.py"
    text = pipe.read_text(encoding="utf-8")
    pipe.write_text(
        text.replace("return FoundryEditorialProvider()", "return LocalRuleProvider()", 1),
        encoding="utf-8",
    )
    assert "Pipeline" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "return LocalRuleProvider()" not in pipe.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_stellt_pipeline_regel_fallback_ab(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    assert "LocalRuleProvider().rewrite" in (tool / "app" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "Pipeline" in module.leftovers_in_tool(tool)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    text = (tool / "app" / "pipeline.py").read_text(encoding="utf-8")
    assert "LocalRuleProvider().rewrite" not in text
    assert "Lokale Regeln sind abgeschaltet" in text
    assert module.leftovers_in_tool(tool) == []
    pipe = tool / "app" / "pipeline.py"
    pipe.write_text(
        text + "\nrewritten = LocalRuleProvider().rewrite(text, semantics, selected)\n",
        encoding="utf-8",
    )
    assert "Pipeline" in module.leftovers_in_tool(tool)


def test_anwenden_entfernt_pipeline_regeln_name(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    pipe = tool / "app" / "pipeline.py"
    text = pipe.read_text(encoding="utf-8")
    assert "LocalRuleProvider.name" not in text
    assert "FastEditorialProvider.name" not in text
    assert "from .providers.local import LocalRuleProvider" not in text
    assert "from .providers.fast_editor import FastEditorialProvider" not in text
    pipe.write_text(
        text
        + "\n        applied_provider = LocalRuleProvider.name\n"
        + "        applied_provider = FastEditorialProvider.name\n",
        encoding="utf-8",
    )
    assert "Pipeline" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    leftover = pipe.read_text(encoding="utf-8")
    assert "LocalRuleProvider.name" not in leftover
    assert "FastEditorialProvider.name" not in leftover
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_ersetzt_einzelnen_mistral_return(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    pipe = tool / "app" / "pipeline.py"
    text = pipe.read_text(encoding="utf-8")
    pipe.write_text(
        text.replace("return FoundryEditorialProvider()", "return LocalMistralProvider()", 1),
        encoding="utf-8",
    )
    assert "Pipeline" in module.leftovers_in_tool(tool)
    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "return LocalMistralProvider()" not in pipe.read_text(encoding="utf-8")
    assert module.leftovers_in_tool(tool) == []


def test_anwenden_meldet_rest_wenn_patch_ausfaellt(tmp_path: Path, monkeypatch) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    monkeypatch.setattr(module, "apply", lambda root: [])
    ok, msg = module.apply_foundry(tool)
    assert ok is False
    assert "nicht alles umgestellt" in msg
    assert "Pipeline" in msg


def test_main_leise_ohne_tool_bleibt_still(monkeypatch, capsys) -> None:
    module = _load_anwenden()
    monkeypatch.setattr(module, "find_tool_root", lambda start=None: None)
    assert module.main(["--leise"]) == 0
    assert capsys.readouterr().out == ""
    assert module.main([]) == 2
    assert "nicht gefunden" in capsys.readouterr().out


def test_main_leise_bei_anwenden_fehler_ist_sichtbar(monkeypatch, capsys) -> None:
    module = _load_anwenden()
    monkeypatch.setattr(module, "find_tool_root", lambda start=None: Path("/tmp/rephraser"))
    monkeypatch.setattr(module, "apply_foundry", lambda root: (False, "kaputt"))
    assert module.main(["--leise"]) == 2
    assert capsys.readouterr().out == ""


def test_main_leise_bei_ausnahme_ist_sichtbar(monkeypatch, capsys) -> None:
    module = _load_anwenden()
    monkeypatch.setattr(module, "find_tool_root", lambda start=None: Path("/tmp/rephraser"))

    def _boom(root: Path) -> tuple[bool, str]:
        raise ValueError("kaputt")

    monkeypatch.setattr(module, "apply_foundry", _boom)
    assert module.main(["--leise"]) == 2
    assert capsys.readouterr().out == ""
    assert module.main([]) == 2
    assert "kaputt" in capsys.readouterr().out
