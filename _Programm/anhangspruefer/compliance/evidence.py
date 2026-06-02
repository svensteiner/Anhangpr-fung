"""Evidence extraction and tracking."""

from dataclasses import dataclass
from typing import Optional
import re

from ..models.document import Document, DocumentSection
from ..models.finding import EvidenceItem
from ..models.checklist import ChecklistItem
from .knowledge.requirement_matcher import MatchResult
from ..utils.logging_config import get_logger

logger = get_logger("evidence")


class EvidenceExtractor:
    """
    Extracts and formats evidence from documents for findings.

    Evidence items are quotes or references from the notes document
    that support or contradict compliance with a disclosure requirement.

    NOTE: Evidence extraction is automated but requires manual validation.
    The tool may miss relevant evidence or misinterpret context.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.max_quote_length = self.config.get("max_quote_length", 500)
        self.max_evidence_items = self.config.get("max_evidence_items", 5)

    def extract_evidence(
        self,
        match_result: MatchResult,
        document: Document,
        item: ChecklistItem
    ) -> list[EvidenceItem]:
        """
        Extract evidence items from a match result.

        Args:
            match_result: Result of requirement matching
            document: The source document
            item: The checklist item being evaluated

        Returns:
            List of EvidenceItem objects
        """
        evidence_items = []

        # Extract evidence from matched quotes
        for section_id, quote, relevance in match_result.matched_quotes:
            section = document.get_section_by_id(section_id)
            if not section:
                continue

            evidence = EvidenceItem(
                section_id=section_id,
                section_title=section.title if section else section_id,
                quote=self._format_quote(quote),
                relevance_score=relevance,
                is_supporting=True,
            )

            # Try to find page number
            evidence.page_number = self._find_page_number(
                document, section_id, quote
            )

            evidence_items.append(evidence)

        # If no quotes found, extract from matched sections
        if not evidence_items and match_result.matched_sections:
            for section, score in match_result.matched_sections[:2]:
                # Extract first relevant paragraph
                quote = self._extract_first_relevant_paragraph(
                    section, item.search_keywords
                )
                if quote:
                    evidence = EvidenceItem(
                        section_id=section.section_id,
                        section_title=section.title,
                        quote=self._format_quote(quote),
                        relevance_score=score,
                        is_supporting=True,
                    )
                    evidence_items.append(evidence)

        # Limit number of evidence items
        evidence_items = evidence_items[:self.max_evidence_items]

        # Sort by relevance
        evidence_items.sort(key=lambda x: x.relevance_score, reverse=True)

        return evidence_items

    def _format_quote(self, quote: str) -> str:
        """Format a quote for presentation."""
        # Clean up whitespace
        quote = " ".join(quote.split())

        # Truncate if too long
        if len(quote) > self.max_quote_length:
            # Try to truncate at sentence boundary
            truncated = quote[:self.max_quote_length]
            last_period = truncated.rfind(".")
            if last_period > self.max_quote_length // 2:
                quote = truncated[:last_period + 1]
            else:
                quote = truncated + "..."

        return quote

    def _find_page_number(
        self,
        document: Document,
        section_id: str,
        quote: str
    ) -> Optional[int]:
        """Attempt to find the page number for a quote."""
        # If document has page metadata
        if "pages" in document.metadata:
            for page_info in document.metadata["pages"]:
                if quote[:50] in page_info.get("text", ""):
                    return page_info["page_number"]

        # Fall back to section metadata
        section = document.get_section_by_id(section_id)
        if section and section.start_page:
            return section.start_page

        return None

    def _extract_first_relevant_paragraph(
        self,
        section: DocumentSection,
        keywords: list[str]
    ) -> Optional[str]:
        """Extract the first paragraph containing keywords."""
        paragraphs = section.content.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if len(para) < 50:
                continue

            para_lower = para.lower()
            for keyword in keywords:
                if keyword.lower() in para_lower:
                    return para

        # If no keyword match, return first substantial paragraph
        for para in paragraphs:
            para = para.strip()
            if len(para) >= 100:
                return para

        return None

    def format_evidence_for_protocol(
        self,
        evidence_items: list[EvidenceItem]
    ) -> str:
        """
        Format evidence items for inclusion in the review protocol.

        Returns formatted markdown text.
        """
        if not evidence_items:
            return "_Keine automatisch identifizierten Nachweise._"

        lines = []
        for i, ev in enumerate(evidence_items, 1):
            indicator = "+" if ev.is_supporting else "-"
            header = f"{i}. {ev.section_title}"
            if ev.page_number:
                header += f" (S. {ev.page_number})"

            lines.append(f"**{header}**")
            lines.append(f"> {ev.quote}")
            lines.append("")

        return "\n".join(lines)

    def identify_missing_evidence(
        self,
        item: ChecklistItem,
        evidence_items: list[EvidenceItem]
    ) -> list[str]:
        """
        Identify what evidence might be missing for a checklist item.

        Returns list of potentially missing elements.

        NOTE: This is a heuristic analysis and should not be treated
        as definitive. The auditor must verify completeness.
        """
        missing = []

        # Check if we have any evidence at all
        if not evidence_items:
            missing.append(
                "Keine automatisch identifizierbaren Angaben zum Thema gefunden"
            )
            return missing

        # Check for specific elements based on keywords
        evidence_text = " ".join(e.quote.lower() for e in evidence_items)

        # Keywords that should typically appear together
        keyword_groups = {
            "fristigkeit": ["restlaufzeit", "fristigkeit", "jahr", "laufzeit"],
            "betrag": ["euro", "eur", "teur", "mio", "betrag"],
            "erlaeuterung": ["weil", "grund", "aufgrund", "begründung", "erklärt"],
        }

        for group_name, keywords in keyword_groups.items():
            found = any(kw in evidence_text for kw in keywords)
            if not found:
                if any(kw.lower() in k.lower()
                       for kw in keywords
                       for k in item.search_keywords):
                    missing.append(
                        f"Mögliche fehlende Angabe: {group_name.capitalize()}"
                    )

        return missing
