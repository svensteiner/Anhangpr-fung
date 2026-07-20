"""
Mandanten-Pipeline: Syngroup Management Consulting AG.

Besonderheit gegenüber der Standard-Pipeline
============================================
1) Der LAUFENDE Anhang liegt als WORD-Dokument (.docx) vor, der Vorjahres-Anhang
   als PDF. Möglich wird das durch den format-agnostischen Konnektor
   (:mod:`anhangspruefer.parsers.document_text`): er linearisiert die Word-
   Absätze und -Tabellen so, dass der Standard-Extraktor sie wie PDF-Inhalte
   liest. Der Word-Anhang braucht daher KEINE eigene Extraktionslogik.

2) Vorjahresvergleich (Modus 1) – Feinschliff der vergleichbaren Posten:
   * Die Latente-Steuern-Tabelle ist eine GEGENÜBERSTELLUNG
       Aktiv/Passiv 31.12.2025 | Aktiv/Passiv 31.12.2024 | Bewegung
     und KEIN Bilanzkontinuitäts-Spiegel (Eröffnung = Schluss Vorjahr). Der
     Standard-Extraktor läse sonst die Bewegungsspalte als "Schlusswert" und
     meldete Scheinabweichungen. Diese Zeilen werden daher aus dem Zahlen-
     Kontinuitätsvergleich genommen; die latenten Steuern prüft der Prüfer
     anhand der Steuerüberleitung separat.
   * Kopf-/Fußzeilen und ähnliche Dokument-Möblierung des PDF-Vorjahresberichts
     (Adresse, Seitenzahlen, Nutzungsdauer-Jahre, Unterschriftszeile) sind keine
     vergleichbaren Bilanzposten und werden ausgefiltert.
"""

from __future__ import annotations

import re

from ..vorjahresvergleich.extractor import AnhangItem
from .base import Pipeline

# Latente-Steuern-Matrix: exakte (leerzeichenfreie) Label-Schlüssel der Zeilen,
# die als Steuerlatenz-Gegenüberstellung – nicht als Kontinuitätsposten – gelten.
#   "rueckstellungfuerabfertigung"  = Singular (Steuerlatenz-Zeile);
#     der ECHTE Spiegel heißt "Rückstellungen für Abfertigungen" (Plural) und
#     bleibt erhalten.
_LATENTE_LABEL_KEYS = {
    "rueckstellungfuerabfertigung",
    "aktivposten",
}

# Dokument-Möblierung / Extraktions-Artefakte aus dem PDF-Vorjahresbericht:
# Adresse, Seitenzahl/Aktenzeichen, Nutzungsdauer-Jahre, Unterschriftszeile.
_NOISE_RE = re.compile(
    r"nutzungsdauer|k[äa]rntner\s+ring|unterschriften|\bseite\b|"
    r"vorjahr:\s*eur|\b119149\b",
    re.I,
)

# Nutzungsdauer-Zeile, deren Label mit einer Jahres-Range endet ("… 9,50 -"):
# das sind Abschreibungs-Nutzungsdauern in JAHREN, keine Bilanzposten.
_NUTZUNGSDAUER_TAIL_RE = re.compile(r"\d+,\d+\s*-\s*$")


def _leads_with_year(it: AnhangItem) -> bool:
    """True, wenn der ERSTE Wert eine nackte Jahreszahl ist und ein echter
    Betrag folgt – typisches Extraktions-Artefakt aus Aufgliederungen wie
    'RST JAB 2024 10.000,00' oder 'Telefongebühren 12/2024 1.485,20'
    (die '2024' wird fälschlich als Wert gelesen).

    Der Betrag kann in einer zweiten current-Spalte ODER – wenn die Zwei-
    Spalten-Logik zugeschlagen hat – in prior_values gelandet sein; beide
    Fälle werden erkannt.
    """
    vals = it.current_values
    if not vals:
        return False
    first = vals[0]
    if not (float(first).is_integer() and 2015 <= first <= 2035):
        return False
    return len(vals) >= 2 or len(it.prior_values) >= 1


def _is_continuity_item(it: AnhangItem) -> bool:
    """True, wenn der Posten in den Vorjahresvergleich (Bilanzkontinuität) gehört."""
    key = it.label_key_compact
    if key in _LATENTE_LABEL_KEYS:
        return False
    if key == "rueckstellungen":               # umgebrochene "SUMME RÜCKSTELLUNGEN"
        return False
    if key.startswith("rst"):                  # "RST JAB"/"RST WP"-Aufgliederung
        return False
    if "latente" in it.label.lower():          # "… latente Steuerabgrenzung"
        return False
    if _NUTZUNGSDAUER_TAIL_RE.search(it.label):
        return False
    if _leads_with_year(it):
        return False
    if _NOISE_RE.search(it.label):
        return False
    return True


class SyngroupPipeline(Pipeline):
    """Dokumenten-Pipeline für Syngroup Management Consulting AG."""

    name = "syngroup"

    # ---- Modus 1: Vorjahresvergleich ----
    def extract_anhang_items(self, pdf_path):
        items = super().extract_anhang_items(pdf_path)
        return [it for it in items if _is_continuity_item(it)]
