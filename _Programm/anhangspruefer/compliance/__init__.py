"""
Compliance-Prüfung (Ziel 1 des Anhangsprüfers)

Prüft einen Anhang zum Jahresabschluss gegen die UGB-Angabepflichten
(§§ 236-243 UGB) anhand einer strukturierten Checkliste.

Submodule:
- engine.py       : Haupt-Engine, orchestriert Parsing → Matching → Bewertung
- evaluator.py    : Compliance-Bewertung pro Checklisten-Punkt
- evidence.py     : Extraktion von Nachweisen aus dem Dokument
- knowledge/      : UGB-Anforderungen, Checklisten, Regel-Katalog
- reporting/      : Generierung der Prüfungsprotokolle (Markdown/HTML)
- rules/          : Regelspezifische Evaluatoren (z.B. Anteilsbesitz § 238 Z 2)
"""

from .engine import ReviewEngine
from .evaluator import ComplianceEvaluator
from .evidence import EvidenceExtractor

__all__ = [
    "ReviewEngine",
    "ComplianceEvaluator",
    "EvidenceExtractor",
]
