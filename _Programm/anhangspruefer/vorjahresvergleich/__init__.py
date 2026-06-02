"""
Vorjahresvergleich (Year-over-Year Comparison)

Ziel 2 des Anhangsprüfers: Prüft, ob die Vorjahreszahlen im aktuellen
Anhang (z.B. 2025) mit den Berichtsjahreszahlen aus dem Vorjahres-Anhang
(z.B. 2024) übereinstimmen.

Komponenten:
- extractor.py  : Extraktion von Label/Zahl-Paaren aus einer Anhang-PDF
- comparator.py : Matching der Label und Vergleich der Werte
- report.py     : Markdown-Bericht über Treffer, Abweichungen, ungematchte Posten

Bewusst getrennt vom Compliance-Checker (Ziel 1) unter `anhangspruefer/review/`.
"""

from .extractor import LabelValuePair, extract_label_value_pairs
from .comparator import CompareResult, ComparisonRow, compare_anhaenge
from .report import generate_report
from .excel_report import generate_excel

__all__ = [
    "LabelValuePair",
    "extract_label_value_pairs",
    "CompareResult",
    "ComparisonRow",
    "compare_anhaenge",
    "generate_report",
    "generate_excel",
]
