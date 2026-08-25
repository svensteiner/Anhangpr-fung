"""
Excel-Export des Vorjahresvergleichs.

Erzeugt eine .xlsx-Datei mit drei Tabellenblättern:
  1. Übersicht       — Zusammenfassung + Statistik
  2. Alle Posten     — Vollständige Vergleichsliste mit Status, Werten, Differenzen
  3. Abweichungen    — Nur Zeilen mit Status ABWEICHUNG (für schnelle Prüfung)

Nutzt openpyxl. Die Statuszellen werden farblich hinterlegt:
  OK             → grün
  ABWEICHUNG     → rot
  NUR_AKTUELL    → orange
  NUR_VORJAHR    → orange
  FEHLENDER_WERT → grau
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from .comparator import CompareResult
from .text_compare import diff_excerpt


STATUS_FILLS = {
    "OK":             PatternFill("solid", fgColor="C6EFCE"),
    "ABWEICHUNG":     PatternFill("solid", fgColor="FFC7CE"),
    "NUR_AKTUELL":    PatternFill("solid", fgColor="FFEB9C"),
    "NUR_VORJAHR":    PatternFill("solid", fgColor="FFEB9C"),
    "FEHLENDER_WERT": PatternFill("solid", fgColor="D9D9D9"),
}

HEADER_FILL = PatternFill("solid", fgColor="305496")
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _set_header(ws, row, headers, widths):
    for col, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = HEADER_ALIGN
        c.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.row_dimensions[row].height = 32
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _write_uebersicht(wb: Workbook, result: CompareResult) -> None:
    ws = wb.active
    ws.title = "Übersicht"

    title = ws.cell(row=1, column=1, value="Vorjahresvergleich – Anhang")
    title.font = Font(bold=True, size=14)
    ws.merge_cells("A1:D1")

    ws.cell(row=3, column=1, value="Aktueller Anhang:").font = Font(bold=True)
    ws.cell(row=3, column=2, value=result.current_pdf.name)
    ws.cell(row=4, column=1, value="Vorjahres-Anhang:").font = Font(bold=True)
    ws.cell(row=4, column=2, value=result.prior_pdf.name)
    ws.merge_cells("B3:D3")
    ws.merge_cells("B4:D4")

    ws.cell(row=6, column=1, value="Status").font = Font(bold=True)
    ws.cell(row=6, column=2, value="Anzahl").font = Font(bold=True)

    stats = result.stats
    rows = [
        ("OK (Zahlen stimmen)",        stats.get("OK", 0)),
        ("ABWEICHUNG",                 stats.get("ABWEICHUNG", 0)),
        ("Nur im aktuellen Anhang",    stats.get("NUR_AKTUELL", 0)),
        ("Nur im Vorjahres-Anhang",    stats.get("NUR_VORJAHR", 0)),
        ("Wert fehlt auf einer Seite", stats.get("FEHLENDER_WERT", 0)),
        ("Gesamt",                      stats.get("GESAMT", 0)),
    ]
    status_keys = ["OK", "ABWEICHUNG", "NUR_AKTUELL", "NUR_VORJAHR", "FEHLENDER_WERT", None]
    for i, ((label, count), key) in enumerate(zip(rows, status_keys), start=7):
        c1 = ws.cell(row=i, column=1, value=label)
        c2 = ws.cell(row=i, column=2, value=count)
        if key in STATUS_FILLS:
            c1.fill = STATUS_FILLS[key]
            c2.fill = STATUS_FILLS[key]
        if label == "Gesamt":
            c1.font = Font(bold=True)
            c2.font = Font(bold=True)

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 14

    # Eigener Bereich: Textvergleich (Vollständigkeit)
    fehlt = sum(1 for t in result.text_rows if t.status == "FEHLT")
    neu = sum(1 for t in result.text_rows if t.status == "NEU")
    geaendert = sum(1 for t in result.text_rows if t.status == "GEÄNDERT")
    ws.cell(row=14, column=1, value="Textvergleich (Vollständigkeit)").font = Font(bold=True)
    tc = ws.cell(row=14, column=2,
                 value=f"FEHLT: {fehlt} · NEU: {neu} · GEÄNDERT: {geaendert}")
    tc.font = Font(bold=True)
    if fehlt:
        tc.fill = STATUS_FILLS["ABWEICHUNG"]
    ws.cell(row=14, column=3,
            value="→ Blatt 'Textvergleich'").font = Font(italic=True, color="7F7F7F")

    ws.cell(row=16, column=1,
            value=("Hinweis: Heuristische Analyse (Regex + Fuzzy-Label-Matching, "
                   "Textvergleich ohne Zahlen). Ersetzt KEINE prüferische Beurteilung. "
                   "Manuelle Validierung erforderlich.")
            ).font = Font(italic=True, color="7F7F7F")
    ws.merge_cells("A16:D16")


def _write_rows(ws, rows, headers, widths):
    _set_header(ws, 1, headers, widths)
    last_label = None
    for r_idx, row in enumerate(rows, start=2):
        # Label nur einmal je Item-Block anzeigen (mehrspaltige Tabellen kompakter)
        label_text = row.label_current_doc or row.label_prior_doc or ""
        display_label = label_text if label_text != last_label else ""
        last_label = label_text

        ws.cell(row=r_idx, column=1, value=display_label)
        ws.cell(row=r_idx, column=2, value=getattr(row, "column_index", 1))
        c3 = ws.cell(row=r_idx, column=3, value=row.value_in_current_anhang)
        c4 = ws.cell(row=r_idx, column=4, value=row.value_in_prior_anhang)
        c5 = ws.cell(row=r_idx, column=5, value=row.difference)
        ws.cell(row=r_idx, column=6, value=row.page_current or None)
        ws.cell(row=r_idx, column=7, value=row.page_prior or None)
        c8 = ws.cell(row=r_idx, column=8, value=row.status)
        ws.cell(row=r_idx, column=9, value=round(row.match_score, 2))

        fmt = '#,##0.00'
        c3.number_format = fmt
        c4.number_format = fmt
        c5.number_format = fmt

        fill = STATUS_FILLS.get(row.status)
        if fill:
            for col in range(1, 10):
                ws.cell(row=r_idx, column=col).fill = fill

        c8.alignment = Alignment(horizontal="center")


_HEADERS = [
    "Bezeichnung",
    "Spalte",
    "Wert lt. aktuellem Anhang (Vorjahresspalte)",
    "Wert lt. Vorjahres-Anhang (Berichtsjahr)",
    "Differenz",
    "Seite aktuell",
    "Seite Vorjahr",
    "Status",
    "Match-Score",
]
_WIDTHS = [55, 8, 30, 30, 16, 10, 10, 16, 12]


def _write_alle(wb: Workbook, result: CompareResult) -> None:
    ws = wb.create_sheet("Alle Posten")
    _write_rows(ws, result.rows, _HEADERS, _WIDTHS)


_TEXT_HEADERS = ["Textteil aktuell", "Textteil Vorjahr", "Status", "S. akt.", "S. VJ", "Unterschied (Auszug)"]
_TEXT_WIDTHS = [70, 70, 12, 8, 8, 60]
NEW_TEXT_FILL = PatternFill("solid", fgColor="FFEB9C")

_TEXT_STATUS_FILL = {
    "IDENT":    PatternFill("solid", fgColor="FFFFFF"),
    "GEÄNDERT": PatternFill("solid", fgColor="FFEB9C"),
    "NEU":      PatternFill("solid", fgColor="DDEBF7"),
    "FEHLT":    PatternFill("solid", fgColor="FFC7CE"),  # Vollständigkeitslücke!
}


def _write_textvergleich(wb: Workbook, result: CompareResult) -> None:
    """Gegenüberstellung der Textteile aktuell ↔ Vorjahr (Vollständigkeit)."""
    ws = wb.create_sheet("Textvergleich")
    _set_header(ws, 1, _TEXT_HEADERS, _TEXT_WIDTHS)

    trows = result.text_rows
    if not trows:
        c = ws.cell(row=2, column=1, value="Kein vergleichbarer Text gefunden.")
        c.font = Font(italic=True, color="7F7F7F")
        ws.merge_cells("A2:F2")
        return

    top = Alignment(wrap_text=True, vertical="top")
    ctr = Alignment(horizontal="center", vertical="top")
    for r_idx, tr in enumerate(trows, start=2):
        c1 = ws.cell(row=r_idx, column=1, value=tr.current); c1.alignment = top
        c2 = ws.cell(row=r_idx, column=2, value=tr.prior);   c2.alignment = top
        c3 = ws.cell(row=r_idx, column=3, value=tr.status);  c3.alignment = ctr
        ws.cell(row=r_idx, column=4, value=tr.page_current).alignment = ctr
        ws.cell(row=r_idx, column=5, value=tr.page_prior).alignment = ctr
        c6 = ws.cell(row=r_idx, column=6, value=diff_excerpt(tr.current, tr.prior))
        c6.alignment = top
        fill = _TEXT_STATUS_FILL.get(tr.status)
        if fill:
            for col in range(1, 7):
                ws.cell(row=r_idx, column=col).fill = fill


def _write_abweichungen(wb: Workbook, result: CompareResult) -> None:
    ws = wb.create_sheet("Abweichungen")
    rows = [r for r in result.rows if r.status == "ABWEICHUNG"]
    _write_rows(ws, rows, _HEADERS, _WIDTHS)



_CHG_HEADERS = ["Status", "S. akt.", "S. VJ", "Entfernt / nur Vorjahr", "Hinzugefügt / nur aktuell", "Text aktuell", "Text Vorjahr"]
_CHG_WIDTHS = [12, 8, 8, 45, 45, 50, 50]


def _write_textaenderungen(wb: Workbook, result: CompareResult) -> None:
    """Nur geaenderte/neue/fehlende Textteile — Wortunterschiede aufgeschluesselt."""
    ws = wb.create_sheet("Textänderungen")
    _set_header(ws, 1, _CHG_HEADERS, _CHG_WIDTHS)
    rows = [t for t in result.text_rows if t.status != "IDENT"]
    if not rows:
        c = ws.cell(row=2, column=1, value="Keine Textänderungen gegenüber dem Vorjahr.")
        c.font = Font(italic=True, color="7F7F7F")
        ws.merge_cells("A2:G2")
        return
    top = Alignment(wrap_text=True, vertical="top")
    ctr = Alignment(horizontal="center", vertical="top")
    for r_idx, tr in enumerate(rows, start=2):
        excerpt = diff_excerpt(tr.current, tr.prior, max_len=800)
        removed = added = ""
        if "Vorjahr:" in excerpt or "aktuell:" in excerpt:
            for p in excerpt.split(" || "):
                if p.startswith("Vorjahr:"):
                    removed = p[len("Vorjahr:"):].strip()
                elif p.startswith("aktuell:"):
                    added = p[len("aktuell:"):].strip()
        elif excerpt.startswith("nur"):
            if "Vorjahr" in excerpt:
                removed = excerpt
            else:
                added = excerpt
        else:
            added = excerpt
        ws.cell(row=r_idx, column=1, value=tr.status).alignment = ctr
        ws.cell(row=r_idx, column=2, value=tr.page_current).alignment = ctr
        ws.cell(row=r_idx, column=3, value=tr.page_prior).alignment = ctr
        ws.cell(row=r_idx, column=4, value=removed).alignment = top
        ws.cell(row=r_idx, column=5, value=added).alignment = top
        ws.cell(row=r_idx, column=6, value=tr.current).alignment = top
        ws.cell(row=r_idx, column=7, value=tr.prior).alignment = top
        fill = _TEXT_STATUS_FILL.get(tr.status)
        if fill:
            for col in range(1, 8):
                ws.cell(row=r_idx, column=col).fill = fill


def generate_excel(result: CompareResult, output_path: Path) -> Path:
    """Schreibt einen Excel-Bericht für das Vergleichsergebnis."""
    wb = Workbook()
    _write_uebersicht(wb, result)
    _write_alle(wb, result)
    _write_abweichungen(wb, result)
    _write_textvergleich(wb, result)
    _write_textaenderungen(wb, result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
