"""Einfaches Text verbessern nur über den zentralen Foundry-Layer.

Kein Mistral, kein Ollama, kein stiller Wechsel. Ist Foundry aus,
bleibt der Text unverändert und die Oberfläche sagt das klar.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from llp_ai.company_ai import CompanyAIError, ask_ai, describe_status, is_ai_ready

MAX_CHARS = 20_000
HOST = "127.0.0.1"

PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Text verbessern – Foundry</title>
  <style>
    body { font: 16px/1.45 system-ui, sans-serif; max-width: 820px; margin: 32px auto; color: #16332a; }
    h1 { font-size: 1.5rem; }
    textarea { width: 100%; min-height: 180px; font: 1rem/1.5 system-ui; padding: 10px; }
    button { margin-top: 12px; min-height: 2.8rem; padding: 0 18px; font-weight: 650; }
    button:disabled { opacity: .55; }
    .hint { color: #4a6a5c; margin: 8px 0 18px; }
    .err { color: #8a1f1f; margin-top: 12px; }
    label { display: block; margin-top: 16px; font-weight: 650; }
  </style>
</head>
<body>
  <h1>Text verbessern</h1>
  <p class="hint" id="status">KI wird geprüft…</p>
  <p class="hint">Nur Microsoft Foundry (llp_ai). Kein Mistral, kein Ollama.</p>
  <label for="quelle">Ausgangstext</label>
  <textarea id="quelle" maxlength="20000" placeholder="Text hier einfügen…"></textarea>
  <button id="run" type="button">Gründlich mit Foundry</button>
  <p class="err" id="fehler"></p>
  <label for="ergebnis">Ergebnis</label>
  <textarea id="ergebnis" readonly></textarea>
  <script>
    fetch('/status').then(r => r.json()).then(d => {
      document.getElementById('status').textContent = d.kurz || 'KI: aus';
    }).catch(() => {
      document.getElementById('status').textContent = 'KI: Status nicht lesbar';
    });
    document.getElementById('run').onclick = async () => {
      const text = document.getElementById('quelle').value;
      const btn = document.getElementById('run');
      const err = document.getElementById('fehler');
      err.textContent = '';
      btn.disabled = true;
      try {
        const resp = await fetch('/umschreiben', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text}),
        });
        const data = await resp.json();
        if (!resp.ok) {
          err.textContent = data.fehler || 'Foundry ist nicht bereit.';
          return;
        }
        document.getElementById('ergebnis').value = data.text || '';
      } catch (e) {
        err.textContent = 'Die Anfrage ist fehlgeschlagen. Bitte erneut versuchen.';
      } finally {
        btn.disabled = false;
      }
    };
  </script>
</body>
</html>
"""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def rewrite(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Bitte zuerst einen Text einfügen.")
    if len(cleaned) > MAX_CHARS:
        raise ValueError(f"Bitte höchstens {MAX_CHARS} Zeichen verwenden.")
    if not is_ai_ready():
        raise CompanyAIError(
            "Foundry ist aus. Es gibt keinen Wechsel auf Mistral oder Ollama."
        )
    prompt = (
        "Formuliere den folgenden Text klarer und professioneller. "
        "Namen, Zahlen und Fakten unverändert lassen. "
        "Nur den umgeschriebenen Text zurückgeben.\n\n"
        f"{cleaned}"
    )
    return ask_ai(prompt).strip()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/status":
            status = describe_status()
            payload = json.dumps({"kurz": status["kurz"], "bereit": status["bereit"]})
            self._send(200, payload.encode("utf-8"), "application/json")
            return
        self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/umschreiben":
            self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            text = rewrite(str(data.get("text") or ""))
        except json.JSONDecodeError:
            payload = json.dumps({"fehler": "Die Anfrage war ungültig."})
            self._send(400, payload.encode("utf-8"), "application/json")
            return
        except ValueError as exc:
            payload = json.dumps({"fehler": str(exc)})
            self._send(400, payload.encode("utf-8"), "application/json")
            return
        except CompanyAIError as exc:
            payload = json.dumps({"fehler": str(exc)})
            self._send(503, payload.encode("utf-8"), "application/json")
            return
        payload = json.dumps({"text": text})
        self._send(200, payload.encode("utf-8"), "application/json")


def serve(port: int | None = None, open_browser: bool = True) -> ThreadingHTTPServer:
    chosen = port or _free_port()
    server = ThreadingHTTPServer((HOST, chosen), Handler)
    if open_browser:
        url = f"http://{HOST}:{chosen}/"
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    return server


def main() -> int:
    server = serve()
    host, port = server.server_address
    print("Text verbessern (nur Foundry). Browser: "
          f"http://{host}:{port}/")
    print("Zum Beenden dieses Fenster schließen.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
