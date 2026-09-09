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
    modus = text_verbessern_modus(desktop)
    return {
        "foundry": describe_status(),
        "anhang": find_anhang(roots),
        "text_desktop": desktop,
        "text_modus": modus,
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
    lines.append("  Keine Schluessel in dieser Anzeige.")
    lines.append("  Anleitung: ANLEITUNG.txt in diesem Ordner.")
    return "\n".join(lines)


def text_foundry_ok(start: Path | None = None) -> bool:
    return report(start)["text_modus"] == "Foundry"


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
    if data["text_modus"] == "noch Mistral":
        return 2
    return 0 if foundry["bereit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
