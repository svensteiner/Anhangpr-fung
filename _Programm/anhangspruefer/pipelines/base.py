"""
Dokumenten-Pipeline – die austauschbare Schicht zwischen den Roh-Unterlagen
eines Mandanten und dem gemeinsamen "Hirn" (Vergleichs-/Prüflogik).

Leitidee (siehe STRUKTUR.md):
    Das Hirn bleibt EINE zentrale Kopie und kennt nur die kanonischen
    Datenobjekte (AnhangItem, AnhangPosition, ExtractedFact). WIE diese
    Objekte aus den konkreten Dateien eines Mandanten gewonnen werden,
    steckt ausschließlich hier in der Pipeline.

Die Standard-Pipeline (`Pipeline`) delegiert 1:1 an die bisherigen
Extraktoren – also KEIN Verhaltensunterschied zu vorher. Mandantenspezifische
Pipelines erben davon und überschreiben/ergänzen nur einzelne Schritte.
"""

from __future__ import annotations

from pathlib import Path

from ..vorjahresvergleich.extractor import AnhangItem, extract_items as _std_extract_items
from ..pruefung.extractor import (
    AnhangPosition,
    ExtractedFact,
    detect_type as _std_detect_type,
    extract_from_anhang as _std_extract_from_anhang,
    extract_from_bank_guarantees as _std_extract_bank,
    extract_from_hr_excel as _std_extract_hr,
)


class Pipeline:
    """Standard-Dokumentenpipeline. Verhalten exakt wie bisher."""

    #: Kurzname – erscheint im Ergebnis, damit der Prüfer sieht, welches
    #: Mandantenprofil gelaufen ist.
    name = "standard"

    # ------------------------------------------------------------------
    # Modus 1 – Vorjahresvergleich
    # ------------------------------------------------------------------
    def extract_anhang_items(self, pdf_path: Path) -> list[AnhangItem]:
        """Liest die vergleichbaren Anhang-Posten (Label + Werte) aus einem PDF."""
        return _std_extract_items(pdf_path)

    # ------------------------------------------------------------------
    # Modus 2 – Belegprüfung (Detailzahlenvergleich)
    # ------------------------------------------------------------------
    #: Zuordnung Anhang-Abschnitt -> Belegtyp, nach dem im Abgleich gesucht wird.
    section_to_type: dict[str, str] = {
        "Haftungsverhaeltnisse": "bank_guarantees",
        "Arbeitnehmer": "hr_employees",
    }

    def extract_anhang_positions(self, pdf_path: Path) -> list[AnhangPosition]:
        """Liest die prüfbaren Positionen aus dem Anhang (Haftungen, Arbeitnehmer …)."""
        return _std_extract_from_anhang(pdf_path)

    def detect_beleg_type(self, path: Path) -> str:
        """Erkennt den Typ einer hochgeladenen Detailunterlage."""
        return _std_detect_type(path)

    def extract_beleg_facts(self, path: Path, dtype: str) -> list[ExtractedFact]:
        """Extrahiert die belegten Werte aus einer Detailunterlage des erkannten Typs."""
        if dtype == "bank_guarantees":
            return _std_extract_bank(path)
        if dtype == "hr_employees":
            return _std_extract_hr(path)
        return []  # unbekannt -> kein Beleg-Fakt

    def match_tolerance(self, anhang_value) -> float:
        """Erlaubte Differenz (EUR), bis zu der Anhang- und Belegwert als OK
        gelten. Standard: 2 Cent (Rundung). Mandanten mit gröberer Darstellung
        (z.B. ganze Euro) können dies überschreiben."""
        return 0.02
