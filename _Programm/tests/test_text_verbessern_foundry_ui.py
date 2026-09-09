"""Foundry-Textseite: nur llp_ai, kein stiller Modellwechsel."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

SHARED = Path(__file__).resolve().parents[2] / "_Gemeinsam"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

SERVER = SHARED / "text_verbessern_foundry" / "server.py"


def _load():
    spec = importlib.util.spec_from_file_location("text_verbessern_foundry_server", SERVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _serve(module):
    server = module.serve(open_browser=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def _json(url: str, data: dict | None = None) -> tuple[int, dict | str]:
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="GET" if data is None else "POST",
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if "json" in resp.headers.get("Content-Type", "") else raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def test_seite_nennt_nur_foundry() -> None:
    module = _load()
    server, base = _serve(module)
    try:
        req = urllib.request.urlopen(base + "/", timeout=5)
        html = req.read().decode("utf-8")
    finally:
        server.shutdown()
    low = html.lower()
    assert "foundry" in low
    assert "mistral" in low and "kein mistral" in low
    assert "ollama" in low and "kein ollama" in low
    assert "api-key" not in low
    assert "FOUNDRY_API_KEY" not in html
    assert "Beenden" in html
    assert "/beenden" in html
    assert "foundryBereit" in html
    assert "run').disabled" in html or 'run").disabled' in html


def test_umschreiben_ohne_foundry_ohne_stillen_wechsel(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "is_ai_ready", lambda: False)

    def _boom(_prompt: str) -> str:
        raise AssertionError("ask_ai darf ohne Foundry nicht laufen")

    monkeypatch.setattr(module, "ask_ai", _boom)
    server, base = _serve(module)
    try:
        code, payload = _json(base + "/umschreiben", {"text": "Bitte den Satz glätten."})
    finally:
        server.shutdown()
    assert code == 503
    assert isinstance(payload, dict)
    err = payload["fehler"].lower()
    assert "foundry" in err
    assert "mistral" in err or "ollama" in err


def test_umschreiben_mit_foundry(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "is_ai_ready", lambda: True)
    monkeypatch.setattr(module, "ask_ai", lambda prompt: "Klarer Satz.")
    server, base = _serve(module)
    try:
        code, payload = _json(base + "/umschreiben", {"text": "unklarer satz"})
        status_code, status = _json(base + "/status")
    finally:
        server.shutdown()
    assert code == 200
    assert payload == {"text": "Klarer Satz."}
    assert status_code == 200
    assert "kurz" in status
    assert "api_key" not in status
    assert "endpoint" not in status


def test_leerer_text_wird_abgelehnt(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "is_ai_ready", lambda: True)
    server, base = _serve(module)
    try:
        code, payload = _json(base + "/umschreiben", {"text": "   "})
    finally:
        server.shutdown()
    assert code == 400
    assert "Text" in payload["fehler"]


def test_beenden_haelt_den_server_an() -> None:
    module = _load()
    server, base = _serve(module)
    code, payload = _json(base + "/beenden", {})
    assert code == 200
    assert payload == {"ok": True}
    deadline = time.time() + 3
    stopped = False
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/", timeout=0.3)
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            stopped = True
            break
        time.sleep(0.05)
    if not stopped:
        server.shutdown()
    assert stopped


@pytest.mark.skipif(
    not shutil.which("google-chrome") and not shutil.which("google-chrome-stable"),
    reason="Chrome nicht vorhanden",
)
@pytest.mark.skipif(not shutil.which("node"), reason="Node nicht vorhanden")
def test_foundry_seite_im_browser_ohne_stillen_wechsel() -> None:
    tests_dir = Path(__file__).resolve().parent
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    from test_ugb_browser import _ensure_puppeteer

    if not _ensure_puppeteer():
        pytest.skip("puppeteer-core konnte nicht eingerichtet werden")
    module = _load()
    server, base = _serve(module)
    env = os.environ.copy()
    env["CHROME_PATH"] = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or ""
    script = Path(__file__).resolve().parent / "text_foundry_browser.mjs"
    try:
        proc = subprocess.run(
            ["node", str(script), base + "/"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BROWSER_OK" in proc.stdout
    assert "foundry" in proc.stdout.lower()
    assert "mistral" in proc.stdout.lower() or "ollama" in proc.stdout.lower()
