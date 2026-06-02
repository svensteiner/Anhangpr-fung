"""
Markdown-Report für den Vorjahresvergleich.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .comparator import CompareResult


def _fmt(val):
    if val is None:
        return "—"
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def generate_report(result: CompareResult, output_path: Path) -> Path:
    """Schreibt einen Markdown-Bericht zum Vergleichsergebnis."""
    stats = result.stats
    lines: list[str] = []

    lines.append("# Vorjahresvergleich – Anhang")
    lines.append("")
    lines.append(f"**Erstellt:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"- **Aktueller Anhang:** `{result.current_pdf.name}`")
    lines.append(f"- **Vorjahres-Anhang:** `{result.prior_pdf.name}`")
    lines.append("")
    lines.append("## Zusammenfassung")
    lines.append("")
    lines.append("| Status | Anzahl |")
    lines.append("|---|---:|")
    lines.append(f"| OK (Zahlen stimmen) | {stats.get('OK', 0)} |")
    lines.append(f"| ABWEICHUNG | {stats.get('ABWEICHUNG', 0)} |")
    lines.append(f"| Nur im aktuellen Anhang | {stats.get('NUR_AKTUELL', 0)} |")
    lines.append(f"| Nur im Vorjahres-Anhang | {stats.get('NUR_VORJAHR', 0)} |")
    lines.append(f"| Wert fehlt auf einer Seite | {stats.get('FEHLENDER_WERT', 0)} |")
    lines.append(f"| **Gesamt** | **{stats.get('GESAMT', 0)}** |")
    lines.append("")

    # Abweichungen zuerst – das Wichtigste
    abw = [r for r in result.rows if r.status == "ABWEICHUNG"]
    if abw:
        lines.append("## ⚠ Abweichungen")
        lines.append("")
        lines.append("| Label (aktuell) | Wert im aktuellen Anhang (Vorjahresspalte) | Wert im Vorjahres-Anhang | Differenz | Seite akt. | Seite vj. |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for r in abw:
            lines.append(
                f"| {r.label_current_doc} | {_fmt(r.value_in_current_anhang)} | "
                f"{_fmt(r.value_in_prior_anhang)} | {_fmt(r.difference)} | "
                f"{r.page_current} | {r.page_prior} |"
            )
        lines.append("")

    fehl = [r for r in result.rows if r.status == "FEHLENDER_WERT"]
    if fehl:
        lines.append("## Fehlende Werte (Label gefunden, Zahl aber nicht in beiden PDFs)")
        lines.append("")
        for r in fehl:
            lines.append(
                f"- **{r.label_current_doc}** — aktuell: {_fmt(r.value_in_current_anhang)}, "
                f"vorjahr: {_fmt(r.value_in_prior_anhang)} (S. {r.page_current}/{r.page_prior})"
            )
        lines.append("")

    nur_a = [r for r in result.rows if r.status == "NUR_AKTUELL"]
    if nur_a:
        lines.append("## Nur im aktuellen Anhang (kein Vorjahres-Match gefunden)")
        lines.append("")
        for r in nur_a[:50]:
            lines.append(f"- {r.label_current_doc}  (S. {r.page_current})")
        if len(nur_a) > 50:
            lines.append(f"- … und {len(nur_a) - 50} weitere")
        lines.append("")

    nur_v = [r for r in result.rows if r.status == "NUR_VORJAHR"]
    if nur_v:
        lines.append("## Nur im Vorjahres-Anhang (im aktuellen Anhang nicht gefunden)")
        lines.append("")
        for r in nur_v[:50]:
            lines.append(f"- {r.label_prior_doc}  (S. {r.page_prior})")
        if len(nur_v) > 50:
            lines.append(f"- … und {len(nur_v) - 50} weitere")
        lines.append("")

    lines.append("## Vollständige Trefferliste (OK)")
    lines.append("")
    ok_rows = [r for r in result.rows if r.status == "OK"]
    if ok_rows:
        lines.append("| Label | Wert | Seite akt. | Seite vj. |")
        lines.append("|---|---:|---:|---:|")
        for r in ok_rows:
            lines.append(
                f"| {r.label_current_doc} | {_fmt(r.value_in_current_anhang)} | "
                f"{r.page_current} | {r.page_prior} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> ⚠ **Hinweis:** Diese Analyse basiert auf einer Heuristik (Regex + Fuzzy-Label-Matching). ")
    lines.append("> Sie ersetzt KEINE prüferische Beurteilung. Treffer und Abweichungen sind manuell zu validieren.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
