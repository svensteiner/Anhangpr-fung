"""Microsoft Foundry – einziger Modellzugang für LLP-Tools.

Kein stiller Wechsel auf einen anderen Anbieter. Schlüssel nur aus der
Umgebung bzw. der lokalen .env neben diesem Modul. Anfragen setzen
store=False. Prompt- und Antworttexte werden nicht geloggt.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ALLOWED_PROVIDER = "foundry"
_ENV_FILE = Path(__file__).resolve().parent / ".env"
_ENV_LOADED = False


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


def _load_env_file() -> None:
    global _ENV_LOADED
    if _ENV_LOADED or not _ENV_FILE.is_file():
        _ENV_LOADED = True
        return
    try:
        text = _ENV_FILE.read_text(encoding="utf-8")
    except OSError:
        _ENV_LOADED = True
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
    _ENV_LOADED = True


def get_config() -> Config:
    _load_env_file()
    return Config(
        enabled=_truthy(os.environ.get("COMPANY_AI_ENABLED")),
        provider=(os.environ.get("COMPANY_AI_PROVIDER") or "").strip().lower(),
        endpoint=(os.environ.get("FOUNDRY_ENDPOINT") or "").strip().rstrip("/"),
        deployment=(os.environ.get("FOUNDRY_DEPLOYMENT") or "").strip(),
        api_key=(os.environ.get("FOUNDRY_API_KEY") or "").strip(),
        api_version=(os.environ.get("FOUNDRY_API_VERSION") or "v1").strip() or "v1",
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
    if not cfg.enabled:
        hinweis = "Foundry ist aus. Die Tools arbeiten ohne Modell (Heuristik/Regeln)."
    elif not provider_ok:
        hinweis = "Anbieter ist nicht Foundry. Es findet kein stiller Wechsel statt."
    elif not (endpoint_ok and deployment_ok and key_ok):
        fehlend = [
            name for name, ok in (
                ("Endpoint", endpoint_ok),
                ("Deployment", deployment_ok),
                ("Schlüssel", key_ok),
            ) if not ok
        ]
        hinweis = "Foundry ist unvollständig eingerichtet (" + ", ".join(fehlend) + ")."
    else:
        hinweis = "Foundry ist eingerichtet. Die Tools können den zentralen Layer nutzen."
    return {
        "enabled": cfg.enabled,
        "provider_ok": provider_ok,
        "endpoint_gesetzt": endpoint_ok,
        "deployment_gesetzt": deployment_ok,
        "schluessel_gesetzt": key_ok,
        "bereit": bereit,
        "hinweis": hinweis,
    }


def active_provider() -> ProviderInfo:
    if is_ai_ready():
        return ProviderInfo("foundry", "Microsoft Foundry")
    return ProviderInfo("", "")


def _chat_url(cfg: Config) -> str:
    base = cfg.endpoint
    if base.endswith("/chat/completions"):
        return base
    if "/openai/" in base:
        return base.rstrip("/") + "/chat/completions"
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
