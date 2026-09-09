"""Tests für den zentralen Foundry-Layer – ohne Netz und ohne Schlüssel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "_Gemeinsam"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from llp_ai import company_ai as layer  # noqa: E402


def _reset(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    monkeypatch.setattr(layer, "_ENV_LOADED", True)
    for key in (
        "COMPANY_AI_ENABLED",
        "COMPANY_AI_PROVIDER",
        "FOUNDRY_ENDPOINT",
        "FOUNDRY_DEPLOYMENT",
        "FOUNDRY_API_KEY",
        "FOUNDRY_API_VERSION",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_ready_false_when_disabled(monkeypatch):
    _reset(monkeypatch, COMPANY_AI_ENABLED="false", COMPANY_AI_PROVIDER="foundry")
    assert layer.is_ai_enabled() is False
    assert layer.is_ai_ready() is False


def test_ready_false_for_other_provider(monkeypatch):
    _reset(
        monkeypatch,
        COMPANY_AI_ENABLED="true",
        COMPANY_AI_PROVIDER="ollama",
        FOUNDRY_ENDPOINT="https://example.openai.azure.com",
        FOUNDRY_DEPLOYMENT="gpt",
        FOUNDRY_API_KEY="x",
    )
    assert layer.is_ai_ready() is False


def test_ready_true_only_for_foundry_with_credentials(monkeypatch):
    _reset(
        monkeypatch,
        COMPANY_AI_ENABLED="true",
        COMPANY_AI_PROVIDER="foundry",
        FOUNDRY_ENDPOINT="https://example.openai.azure.com",
        FOUNDRY_DEPLOYMENT="gpt",
        FOUNDRY_API_KEY="x",
    )
    assert layer.is_ai_ready() is True
    assert layer.active_provider().name == "foundry"


def test_ask_json_raises_when_not_ready(monkeypatch):
    _reset(monkeypatch, COMPANY_AI_ENABLED="false")
    with pytest.raises(layer.CompanyAIError):
        layer.ask_json("egal")


def test_chat_sends_store_false_and_no_other_provider(monkeypatch):
    _reset(
        monkeypatch,
        COMPANY_AI_ENABLED="true",
        COMPANY_AI_PROVIDER="foundry",
        FOUNDRY_ENDPOINT="https://example.openai.azure.com",
        FOUNDRY_DEPLOYMENT="llp-gpt",
        FOUNDRY_API_KEY="secret-key",
    )
    captured: dict = {}

    class _Resp:
        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": '{"ok": true}'}}],
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=90):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = json.loads(request.data.decode())
        return _Resp()

    monkeypatch.setattr(layer.urllib.request, "urlopen", fake_urlopen)
    data = layer.ask_json("Prüfe den Anhang.")
    assert data == {"ok": True}
    assert captured["body"]["store"] is False
    assert captured["body"]["model"] == "llp-gpt"
    assert captured["headers"]["api-key"] == "secret-key"
    assert captured["url"].endswith("/openai/v1/chat/completions")


def test_describe_status_has_no_secrets_when_off(monkeypatch):
    _reset(monkeypatch, COMPANY_AI_ENABLED="false", COMPANY_AI_PROVIDER="foundry")
    status = layer.describe_status()
    blob = json.dumps(status)
    assert "api_key" not in blob
    assert "FOUNDRY" not in blob
    assert status["bereit"] is False
    assert "ohne Modell" in status["hinweis"]


def test_describe_status_names_missing_parts(monkeypatch):
    _reset(
        monkeypatch,
        COMPANY_AI_ENABLED="true",
        COMPANY_AI_PROVIDER="foundry",
        FOUNDRY_ENDPOINT="https://example.openai.azure.com",
    )
    status = layer.describe_status()
    assert status["endpoint_gesetzt"] is True
    assert status["schluessel_gesetzt"] is False
    assert "Schlüssel" in status["hinweis"]
    assert "https://" not in json.dumps(status)


def test_healthz_foundry_status_has_no_secrets():
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import app as webapp

    data = webapp.app.test_client().get("/healthz").get_json()
    assert data["foundry_bereit"] is False
    assert "ohne Modell" in data["foundry"]["hinweis"] or "nicht erreichbar" in data["foundry"]["hinweis"]
    blob = json.dumps(data)
    assert "api_key" not in blob
    assert "FOUNDRY_API_KEY" not in blob


def test_wrapper_stays_isolated_in_default_tests():
    from anhangspruefer.services import company_ai

    assert company_ai.is_ai_ready() is False
