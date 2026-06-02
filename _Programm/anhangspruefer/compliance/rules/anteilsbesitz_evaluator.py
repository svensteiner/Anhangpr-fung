"""
Evaluator for § 238 Abs 1 Z 2 UGB (Anteilsbesitz)

This evaluator applies the formalized rule to actual document content.
It produces structured findings, NOT final judgments.

Integration point: Called by ReviewEngine for this specific checklist item.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ...models.document import Document, DocumentSection
from ..knowledge.rules.anteilsbesitz_238_z2 import (
    RULE_ID,
    REQUIRED_ELEMENTS,
    RuleEvaluationResult,
    ParticipationAssessment,
    ElementAssessment,
    DisclosureStatus,
    determine_compliance_status,
    RULE_SCHEMA,
)


@dataclass
class ExtractedParticipation:
    """Raw extraction from document before assessment."""
    raw_text: str
    entity_name_candidate: Optional[str] = None
    percentage_candidate: Optional[str] = None
    equity_candidate: Optional[str] = None
    result_candidate: Optional[str] = None
    location: Optional[str] = None


class AnteilsbesitzEvaluator:
    """
    Evaluator for the Anteilsbesitz disclosure requirement.

    This class:
    1. Locates the Anteilsbesitz section in the document
    2. Attempts to extract participation entries
    3. Assesses each entry against required elements
    4. Produces a structured result with explicit uncertainties

    This class does NOT:
    - Make final compliance determinations
    - Judge materiality
    - Assume completeness
    - Use probabilistic scoring
    """

    # Section identification patterns
    SECTION_PATTERNS = [
        r"[Aa]nteilsbesitz",
        r"[Bb]eteiligung(?:en)?(?:\s+an\s+anderen\s+Unternehmen)?",
        r"[Aa]ngaben\s+(?:zu|über)\s+(?:verbundene|Beteiligung)",
        r"§\s*238\s*(?:Abs\s*1\s*)?(?:Z|Ziffer)?\s*2",
    ]

    # Patterns for table headers (strong indicator of structured disclosure)
    TABLE_HEADER_PATTERNS = [
        r"Name.*Sitz.*Anteil.*(?:Eigenkapital|EK).*(?:Ergebnis|Jahres)",
        r"Firma.*%.*EUR",
        r"Gesellschaft.*Beteiligung.*Kapital",
    ]

    # Entity name patterns (Austrian/German company forms)
    ENTITY_PATTERNS = [
        r"([A-ZÄÖÜ][A-Za-zäöüßÄÖÜ\s\-&\.]+(?:GmbH|AG|KG|OG|e\.U\.|SE|Ges\.?m\.?b\.?H\.?))",
        r"([A-ZÄÖÜ][A-Za-zäöüßÄÖÜ\s\-&\.]{3,50})\s+(?:mit\s+Sitz|,\s*[A-Z][a-z]+)",
    ]

    # Percentage patterns
    PERCENTAGE_PATTERNS = [
        r"(\d{1,3}(?:[.,]\d+)?)\s*%",
        r"(\d{1,3}(?:[.,]\d+)?)\s*(?:Prozent|v\.H\.)",
        r"(?:Anteil|Beteiligung)(?:\s+von)?\s*(\d{1,3}(?:[.,]\d+)?)",
    ]

    # Amount patterns (EUR, TEUR)
    AMOUNT_PATTERNS = [
        r"(?:EUR|€)\s*([\d\.,]+)",
        r"([\d\.,]+)\s*(?:EUR|€|TEUR)",
        r"(?:Eigenkapital|EK)[\s:]*(?:EUR|€)?\s*([\d\.,\-]+)",
        r"(?:Ergebnis|Jahresüberschuss|Jahresfehlbetrag)[\s:]*(?:EUR|€)?\s*([\d\.,\-]+)",
    ]

    # Protective clause patterns
    PROTECTIVE_CLAUSE_PATTERNS = [
        r"§\s*241\s*(?:Abs\.?\s*2)?",
        r"[Ss]chutzklausel",
        r"erhebliche[rn]?\s+[Nn]achteil",
        r"Angaben?\s+unterbleib",
    ]

    def __init__(self):
        self.rule_id = RULE_ID
        self.rule_schema = RULE_SCHEMA

    def evaluate(self, document: Document) -> RuleEvaluationResult:
        """
        Evaluate the document against § 238 Abs 1 Z 2 UGB.

        Returns a structured result with:
        - What was found
        - What appears to be missing
        - What cannot be determined
        - What the auditor must verify
        """
        result = RuleEvaluationResult(rule_id=self.rule_id)

        # Step 1: Find the relevant section
        section = self._find_anteilsbesitz_section(document)

        if section is None:
            result.compliance_status = "NOT_ASSESSABLE"
            result.compliance_reasoning = (
                "Kein Abschnitt 'Anteilsbesitz' oder 'Beteiligungen' automatisch identifiziert."
            )
            result.auditor_actions_required = [
                "Prüfen ob Anteilsbesitz-Angaben im Anhang vorhanden sind",
                "Falls vorhanden: manuelle Analyse der Vollständigkeit",
                "Falls nicht vorhanden: prüfen ob Befreiungstatbestand (§ 242 UGB)",
            ]
            result.uncertainties = [
                "Abschnittsidentifikation nicht erfolgreich",
            ]
            return result

        # Step 2: Check for Finanzanlagen reference (balance sheet)
        result.finanzanlagen_mentioned = self._check_finanzanlagen_reference(document)

        # Step 3: Check for protective clause
        protective_clause_found = self._check_protective_clause(section)

        # Step 4: Detect table structure
        has_table_structure = self._detect_table_structure(section)

        # Step 5: Extract participation entries
        extractions = self._extract_participations(section)

        if not extractions:
            result.compliance_status = "NOT_ASSESSABLE"
            result.compliance_reasoning = (
                f"Abschnitt gefunden ('{section.title[:50]}...'), aber keine "
                "Beteiligungseinträge automatisch extrahierbar."
            )
            if has_table_structure:
                result.compliance_reasoning += " Tabellenstruktur erkannt, aber nicht parsebar."
            result.auditor_actions_required = [
                "Manuelle Analyse des Anteilsbesitz-Abschnitts",
                "Prüfung der vier Pflichtangaben je Beteiligung",
            ]
            return result

        # Step 6: Assess each extracted participation
        for extraction in extractions:
            assessment = self._assess_participation(extraction, protective_clause_found)
            result.participations_found.append(assessment)

        result.total_participations_detected = len(result.participations_found)

        # Step 7: Check for count mismatch (if possible)
        if result.finanzanlagen_mentioned:
            result.apparent_count_mismatch = False  # Cannot reliably determine
            result.count_mismatch_note = (
                "Finanzanlagen in Dokument erwähnt. Abgleich mit Bilanz erforderlich."
            )
            result.auditor_actions_required.append(
                "Anzahl Beteiligungen gegen Bilanz-Position Finanzanlagen abgleichen"
            )

        # Step 8: Determine overall status
        status, reasoning, actions = determine_compliance_status(
            result.participations_found,
            result.finanzanlagen_mentioned,
        )

        result.compliance_status = status
        result.compliance_reasoning = reasoning
        result.auditor_actions_required.extend(actions)

        # Step 9: Add standard uncertainties
        result.uncertainties = [
            "Vollständigkeit der Beteiligungsliste nicht prüfbar",
            "Richtigkeit der Zahlen nicht verifiziert",
            "Aktualität der Jahresabschlüsse nicht prüfbar",
        ]

        if protective_clause_found:
            result.uncertainties.append(
                "Angemessenheit der Schutzklausel-Anwendung nicht beurteilbar"
            )

        return result

    def _find_anteilsbesitz_section(
        self, document: Document
    ) -> Optional[DocumentSection]:
        """Locate the Anteilsbesitz section in the document."""
        # First try: exact section match
        for section in document.sections:
            for pattern in self.SECTION_PATTERNS:
                if re.search(pattern, section.title, re.IGNORECASE):
                    return section
                if re.search(pattern, section.content[:500], re.IGNORECASE):
                    return section

        # Second try: search in raw text for section
        text = document.raw_text
        for pattern in self.SECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract surrounding context as pseudo-section
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 2000)
                return DocumentSection(
                    section_id="extracted_anteilsbesitz",
                    title="Anteilsbesitz (automatisch extrahiert)",
                    content=text[start:end],
                    section_type=None,
                )

        return None

    def _check_finanzanlagen_reference(self, document: Document) -> bool:
        """Check if Finanzanlagen are mentioned in the document."""
        patterns = [
            r"[Ff]inanzanlagen",
            r"[Bb]eteiligung(?:en)?\s+(?:an\s+)?(?:verbundenen?\s+)?[Uu]nternehmen",
            r"[Aa]nteile?\s+an\s+verbundenen\s+Unternehmen",
        ]
        for pattern in patterns:
            if re.search(pattern, document.raw_text):
                return True
        return False

    def _check_protective_clause(self, section: DocumentSection) -> bool:
        """Check if protective clause (§ 241 Abs 2) is referenced."""
        for pattern in self.PROTECTIVE_CLAUSE_PATTERNS:
            if re.search(pattern, section.content, re.IGNORECASE):
                return True
        return False

    def _detect_table_structure(self, section: DocumentSection) -> bool:
        """Detect if section contains a structured table."""
        for pattern in self.TABLE_HEADER_PATTERNS:
            if re.search(pattern, section.content, re.IGNORECASE):
                return True
        # Also check for multiple rows with similar structure
        lines = section.content.split("\n")
        numeric_lines = sum(
            1 for line in lines
            if re.search(r"\d+[.,]\d+\s*%", line) or re.search(r"EUR\s*[\d.,]+", line)
        )
        return numeric_lines >= 2

    def _extract_participations(
        self, section: DocumentSection
    ) -> list[ExtractedParticipation]:
        """Extract raw participation data from section."""
        extractions = []
        content = section.content

        # Try to find entity names first
        entity_matches = []
        for pattern in self.ENTITY_PATTERNS:
            for match in re.finditer(pattern, content):
                entity_matches.append((match.start(), match.group(1).strip()))

        if not entity_matches:
            return extractions

        # For each entity, try to find associated data
        for i, (pos, entity_name) in enumerate(entity_matches):
            # Define search window (until next entity or end)
            if i + 1 < len(entity_matches):
                end_pos = entity_matches[i + 1][0]
            else:
                end_pos = min(pos + 500, len(content))

            window = content[pos:end_pos]

            extraction = ExtractedParticipation(
                raw_text=window[:200],
                entity_name_candidate=entity_name,
                location=f"Position {pos}",
            )

            # Find percentage
            for pattern in self.PERCENTAGE_PATTERNS:
                match = re.search(pattern, window)
                if match:
                    extraction.percentage_candidate = match.group(1)
                    break

            # Find amounts (first two numeric values could be equity and result)
            amounts = []
            for pattern in self.AMOUNT_PATTERNS:
                for match in re.finditer(pattern, window):
                    amounts.append(match.group(1))

            if len(amounts) >= 1:
                extraction.equity_candidate = amounts[0]
            if len(amounts) >= 2:
                extraction.result_candidate = amounts[1]

            extractions.append(extraction)

        return extractions

    def _assess_participation(
        self,
        extraction: ExtractedParticipation,
        protective_clause_found: bool,
    ) -> ParticipationAssessment:
        """Assess a single extracted participation against requirements."""
        assessment = ParticipationAssessment(
            entity_name=extraction.entity_name_candidate,
            entity_identified=extraction.entity_name_candidate is not None,
            protective_clause_claimed=protective_clause_found,
        )

        # Assess each required element
        for elem in REQUIRED_ELEMENTS:
            elem_assessment = ElementAssessment(
                element_id=elem.element_id,
                status=DisclosureStatus.NOT_ASSESSABLE,
            )

            if elem.element_id == "name_and_seat":
                if extraction.entity_name_candidate:
                    elem_assessment.status = DisclosureStatus.PRESENT
                    elem_assessment.extracted_value = extraction.entity_name_candidate
                else:
                    elem_assessment.status = DisclosureStatus.NOT_ASSESSABLE

            elif elem.element_id == "share_percentage":
                if extraction.percentage_candidate:
                    elem_assessment.status = DisclosureStatus.PRESENT
                    elem_assessment.extracted_value = extraction.percentage_candidate
                else:
                    elem_assessment.status = DisclosureStatus.ABSENT
                    elem_assessment.confidence_note = "Kein Prozentsatz im Kontext gefunden"

            elif elem.element_id == "equity_capital":
                if extraction.equity_candidate:
                    elem_assessment.status = DisclosureStatus.PRESENT
                    elem_assessment.extracted_value = extraction.equity_candidate
                elif protective_clause_found:
                    elem_assessment.status = DisclosureStatus.NOT_ASSESSABLE
                    elem_assessment.confidence_note = "Schutzklausel möglicherweise anwendbar"
                else:
                    elem_assessment.status = DisclosureStatus.ABSENT

            elif elem.element_id == "last_year_result":
                if extraction.result_candidate:
                    elem_assessment.status = DisclosureStatus.PRESENT
                    elem_assessment.extracted_value = extraction.result_candidate
                elif protective_clause_found:
                    elem_assessment.status = DisclosureStatus.NOT_ASSESSABLE
                    elem_assessment.confidence_note = "Schutzklausel möglicherweise anwendbar"
                else:
                    elem_assessment.status = DisclosureStatus.ABSENT

            assessment.element_assessments.append(elem_assessment)

        return assessment


# =============================================================================
# INTEGRATION FUNCTION
# =============================================================================

def evaluate_anteilsbesitz(document: Document) -> RuleEvaluationResult:
    """
    Main entry point for Anteilsbesitz evaluation.

    Called by ReviewEngine when processing checklist item for § 238 Abs 1 Z 2.
    """
    evaluator = AnteilsbesitzEvaluator()
    return evaluator.evaluate(document)
