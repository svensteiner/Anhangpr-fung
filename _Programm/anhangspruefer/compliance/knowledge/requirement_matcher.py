"""Requirement to document matching logic."""

from dataclasses import dataclass
from typing import Optional

from ...models.document import Document, DocumentSection
from ...models.checklist import ChecklistItem, Checklist
from ...utils.text_processing import fuzzy_match, extract_ugb_reference
from ...utils.logging_config import get_logger

logger = get_logger("requirement_matcher")


@dataclass
class MatchResult:
    """Result of matching a checklist item to document content."""
    checklist_item_id: str
    matched_sections: list[tuple[DocumentSection, float]]  # (section, relevance_score)
    matched_quotes: list[tuple[str, str, float]]  # (section_id, quote, relevance)
    ugb_references_found: list[str]
    confidence: float  # Overall match confidence


class RequirementMatcher:
    """
    Matches checklist requirements to document sections and content.

    Uses keyword matching and UGB reference detection to find
    relevant content in the notes document.

    NOTE: This is a heuristic-based matcher. Results should be
    validated by the auditor. False positives and false negatives
    are expected and must be addressed through manual review.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.fuzzy_threshold = self.config.get("fuzzy_threshold", 0.6)
        self.max_quotes = self.config.get("max_quotes", 5)

    def match_item(
        self,
        item: ChecklistItem,
        document: Document
    ) -> MatchResult:
        """
        Match a single checklist item against a document.

        Args:
            item: The checklist item to match
            document: The document to search

        Returns:
            MatchResult with matched sections and quotes
        """
        matched_sections = []
        matched_quotes = []
        ugb_refs_found = []

        # Get search patterns
        patterns = item.get_search_patterns()

        # Search in each section
        for section in document.sections:
            section_score = self._score_section(section, patterns)

            if section_score > 0:
                matched_sections.append((section, section_score))

                # Extract relevant quotes
                quotes = self._extract_quotes(section, patterns)
                for quote, score in quotes:
                    matched_quotes.append((section.section_id, quote, score))

                # Find UGB references in section
                refs = extract_ugb_reference(section.content)
                for ref in refs:
                    if any(item_ref in ref for item_ref in item.ugb_references):
                        if ref not in ugb_refs_found:
                            ugb_refs_found.append(ref)

        # Also search raw text for UGB references
        all_refs = extract_ugb_reference(document.raw_text)
        for ref in all_refs:
            for item_ref in item.ugb_references:
                if item_ref.replace("§ ", "§") in ref.replace("§ ", "§"):
                    if ref not in ugb_refs_found:
                        ugb_refs_found.append(ref)

        # Sort by relevance
        matched_sections.sort(key=lambda x: x[1], reverse=True)
        matched_quotes.sort(key=lambda x: x[2], reverse=True)

        # Limit quotes
        matched_quotes = matched_quotes[:self.max_quotes]

        # Calculate overall confidence
        confidence = self._calculate_confidence(
            matched_sections, matched_quotes, ugb_refs_found, item
        )

        return MatchResult(
            checklist_item_id=item.item_id,
            matched_sections=matched_sections,
            matched_quotes=matched_quotes,
            ugb_references_found=ugb_refs_found,
            confidence=confidence,
        )

    def match_all(
        self,
        checklist: Checklist,
        document: Document
    ) -> dict[str, MatchResult]:
        """
        Match all checklist items against a document.

        Args:
            checklist: The checklist with items to match
            document: The document to search

        Returns:
            Dictionary mapping item_id to MatchResult
        """
        results = {}

        for item in checklist.items:
            result = self.match_item(item, document)
            results[item.item_id] = result

            logger.debug(
                f"Matched {item.item_id}: confidence={result.confidence:.2f}, "
                f"sections={len(result.matched_sections)}, "
                f"quotes={len(result.matched_quotes)}"
            )

        # Log summary
        high_conf = sum(1 for r in results.values() if r.confidence >= 0.7)
        low_conf = sum(1 for r in results.values() if r.confidence < 0.3)

        logger.info(
            f"Matching complete: {len(results)} items, "
            f"{high_conf} high confidence, {low_conf} low confidence"
        )

        return results

    def _score_section(
        self,
        section: DocumentSection,
        patterns: list[str]
    ) -> float:
        """Score how well a section matches the search patterns."""
        if not patterns:
            return 0.0

        content_lower = section.content.lower()
        title_lower = section.title.lower()

        total_score = 0.0
        matches_found = 0

        for pattern in patterns:
            pattern_lower = pattern.lower()

            # Exact match in title (high weight)
            if pattern_lower in title_lower:
                total_score += 0.8
                matches_found += 1
                continue

            # Exact match in content
            if pattern_lower in content_lower:
                count = content_lower.count(pattern_lower)
                total_score += min(0.5, 0.1 * count)
                matches_found += 1
                continue

            # Fuzzy match
            is_match, score = fuzzy_match(content_lower, pattern_lower, self.fuzzy_threshold)
            if is_match:
                total_score += score * 0.3
                matches_found += 1

        if matches_found == 0:
            return 0.0

        # Normalize by number of patterns
        return min(1.0, total_score / len(patterns))

    def _extract_quotes(
        self,
        section: DocumentSection,
        patterns: list[str]
    ) -> list[tuple[str, float]]:
        """Extract relevant quotes from a section."""
        quotes = []
        lines = section.content.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 20:
                continue

            line_lower = line.lower()

            for pattern in patterns:
                if pattern.lower() in line_lower:
                    # Extract context (current line + neighbors)
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    context = " ".join(
                        l.strip() for l in lines[start:end] if l.strip()
                    )

                    # Truncate if too long
                    if len(context) > 500:
                        context = context[:500] + "..."

                    # Calculate relevance
                    relevance = line_lower.count(pattern.lower()) * 0.2
                    relevance = min(1.0, relevance + 0.3)

                    quotes.append((context, relevance))
                    break  # One quote per line

        # Remove duplicates
        seen = set()
        unique_quotes = []
        for quote, rel in quotes:
            quote_key = quote[:100]
            if quote_key not in seen:
                seen.add(quote_key)
                unique_quotes.append((quote, rel))

        return unique_quotes

    def _calculate_confidence(
        self,
        sections: list[tuple[DocumentSection, float]],
        quotes: list[tuple[str, str, float]],
        ugb_refs: list[str],
        item: ChecklistItem
    ) -> float:
        """
        Calculate overall confidence for a match.

        The confidence score is a heuristic measure and should not
        be interpreted as a probability of compliance.
        """
        if not sections and not quotes:
            return 0.0

        confidence = 0.0

        # Section matches contribute
        if sections:
            top_section_score = sections[0][1]
            confidence += top_section_score * 0.4

        # Quote relevance contributes
        if quotes:
            avg_quote_relevance = sum(q[2] for q in quotes) / len(quotes)
            confidence += avg_quote_relevance * 0.3

        # UGB reference presence contributes
        if item.ugb_references:
            ref_coverage = len(ugb_refs) / len(item.ugb_references)
            confidence += min(0.3, ref_coverage * 0.3)

        return min(1.0, confidence)

    def find_missing_disclosures(
        self,
        checklist: Checklist,
        document: Document,
        confidence_threshold: float = 0.3
    ) -> list[ChecklistItem]:
        """
        Find checklist items that appear to have no corresponding
        disclosure in the document.

        NOTE: Low confidence does not necessarily mean non-compliance.
        Manual review is required to verify missing disclosures.
        """
        results = self.match_all(checklist, document)

        missing = []
        for item in checklist.items:
            result = results.get(item.item_id)
            if result and result.confidence < confidence_threshold:
                missing.append(item)

        return missing
