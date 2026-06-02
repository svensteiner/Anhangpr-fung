"""Compliance evaluation logic."""

from dataclasses import dataclass
from typing import Optional

from ..models.enums import ComplianceStatus
from ..models.checklist import ChecklistItem
from ..models.finding import Finding, EvidenceItem
from .knowledge.requirement_matcher import MatchResult
from ..utils.logging_config import get_logger

logger = get_logger("evaluator")


@dataclass
class EvaluationCriteria:
    """Criteria for compliance evaluation."""
    min_confidence_for_compliant: float = 0.7
    min_confidence_for_partial: float = 0.4
    min_evidence_count: int = 1
    require_ugb_reference: bool = False


class ComplianceEvaluator:
    """
    Evaluates compliance status for checklist items.

    IMPORTANT: This evaluator provides PRELIMINARY assessments only.
    All status determinations require validation by a qualified auditor.

    The evaluation logic is intentionally conservative:
    - When in doubt, status is set to NOT_ASSESSABLE
    - High thresholds are used for COMPLIANT status
    - Clear documentation of judgment requirements

    NOTE TO IMPLEMENTERS: The evaluation thresholds and logic should
    be calibrated based on audit experience and firm methodology.
    """

    def __init__(
        self,
        criteria: Optional[EvaluationCriteria] = None,
        config: Optional[dict] = None
    ):
        self.criteria = criteria or EvaluationCriteria()
        self.config = config or {}

    def evaluate(
        self,
        item: ChecklistItem,
        match_result: MatchResult,
        evidence: list[EvidenceItem]
    ) -> Finding:
        """
        Evaluate a single checklist item.

        Args:
            item: The checklist item being evaluated
            match_result: Result of requirement matching
            evidence: Extracted evidence items

        Returns:
            Finding with preliminary status assessment
        """
        # Determine status based on matching results
        status = self._determine_status(match_result, evidence, item)

        # Generate technical reasoning
        reasoning = self._generate_reasoning(status, match_result, evidence, item)

        # Identify areas requiring judgment
        judgment_areas = self._identify_judgment_areas(item, status, evidence)

        finding = Finding(
            checklist_item_id=item.item_id,
            status=status,
            ugb_references=item.ugb_references,
            evidence=evidence,
            missing_elements=self._identify_missing_elements(item, evidence),
            technical_reasoning=reasoning,
            requires_judgment=True,  # Always true - auditor must validate
            judgment_areas=judgment_areas,
        )

        logger.debug(
            f"Evaluated {item.item_id}: status={status.value}, "
            f"confidence={match_result.confidence:.2f}"
        )

        return finding

    def _determine_status(
        self,
        match_result: MatchResult,
        evidence: list[EvidenceItem],
        item: ChecklistItem
    ) -> ComplianceStatus:
        """
        Determine preliminary compliance status.

        Uses conservative thresholds to minimize false positives.
        """
        confidence = match_result.confidence
        evidence_count = len(evidence)
        has_ugb_refs = len(match_result.ugb_references_found) > 0

        # High confidence with sufficient evidence
        if (confidence >= self.criteria.min_confidence_for_compliant and
            evidence_count >= self.criteria.min_evidence_count):

            if self.criteria.require_ugb_reference and not has_ugb_refs:
                return ComplianceStatus.PARTIALLY_COMPLIANT
            return ComplianceStatus.COMPLIANT

        # Medium confidence - partial compliance
        if (confidence >= self.criteria.min_confidence_for_partial and
            evidence_count >= 1):
            return ComplianceStatus.PARTIALLY_COMPLIANT

        # Low confidence with some evidence
        if confidence > 0.1 and evidence_count > 0:
            return ComplianceStatus.PARTIALLY_COMPLIANT

        # Very low or no confidence
        if confidence <= 0.1:
            return ComplianceStatus.NOT_COMPLIANT

        # Default - cannot assess automatically
        return ComplianceStatus.NOT_ASSESSABLE

    def _generate_reasoning(
        self,
        status: ComplianceStatus,
        match_result: MatchResult,
        evidence: list[EvidenceItem],
        item: ChecklistItem
    ) -> str:
        """Generate technical reasoning for the assessment."""
        reasoning_parts = []

        # Confidence level
        confidence = match_result.confidence
        if confidence >= 0.7:
            reasoning_parts.append(
                f"Hohe Übereinstimmung (Konfidenz: {confidence:.0%}) "
                "mit den Suchkriterien gefunden."
            )
        elif confidence >= 0.4:
            reasoning_parts.append(
                f"Teilweise Übereinstimmung (Konfidenz: {confidence:.0%}) "
                "mit den Suchkriterien gefunden."
            )
        elif confidence > 0:
            reasoning_parts.append(
                f"Geringe Übereinstimmung (Konfidenz: {confidence:.0%}) "
                "mit den Suchkriterien."
            )
        else:
            reasoning_parts.append(
                "Keine relevanten Textstellen automatisch identifiziert."
            )

        # Evidence summary
        if evidence:
            reasoning_parts.append(
                f"{len(evidence)} potenzielle Nachweisstellen identifiziert."
            )
            sections = set(e.section_title for e in evidence)
            if sections:
                reasoning_parts.append(
                    f"Relevante Abschnitte: {', '.join(list(sections)[:3])}"
                )
        else:
            reasoning_parts.append(
                "Keine spezifischen Textnachweise extrahiert."
            )

        # UGB references
        if match_result.ugb_references_found:
            reasoning_parts.append(
                f"UGB-Verweise im Dokument: {', '.join(match_result.ugb_references_found[:3])}"
            )

        # Status-specific notes
        status_notes = {
            ComplianceStatus.COMPLIANT: (
                "Vorläufige Bewertung: Angaben scheinen vorhanden. "
                "Prüfervalidierung erforderlich."
            ),
            ComplianceStatus.PARTIALLY_COMPLIANT: (
                "Vorläufige Bewertung: Angaben möglicherweise unvollständig. "
                "Manuelle Prüfung erforderlich."
            ),
            ComplianceStatus.NOT_COMPLIANT: (
                "Vorläufige Bewertung: Keine entsprechenden Angaben gefunden. "
                "Prüferfeststellung erforderlich."
            ),
            ComplianceStatus.NOT_ASSESSABLE: (
                "Automatische Beurteilung nicht möglich. "
                "Manuelle Prüfung durch Wirtschaftsprüfer erforderlich."
            ),
        }
        reasoning_parts.append(status_notes.get(status, ""))

        return " ".join(reasoning_parts)

    def _identify_judgment_areas(
        self,
        item: ChecklistItem,
        status: ComplianceStatus,
        evidence: list[EvidenceItem]
    ) -> list[str]:
        """Identify specific areas requiring professional judgment."""
        judgment_areas = []

        # Always include standard judgment note
        judgment_areas.append(
            "Vollständigkeit der identifizierten Angaben prüfen"
        )

        # Status-specific judgment areas
        if status == ComplianceStatus.PARTIALLY_COMPLIANT:
            judgment_areas.append(
                "Fehlende Teilaspekte der Angabepflicht identifizieren"
            )

        if status == ComplianceStatus.NOT_COMPLIANT:
            judgment_areas.append(
                "Prüfen ob Angabepflicht tatsächlich besteht (Wesentlichkeit, Anwendbarkeit)"
            )

        if status == ComplianceStatus.NOT_ASSESSABLE:
            judgment_areas.append(
                "Manuelle Suche nach relevanten Angaben durchführen"
            )

        # Item-specific judgment
        if item.judgment_guidance:
            judgment_areas.append(item.judgment_guidance)

        return judgment_areas

    def _identify_missing_elements(
        self,
        item: ChecklistItem,
        evidence: list[EvidenceItem]
    ) -> list[str]:
        """Identify potentially missing disclosure elements."""
        missing = []

        if not evidence:
            missing.append(
                "Keine Angaben zum Thema automatisch identifiziert"
            )
        else:
            # Check evidence for completeness indicators
            evidence_text = " ".join(e.quote.lower() for e in evidence)

            # Common completeness checks
            if "vorjahr" not in evidence_text and "vergleichszahl" not in evidence_text:
                missing.append("Möglicherweise fehlende Vorjahresvergleichszahlen")

            if "begründ" not in evidence_text and "weil" not in evidence_text:
                if any(kw in item.description.lower()
                       for kw in ["erläuter", "begründ", "angab"]):
                    missing.append("Möglicherweise fehlende Erläuterung/Begründung")

        return missing


class EvaluationSummary:
    """
    Generates summary statistics for evaluation results.
    """

    @staticmethod
    def summarize(findings: list[Finding]) -> dict:
        """Generate summary statistics."""
        total = len(findings)
        if total == 0:
            return {"total": 0}

        status_counts = {}
        for finding in findings:
            status = finding.effective_status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total": total,
            "status_breakdown": status_counts,
            "requiring_review": sum(
                1 for f in findings if not f.auditor_reviewed
            ),
            "with_evidence": sum(
                1 for f in findings if len(f.evidence) > 0
            ),
            "compliance_rate": (
                status_counts.get(ComplianceStatus.COMPLIANT.value, 0) / total
                if total > 0 else 0
            ),
        }
