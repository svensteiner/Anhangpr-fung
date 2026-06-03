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

    # Eigener Bereich: Textvergleich
    tcount = len(result.new_text_blocks)
    ws.cell(row=14, column=1, value="Neue Textteile (eigener Bereich)").font = Font(bold=True)
    tc = ws.cell(row=14, column=2, value=tcount)
    tc.font = Font(bold=True)
    tc.fill = NEW_TEXT_FILL
    ws.cell(row=14, column=3,
            value="→ Blatt 'Neue Textteile'").font = Font(italic=True, color="7F7F7F")

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
    "Wert lt. 2025er Anhang (Vorjahresspalte = 2024)",
    "Wert lt. 2024er Anhang (Berichtsjahr = 2024)",
    "Differenz",
    "Seite 2025",
    "Seite 2024",
    "Status",
    "Match-Score",
]
_WIDTHS = [55, 8, 30, 30, 16, 10, 10, 16, 12]


def _write_alle(wb: Workbook, result: CompareResult) -> None:
    ws = wb.create_sheet("Alle Posten")
    _write_rows(ws, result.rows, _HEADERS, _WIDTHS)


_TEXT_HEADERS = ["Neuer Textteil (im aktuellen Anhang)", "Seite", "Ähnlichkeit Vorjahr"]
_TEXT_WIDTHS = [110, 8, 18]
NEW_TEXT_FILL = PatternFill("solid", fgColor="FFEB9C")


def _write_neue_textteile(wb: Workbook, result: CompareResult) -> None:
    """Eigener Bereich: Textteile, die im aktuellen Anhang neu hinzugekommen sind."""
    ws = wb.create_sheet("Neue Textteile")
    _set_header(ws, 1, _TEXT_HEADERS, _TEXT_WIDTHS)

    blocks = result.new_text_blocks
    if not blocks:
        c = ws.cell(row=2, column=1,
                    value="Keine neuen Textteile gegenüber dem Vorjahres-Anhang gefunden.")
        c.font = Font(italic=True, color="7F7F7F")
        ws.merge_cells("A2:C2")
        return

    for r_idx, blk in enumerate(blocks, start=2):
        c1 = ws.cell(row=r_idx, column=1, value=blk.text)
        c1.alignment = Alignment(wrap_text=True, vertical="top")
        c1.fill = NEW_TEXT_FILL
        c2 = ws.cell(row=r_idx, column=2, value=blk.page)
        c2.alignment = Alignment(horizontal="center", vertical="top")
        c3 = ws.cell(row=r_idx, column=3, value=blk.best_score)
        c3.alignment = Alignment(horizontal="center", vertical="top")
        c3.number_format = "0.00"


def _write_abweichungen(wb: Workbook, result: CompareResult) -> None:
    ws = wb.create_sheet("Abweichungen")
    rows = [r for r in result.rows if r.status == "ABWEICHUNG"]
    _write_rows(ws, rows, _HEADERS, _WIDTHS)


def generate_excel(result: CompareResult, output_path: Path) -> Path:
    """Schreibt einen Excel-Bericht für das Vergleichsergebnis."""
    wb = Workbook()
    _write_uebersicht(wb, result)
    _write_alle(wb, result)
    _write_abweichungen(wb, result)
    _write_neue_textteile(wb, result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
