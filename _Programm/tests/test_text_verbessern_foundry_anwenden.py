"""Share-Patch: Text verbessern auf Foundry umstellen, ohne Ollama/Mistral."""

from __future__ import annotations

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
    raise RuntimeError(f"Unknown provider: {name}")
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
'''

STREAMLIT_MAIN = '''from app.local_runtime import (
    LOCAL_MODEL_MAX_CHARACTERS,
    local_mistral_ready,
    local_model_eligible,
    preflight_local_mistral,
)
from app.pipeline import run_pipeline
from app.providers.base import ProviderError


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
    return tool


def test_anwenden_stellt_text_verbessern_auf_foundry_um(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert "Foundry-Anbindung" in msg
    assert (tool / "app" / "providers" / "foundry_provider.py").is_file()
    provider = (tool / "app" / "providers" / "foundry_provider.py").read_text(encoding="utf-8")
    assert "ask_ai" in provider
    assert "ollama" in provider.lower()
    assert "No silent switch" in provider or "kein stiller" in provider.lower()

    pipeline = (tool / "app" / "pipeline.py").read_text(encoding="utf-8")
    assert "from .providers.foundry_provider import FoundryEditorialProvider, HybridFoundryProvider" in pipeline
    assert '"foundry", "company-ai"' in pipeline
    assert '"rules+foundry"' in pipeline

    desktop = (tool / "app" / "desktop.py").read_text(encoding="utf-8")
    assert 'MODE_STRONG = "Gründlich mit Foundry (Büro-KI)"' in desktop
    assert "from app.providers.foundry_provider import foundry_ready" in desktop
    assert 'return "rules+foundry", "substantial"' in desktop
    assert "if foundry_ready():" in desktop
    assert "if not mistral_ready:" not in desktop
    assert "thorough_ready = foundry_ready()" in desktop
    assert "local_model_eligible(current_source, self._mistral_can_start())" not in desktop
    assert "preflight_local_mistral()" not in desktop
    assert "if not foundry_ready():" in desktop
    assert '"mistral" in provider' not in desktop
    assert '"foundry" in provider' in desktop
    assert "rules+mistral-local" not in desktop

    streamlit = (tool / "app" / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "Gründlich mit Foundry (Büro-KI)" in streamlit
    assert "Gründlich mit Mistral" not in streamlit
    assert "mistral_ready = foundry_ready()" in streamlit
    assert "mistral_for_text = foundry_ready()" in streamlit
    assert "local_model_eligible(st.session_state.source_text, mistral_ready)" not in streamlit
    assert "preflight_local_mistral()" not in streamlit
    assert "mistral_preflight_failed = not foundry_ready()" in streamlit
    assert "rules+foundry" in streamlit
    assert "rules+mistral-local" not in streamlit
    assert '"foundry" in provider' in streamlit
    assert '"mistral" in provider' not in streamlit

    launcher = (tool / "TEXT VERBESSERN.cmd").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in launcher
    assert "mistral-rephraser wird nicht gestartet" in launcher.lower()
    assert "TEXT VERBESSERN.original.cmd" not in launcher
    assert "TextVerbessern.exe" not in launcher
    assert "from app.desktop import main" not in launcher
    assert "app\\desktop.py" not in launcher
    assert "text_verbessern_foundry" in launcher.lower()
    backup = (tool / "TEXT VERBESSERN.original.cmd").read_text(encoding="utf-8")
    assert "TextVerbessern.exe" in backup
    assert "LLP-FOUNDRY-TOR" not in backup

    ps1 = (tool / "scripts" / "start_windows.ps1").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in ps1
    assert "streamlit" not in ps1.lower()
    assert "mistral-rephraser wird nicht gestartet" in ps1.lower()
    assert "text_verbessern_foundry" in ps1.lower()
    assert "foundry-seite" in ps1.lower()
    ps1_bak = (tool / "scripts" / "start_windows.ps1.llp-alt").read_text(encoding="utf-8")
    assert "streamlit" in ps1_bak.lower()
    assert "LLP-FOUNDRY-TOR" not in ps1_bak

    note = (tool / "LIESMICH-FOUNDRY.txt").read_text(encoding="utf-8")
    assert "LLP-FOUNDRY-TOR" in note
    assert "kein mistral" in note.lower()
    assert "kein streamlit" in note.lower()
    schnell = (tool / "SCHNELLSTART.md").read_text(encoding="utf-8")
    assert schnell == note
    assert "textverbessern.exe" not in schnell.lower()
    schnell_bak = (tool / "SCHNELLSTART.md.llp-alt").read_text(encoding="utf-8")
    assert "Gründlich mit Mistral" in schnell_bak
    assert "LLP-FOUNDRY-TOR" not in schnell_bak

    ok2, msg2 = module.apply_foundry(tool)
    assert ok2, msg2
    assert "bereits auf Foundry" in msg2
    backup2 = (tool / "TEXT VERBESSERN.original.cmd").read_text(encoding="utf-8")
    assert backup2 == backup
    ps1_again = (tool / "scripts" / "start_windows.ps1").read_text(encoding="utf-8")
    assert ps1_again == ps1
    assert (tool / "scripts" / "start_windows.ps1.llp-alt").read_text(encoding="utf-8") == ps1_bak


def test_anwenden_ohne_windows_startskript_bleibt_ok(tmp_path: Path) -> None:
    module = _load_anwenden()
    tool = _fake_rephraser(tmp_path)
    (tool / "scripts" / "start_windows.ps1").unlink()
    ok, msg = module.apply_foundry(tool)
    assert ok, msg
    assert not (tool / "scripts" / "start_windows.ps1").is_file()


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
