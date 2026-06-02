"""
Evaluator for § 237 Abs 1 Z 1 UGB — Durchschnittliche Anzahl der Arbeitnehmer
==============================================================================

§ 237 Abs 1 Z 1 UGB verlangt im Anhang die Angabe der **durchschnittlichen
Anzahl der während des Geschäftsjahres beschäftigten Arbeitnehmer**, getrennt
nach Gruppen (in der Praxis meist: Angestellte / Arbeiter).

Diese Heuristik prüft das Vorhandensein der Pflichtangabe; sie macht **keine
abschließende Beurteilung**, sondern liefert strukturierte Hinweise für den
Prüfer:

  - Wurde überhaupt eine Personalstand-Angabe gefunden?
  - Steht eine Durchschnittszahl (oder zumindest eine Jahreszahl) drin?
  - Ist eine Aufgliederung in Gruppen (Angestellte, Arbeiter, …) erkennbar?
  - Sind Vorjahreszahlen vorhanden?

Ergebnis: ein Finding mit COMPLIANT / PARTIALLY_COMPLIANT / NOT_COMPLIANT /
NOT_ASSESSABLE plus konkrete Hinweise auf fehlende Bestandteile.

Wie der Anteilsbesitz-Evaluator ist dieser Code bewusst konservativ:
Bei Zweifeln → NOT_ASSESSABLE und Prüfer-Aktion erforderlich.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ...models.document import Document, DocumentSection
from ...models.enums import ComplianceStatus
from ...models.finding import EvidenceItem, Finding


# ---------------------------------------------------------------------------
# Regex / Mustererkennung
# ---------------------------------------------------------------------------
SECTION_PATTERNS = [
    r"[Aa]rbeitnehmer",
    r"[Pp]ersonalstand",
    r"[Bb]eschäftigte",
    r"[Mm]itarbeiter(?:innen)?",
    r"§\s*237\s*(?:Abs\s*1\s*)?(?:Z|Ziffer)?\s*1",
]

# "durchschnittlich(e) Anzahl", "im Durchschnitt", "Jahresdurchschnitt", "durchschnittlich N"
AVERAGE_PATTERNS = [
    r"durchschnittliche?(?:n|r)?\s+Anzahl",
    r"im\s+(?:Jahres-?)?[Dd]urchschnitt",
    r"[Jj]ahresdurchschnitt",
    r"Durchschnitt\s+(?:des|der)\s+(?:Berichtsjahre|Geschäftsjahre)",
    r"durchschnittlich\s+\d",
]

# Gruppen-Aufgliederung (Angestellte / Arbeiter / …)
GROUP_PATTERNS = [
    r"[Aa]ngestellte",
    r"[Aa]rbeiter(?:innen)?",
    r"[Ll]ehrlinge",
    r"[Aa]uszubildende",
    r"[Vv]ollzeit",
    r"[Tt]eilzeit",
    r"[Gg]eringfügig",
]

# Zahlen, die im Personal-Kontext stehen
EMPLOYEE_COUNT_PATTERN = re.compile(
    r"(\d{1,4}(?:[.,]\d+)?)\s*(?:Mitarbeiter|Arbeitnehmer|Beschäftigte|Angestellte|Arbeiter|Personen)?",
    re.IGNORECASE,
)

# Vorjahres-Indikatoren
PRIOR_YEAR_PATTERNS = [
    r"\bVorjahr\b",
    r"\b(?:Vergleichs|Vorperioden?)(?:zahlen|werte)?\b",
    r"\b20\d{2}\s*(?:vs\.?|/)\s*20\d{2}\b",
]

# Maximale Fenstergröße um den gefundenen Section-Treffer (Zeichen)
WINDOW_CHARS = 1500


# ---------------------------------------------------------------------------
# Datencontainer
# ---------------------------------------------------------------------------
@dataclass
class ArbeitnehmerAssessment:
    """Strukturiertes Zwischenergebnis der Arbeitnehmer-Prüfung."""
    section_found: bool = False
    section_title: Optional[str] = None
    section_excerpt: Optional[str] = None
    has_average: bool = False
    has_group_breakdown: bool = False
    detected_groups: list[str] = field(default_factory=list)
    detected_counts: list[float] = field(default_factory=list)
    has_prior_year: bool = False

    @property
    def is_complete(self) -> bool:
        """Vollständig nach § 237 Abs 1 Z 1: Durchschnitt + Gruppenaufgliederung."""
        return self.has_average and self.has_group_breakdown


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
class ArbeitnehmerEvaluator:
    """
    Evaluator für die Pflichtangabe nach § 237 Abs 1 Z 1 UGB.

    Vorgehen:
      1. Personalstand-Abschnitt im Anhang lokalisieren (Sektion oder
         Fließtext-Treffer).
      2. Innerhalb des Treffers nach Durchschnittsangabe und
         Gruppenaufgliederung suchen.
      3. Status nach konservativen Kriterien bestimmen.
    """

    UGB_REFERENCE = "§ 237 Abs 1 Z 1 UGB"

    def evaluate(self, document: Document) -> Finding:
        """Hauptmethode: liefert ein Finding für die Checkliste."""
        assessment = self._assess(document)
        status = self._determine_status(assessment)
        evidence = self._build_evidence(assessment)

        finding = Finding(
            checklist_item_id="ugb_237_abs1_z1_arbeitnehmer",
            status=status,
            ugb_references=[self.UGB_REFERENCE],
            evidence=evidence,
            missing_elements=self._missing_elements(assessment),
            technical_reasoning=self._reasoning(assessment, status),
            requires_judgment=True,
            judgment_areas=[
                "Vollständigkeit der Aufgliederung prüfen "
                "(Mindestens: Angestellte, Arbeiter; ggf. Lehrlinge)",
                "Plausibilität der Durchschnittszahlen "
                "(Stichtagswerte vs. echter Jahresdurchschnitt)",
                "Vergleich mit Personalkostenpositionen in der GuV",
            ],
        )
        return finding

    # ------------------------------------------------------------------
    # Interne Schritte
    # ------------------------------------------------------------------
    def _assess(self, document: Document) -> ArbeitnehmerAssessment:
        result = ArbeitnehmerAssessment()

        section_text, section_title = self._find_section(document)
        if section_text is None:
            return result

        result.section_found = True
        result.section_title = section_title
        result.section_excerpt = section_text[:600]

        if any(re.search(p, section_text, re.IGNORECASE) for p in AVERAGE_PATTERNS):
            result.has_average = True

        for pattern in GROUP_PATTERNS:
            m = re.search(pattern, section_text, re.IGNORECASE)
            if m:
                label = m.group(0)
                if label.lower() not in (g.lower() for g in result.detected_groups):
                    result.detected_groups.append(label)

        # Mind. zwei verschiedene Gruppen → echte Aufgliederung
        result.has_group_breakdown = len(result.detected_groups) >= 2

        # Zahlen im Kontext einsammeln (für Evidenz, nicht für Wertung)
        for m in EMPLOYEE_COUNT_PATTERN.finditer(section_text):
            try:
                v = float(m.group(1).replace(".", "").replace(",", "."))
                if 0 < v < 100000:
                    result.detected_counts.append(v)
            except ValueError:
                continue

        if any(re.search(p, section_text, re.IGNORECASE) for p in PRIOR_YEAR_PATTERNS):
            result.has_prior_year = True

        return result

    def _find_section(
        self, document: Document
    ) -> tuple[Optional[str], Optional[str]]:
        """Findet einen Personalstand-Abschnitt; gibt (Text, Titel) zurück."""
        # 1) Strukturierte Sektionen durchsuchen
        for section in document.sections:
            for pattern in SECTION_PATTERNS:
                if re.search(pattern, section.title, re.IGNORECASE):
                    return section.content, section.title
                if re.search(pattern, section.content[:400], re.IGNORECASE):
                    return section.content, section.title

        # 2) Fallback: Rohtext nach Treffer absuchen
        text = document.raw_text
        for pattern in SECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + WINDOW_CHARS)
                return text[start:end], "Personalstand (automatisch extrahiert)"

        return None, None

    def _determine_status(
        self, assessment: ArbeitnehmerAssessment
    ) -> ComplianceStatus:
        if not assessment.section_found:
            return ComplianceStatus.NOT_COMPLIANT
        if assessment.is_complete:
            return ComplianceStatus.COMPLIANT
        if assessment.has_average or assessment.has_group_breakdown:
            return ComplianceStatus.PARTIALLY_COMPLIANT
        # Abschnitt da, aber weder Durchschnitt noch Gruppen klar erkennbar
        return ComplianceStatus.NOT_ASSESSABLE

    def _build_evidence(
        self, assessment: ArbeitnehmerAssessment
    ) -> list[EvidenceItem]:
        if not assessment.section_found or not assessment.section_excerpt:
            return []
        return [
            EvidenceItem(
                section_id="arbeitnehmer",
                section_title=assessment.section_title or "Personalstand",
                quote=assessment.section_excerpt,
                relevance_score=0.9 if assessment.is_complete else 0.5,
                is_supporting=True,
            )
        ]

    def _missing_elements(
        self, assessment: ArbeitnehmerAssessment
    ) -> list[str]:
        missing: list[str] = []
        if not assessment.section_found:
            missing.append("Kein Personalstand-Abschnitt im Anhang gefunden")
            return missing
        if not assessment.has_average:
            missing.append(
                "Durchschnittliche Anzahl Arbeitnehmer nicht eindeutig "
                "ausgewiesen (Stichwort 'durchschnittlich' / 'im Jahresdurchschnitt')"
            )
        if not assessment.has_group_breakdown:
            missing.append(
                "Aufgliederung nach Gruppen (Angestellte/Arbeiter) "
                "nicht oder nur teilweise erkennbar"
            )
        if not assessment.has_prior_year:
            missing.append(
                "Vorjahresvergleichszahl möglicherweise nicht angegeben"
            )
        return missing

    def _reasoning(
        self, assessment: ArbeitnehmerAssessment, status: ComplianceStatus
    ) -> str:
        if not assessment.section_found:
            return (
                "Kein Personalstand-Abschnitt im Anhang automatisch identifiziert. "
                "Pflichtangabe nach § 237 Abs 1 Z 1 UGB scheint zu fehlen — "
                "manuelle Verifikation erforderlich."
            )
        parts = [f"Personalstand-Abschnitt gefunden ('{assessment.section_title}')."]
        if assessment.has_average:
            parts.append("Hinweis auf Durchschnittsangabe vorhanden.")
        else:
            parts.append("Keine eindeutige Durchschnittsangabe erkannt.")
        if assessment.has_group_breakdown:
            parts.append(
                "Gruppenaufgliederung erkannt: "
                + ", ".join(assessment.detected_groups[:4])
                + "."
            )
        else:
            parts.append("Keine ausreichende Gruppenaufgliederung erkannt.")
        if assessment.has_prior_year:
            parts.append("Vorjahresvergleich vermutlich vorhanden.")
        parts.append(
            f"Vorläufige Bewertung: {status.value}. Validierung durch Prüfer erforderlich."
        )
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Modul-Entry-Point (analog zum Anteilsbesitz-Evaluator)
# ---------------------------------------------------------------------------
def evaluate_arbeitnehmer(document: Document) -> Finding:
    """Convenience-Funktion: liefert direkt ein Finding."""
    return ArbeitnehmerEvaluator().evaluate(document)
