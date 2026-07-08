"""
Vergleicht Anhang-Positionen mit extrahierten Belegwerten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .extractor import (
    AnhangPosition,
    ExtractedFact,
    detect_type,
    extract_from_anhang,
    extract_from_bank_guarantees,
    extract_from_hr_excel,
)


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------
SECTION_TO_TYPE: dict[str, str] = {
    "Haftungsverhaeltnisse": "bank_guarantees",
    "Arbeitnehmer": "hr_employees",
}

STATUS_OK       = "OK"
STATUS_ABWEICHUNG = "ABWEICHUNG"
STATUS_KEIN_BELEG = "KEIN_BELEG"     # kein passender Beleg hochgeladen
STATUS_KEIN_WERT  = "KEIN_WERT"      # Beleg vorhanden, aber kein extrahierbarer Wert
STATUS_HINWEIS    = "HINWEIS"        # passt, aber methodischer Hinweis


@dataclass
class PruefRow:
    """Eine Prüfzeile im Ergebnis-Report."""
    section: str
    label: str                          # Bezeichnung laut Anhang
    anhang_value: Optional[float]       # Wert im Anhang
    beleg_value: Optional[float]        # Summe aus Belegen
    difference: Optional[float]         # anhang_value - beleg_value
    status: str
    page_anhang: int
    belege: list[ExtractedFact] = field(default_factory=list)
    note: str = ""


@dataclass
class PruefResult:
    rows: list[PruefRow]
    anhang_filename: str
    beleg_filenames: list[str]

    @property
    def count_ok(self) -> int:
        return sum(1 for r in self.rows if r.status in (STATUS_OK, STATUS_HINWEIS))

    @property
    def count_abweichung(self) -> int:
        return sum(1 for r in self.rows if r.status == STATUS_ABWEICHUNG)

    @property
    def count_kein_beleg(self) -> int:
        return sum(1 for r in self.rows if r.status == STATUS_KEIN_BELEG)


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def pruefen(anhang_path: Path, beleg_paths: list[Path], pipeline=None) -> PruefResult:
    """
    Prüft den Anhang gegen alle übergebenen Belegdateien.

    Args:
        anhang_path:  Pfad zum Anhang-PDF
        beleg_paths:  Liste der Detailunterlagen (PDF / XLSX)
        pipeline:     Dokumenten-Pipeline (mandantenspezifisch). None -> Standard.

    Returns:
        PruefResult mit allen Prüfzeilen
    """
    from ..pipelines import Pipeline
    pipeline = pipeline or Pipeline()

    anhang_path = Path(anhang_path)
    beleg_paths = [Path(p) for p in beleg_paths]

    # 1) Anhang-Positionen extrahieren (Pipeline liefert das mandantenspezifische Set)
    positions = pipeline.extract_anhang_positions(anhang_path)

    # 2) Belegdateien erkennen und extrahieren – beides über die Pipeline
    all_facts: list[ExtractedFact] = []
    detected_types: dict[str, str] = {}

    for bpath in beleg_paths:
        dtype = pipeline.detect_beleg_type(bpath)
        detected_types[bpath.name] = dtype
        all_facts.extend(pipeline.extract_beleg_facts(bpath, dtype))

    # 3) Positionen mit Belegen abgleichen
    rows: list[PruefRow] = []

    for pos in positions:
        fact_type = pipeline.section_to_type.get(pos.section)
        matching = [f for f in all_facts if f.source_type == fact_type]

        if not matching:
            rows.append(PruefRow(
                section=pos.section,
                label=pos.label,
                anhang_value=pos.current_value,
                beleg_value=None,
                difference=None,
                status=STATUS_KEIN_BELEG,
                page_anhang=pos.page,
                note=pos.note,
            ))
            continue

        beleg_total = sum(f.value for f in matching)

        if pos.current_value is None:
            status = STATUS_KEIN_WERT
            diff = None
        else:
            diff = pos.current_value - beleg_total
            if abs(diff) <= pipeline.match_tolerance(pos.current_value):
                status = STATUS_HINWEIS if pos.note else STATUS_OK
            else:
                status = STATUS_ABWEICHUNG

        rows.append(PruefRow(
            section=pos.section,
            label=pos.label,
            anhang_value=pos.current_value,
            beleg_value=beleg_total,
            difference=diff,
            status=status,
            page_anhang=pos.page,
            belege=matching,
            note=pos.note,
        ))

    return PruefResult(
        rows=rows,
        anhang_filename=anhang_path.name,
        beleg_filenames=[p.name for p in beleg_paths],
    )
