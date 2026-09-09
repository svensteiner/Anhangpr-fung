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


def text_cmd_modus(path: Path | None) -> str:
    if path is None:
        return "nicht gefunden"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "LLP-FOUNDRY-TOR" in text:
        return "Foundry-Tor"
    return "noch alt"


def find_live_text_exe(roots: list[Path]) -> Path | None:
    for root in roots:
        for name in TOOL_NAMES["text"]:
            for exe_name in ("TextVerbessern.exe", "TEXT VERBESSERN.exe", "rephraser.exe"):
                candidate = root / name / exe_name
                if candidate.is_file():
                    return candidate
    return None


def find_foundry_provider(roots: list[Path]) -> Path | None:
    for root in roots:
        found = _first_existing(root, TOOL_NAMES["text"], "app/providers/foundry_provider.py")
        if found is not None:
            return found
    return None


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
    exe = find_live_text_exe(roots)
    provider = find_foundry_provider(roots)
    modus = text_verbessern_modus(desktop)
    start_modus = text_startskript_modus(startskript)
    cmd_modus = text_cmd_modus(cmd)
    return {
        "foundry": describe_status(),
        "anhang": find_anhang(roots),
        "text_desktop": desktop,
        "text_modus": modus,
        "text_startskript": startskript,
        "text_start": start_modus,
        "text_cmd": cmd,
        "text_cmd_modus": cmd_modus,
        "text_exe": exe,
        "text_provider": provider,
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
    lines.append("  Keine Schluessel in dieser Anzeige.")
    lines.append("  Anleitung: ANLEITUNG.txt in diesem Ordner.")
    return "\n".join(lines)


def text_foundry_ok(start: Path | None = None) -> bool:
    data = report(start)
    start_ok = data["text_start"] in {"Foundry-Tor", "nicht gefunden"}
    cmd_ok = data["text_cmd_modus"] in {"Foundry-Tor", "nicht gefunden"}
    exe_ok = data["text_exe"] is None
    provider_ok = data["text_provider"] is not None or data["text_desktop"] is None
    return (
        data["text_modus"] == "Foundry"
        and start_ok
        and cmd_ok
        and exe_ok
        and provider_ok
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--kurz" in args:
        print(describe_status()["kurz"])
        return 0
    if "--text-foundry" in args:
        return 0 if text_foundry_ok() else 1
    data = report()
    print(format_report(data))
    foundry = data["foundry"]
    assert isinstance(foundry, dict)
    leftover = (
        data["text_modus"] == "noch Mistral"
        or data["text_start"] == "noch Streamlit"
        or data["text_cmd_modus"] == "noch alt"
        or data["text_exe"] is not None
        or (data["text_desktop"] is not None and data["text_provider"] is None)
    )
    if leftover:
        return 2
    return 0 if foundry["bereit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
