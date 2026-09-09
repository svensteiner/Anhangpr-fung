"""Microsoft Foundry – einziger Modellzugang für LLP-Tools.

Kein stiller Wechsel auf einen anderen Anbieter. Schlüssel nur aus der
Umgebung bzw. der lokalen .env neben diesem Modul. Anfragen setzen
store=False. Prompt- und Antworttexte werden nicht geloggt.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATE_API_VERSION = re.compile(r"^\d{4}-\d{2}-\d{2}")

_ALLOWED_PROVIDER = "foundry"
_OFFICE_SHARED = Path(r"K:\LLP Wirtschaftsprüfung\AI Tools\_Gemeinsam")
_ENV_LOADED = False
_ENDPOINT_KEYS = (
    "FOUNDRY_ENDPOINT",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_AI_ENDPOINT",
    "AZURE_AI_FOUNDRY_ENDPOINT",
)
_DEPLOYMENT_KEYS = (
    "FOUNDRY_DEPLOYMENT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "AZURE_OPENAI_MODEL",
)
_KEY_KEYS = (
    "FOUNDRY_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AZURE_AI_API_KEY",
)
_VERSION_KEYS = (
    "FOUNDRY_API_VERSION",
    "AZURE_OPENAI_API_VERSION",
)


class CompanyAIError(Exception):
    """Foundry nicht nutzbar oder Anfrage fehlgeschlagen."""


@dataclass(frozen=True)
class Config:
    enabled: bool
    provider: str
    endpoint: str
    deployment: str
    api_key: str
    api_version: str


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    label: str


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on", "ja"}


def _env_files() -> list[Path]:
    roots: list[Path] = []
    shared = os.environ.get("LLP_SHARED_AI_ROOT")
    if shared:
        roots.append(Path(shared))
    roots.append(_OFFICE_SHARED)
    here = Path(__file__).resolve().parent
    roots.append(here.parent)
    try:
        roots.append(here.parents[2] / "_Gemeinsam")
    except IndexError:
        pass
    files: list[Path] = []
    for root in roots:
        files.append(root / "llp_ai" / ".env")
        files.append(root / ".env")
    files.append(here / ".env")
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _apply_env_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _load_env_file() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    for path in _env_files():
        if path.is_file():
            _apply_env_file(path)
    _ENV_LOADED = True


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _normalize_provider(raw: str) -> str:
    name = (raw or "").strip().lower()
    if name in {"", "foundry", "azure", "azure-openai", "azure_openai", "microsoft"}:
        return _ALLOWED_PROVIDER
    return name


def _explicitly_disabled() -> bool:
    raw = os.environ.get("COMPANY_AI_ENABLED")
    if raw is None or raw.strip() == "":
        return False
    return not _truthy(raw)


def get_config() -> Config:
    _load_env_file()
    endpoint = _first_env(*_ENDPOINT_KEYS).rstrip("/")
    deployment = _first_env(*_DEPLOYMENT_KEYS)
    api_key = _first_env(*_KEY_KEYS)
    api_version = _first_env(*_VERSION_KEYS) or "v1"
    provider = _normalize_provider(_first_env("COMPANY_AI_PROVIDER"))
    has_creds = bool(endpoint and deployment and api_key)
    enabled = (not _explicitly_disabled()) and has_creds
    return Config(
        enabled=enabled,
        provider=provider,
        endpoint=endpoint,
        deployment=deployment,
        api_key=api_key,
        api_version=api_version,
    )


def is_ai_enabled() -> bool:
    return get_config().enabled


def is_ai_ready() -> bool:
    cfg = get_config()
    if not cfg.enabled:
        return False
    if cfg.provider != _ALLOWED_PROVIDER:
        return False
    return bool(cfg.endpoint and cfg.deployment and cfg.api_key)


def describe_status() -> dict[str, Any]:
    """Status ohne Schlüssel, Endpunkt oder Prompt-Inhalt."""
    cfg = get_config()
    provider_ok = cfg.provider == _ALLOWED_PROVIDER
    endpoint_ok = bool(cfg.endpoint)
    deployment_ok = bool(cfg.deployment)
    key_ok = bool(cfg.api_key)
    bereit = is_ai_ready()
    irgendetwas = endpoint_ok or deployment_ok or key_ok
    if _explicitly_disabled():
        hinweis = (
            "Foundry ist bewusst ausgeschaltet. Anhangsprüfer: ohne Modell (Heuristik). "
            "Text verbessern ändert den Text nicht."
        )
    elif not provider_ok:
        hinweis = "Anbieter ist nicht Foundry. Es findet kein stiller Wechsel statt."
    elif irgendetwas and not (endpoint_ok and deployment_ok and key_ok):
        fehlend = [
            name for name, ok in (
                ("Endpoint", endpoint_ok),
                ("Deployment", deployment_ok),
                ("Schlüssel", key_ok),
            ) if not ok
        ]
        hinweis = "Foundry ist unvollständig eingerichtet (" + ", ".join(fehlend) + ")."
    elif not irgendetwas:
        hinweis = (
            "Foundry-Zugang nicht gefunden. Es gilt die bestehende Datei "
            "llp_ai\\.env auf dem Server (derselbe Zugang wie bisher beim Anhangsprüfer)."
        )
    else:
        hinweis = "Foundry ist eingerichtet. Die Tools können den zentralen Layer nutzen."
    kurz = "KI: bereit" if bereit else "KI: aus – Heuristik"
    return {
        "enabled": cfg.enabled,
        "provider_ok": provider_ok,
        "endpoint_gesetzt": endpoint_ok,
        "deployment_gesetzt": deployment_ok,
        "schluessel_gesetzt": key_ok,
        "bereit": bereit,
        "hinweis": hinweis,
        "kurz": kurz,
    }


def active_provider() -> ProviderInfo:
    if is_ai_ready():
        return ProviderInfo("foundry", "Microsoft Foundry")
    return ProviderInfo("", "")


def _legacy_azure_chat_url(cfg: Config) -> bool:
    """Klassische Azure-OpenAI-URL, wie sie beim Anhangsprüfer schon ging."""
    return bool(_DATE_API_VERSION.match(cfg.api_version or ""))


def _chat_url(cfg: Config) -> str:
    base = cfg.endpoint.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if _legacy_azure_chat_url(cfg):
        return (
            f"{base}/openai/deployments/{cfg.deployment}/chat/completions"
            f"?api-version={cfg.api_version}"
        )
    if "/openai/" in base:
        return base + "/chat/completions"
    return f"{base}/openai/{cfg.api_version}/chat/completions"


def _post_chat(prompt: str, *, json_mode: bool) -> str:
    if not is_ai_ready():
        raise CompanyAIError("Foundry ist aus oder nicht eingerichtet.")
    cfg = get_config()
    body: dict[str, Any] = {
        "model": cfg.deployment,
        "store": False,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        _chat_url(cfg),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": cfg.api_key,
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise CompanyAIError("Foundry hat die Anfrage abgelehnt.") from exc
    except Exception as exc:
        raise CompanyAIError("Foundry ist nicht erreichbar.") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
    except Exception as exc:
        raise CompanyAIError("Foundry-Antwort war ungültig.") from exc
    if not isinstance(text, str) or not text.strip():
        raise CompanyAIError("Foundry-Antwort war leer.")
    return text


def ask_ai(prompt: str, **_kwargs: Any) -> str:
    return _post_chat(prompt, json_mode=False)


def ask_json(prompt: str, **_kwargs: Any) -> dict:
    text = _post_chat(prompt, json_mode=True)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CompanyAIError("Foundry-Antwort war kein JSON.") from exc
    if not isinstance(data, dict):
        raise CompanyAIError("Foundry-Antwort war kein JSON-Objekt.")
    return data
