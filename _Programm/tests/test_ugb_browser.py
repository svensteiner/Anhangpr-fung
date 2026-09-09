"""Modus 3 im echten Chrome: Gesellschaft, Häkchen, kein unbekannt."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).resolve().parent / "modus3_browser.mjs"
PUPPETEER_DIR = Path("/tmp/llp-browser")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _ensure_puppeteer() -> bool:
    marker = PUPPETEER_DIR / "node_modules" / "puppeteer-core"
    if marker.is_dir():
        return True
    if not shutil.which("npm"):
        return False
    PUPPETEER_DIR.mkdir(parents=True, exist_ok=True)
    pkg = PUPPETEER_DIR / "package.json"
    if not pkg.is_file():
        pkg.write_text('{"name":"llp-browser","private":true}\n', encoding="utf-8")
    proc = subprocess.run(
        ["npm", "install", "puppeteer-core@24.15.0", "--no-fund", "--silent"],
        cwd=PUPPETEER_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode == 0 and marker.is_dir()


@pytest.mark.skipif(
    not shutil.which("google-chrome") and not shutil.which("google-chrome-stable"),
    reason="Chrome nicht vorhanden",
)
@pytest.mark.skipif(not shutil.which("node"), reason="Node nicht vorhanden")
def test_ugb_browser_click_through(tmp_path: Path) -> None:
    if not _ensure_puppeteer():
        pytest.skip("puppeteer-core konnte nicht eingerichtet werden")

    import docx

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app as webapp

    doc = docx.Document()
    doc.add_paragraph(
        "Die Musterfirma Handels GmbH ist eine kleine Kapitalgesellschaft. "
        "Die Vorräte werden zu Anschaffungskosten bewertet. "
        "Die Vorratsbewertung erfolgt zu Anschaffungskosten."
    )
    anhang = tmp_path / "anhang.docx"
    doc.save(str(anhang))

    port = _free_port()
    thread = threading.Thread(
        target=lambda: webapp.app.run(
            host="127.0.0.1",
            port=port,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
    )
    thread.start()
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                break
        except OSError:
            time.sleep(0.1)
    else:
        pytest.fail("Flask-Server ist nicht gestartet")

    out_dir = ROOT / "Ergebnisse"
    before = {p.resolve() for p in out_dir.glob("*.xlsx")} if out_dir.is_dir() else set()

    env = os.environ.copy()
    env["CHROME_PATH"] = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or ""
    proc = subprocess.run(
        ["node", str(SCRIPT), f"http://127.0.0.1:{port}/", str(anhang)],
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BROWSER_OK" in proc.stdout
    assert "unbekannt" not in proc.stdout.lower()
    assert "gmbh" in proc.stdout.lower()
    assert "klein" in proc.stdout.lower()
    if out_dir.is_dir():
        for path in out_dir.glob("*.xlsx"):
            if path.resolve() not in before:
                path.unlink(missing_ok=True)
