"""Section detection for notes documents."""

import re
from dataclasses import dataclass
from typing import Optional

from ..models.document import Document, DocumentSection
from ..models.enums import SectionType
from ..config import SECTION_KEYWORDS
from ..utils.logging_config import get_logger

logger = get_logger("section_detector")


@dataclass
class DetectedHeading:
    """Represents a detected section heading."""
    line_number: int
    text: str
    level: int  # 1 = main section, 2 = subsection, etc.
    section_type: SectionType
    confidence: float  # 0.0 to 1.0


class SectionDetector:
    """
    Detects and extracts logical sections from notes documents.

    Uses heuristics based on common German financial statement
    note structures. May require adjustment for specific document formats.

    NOTE: Section detection is inherently heuristic and may require
    manual validation for unusual document layouts.
    """

    # Heading patterns with priority
    HEADING_PATTERNS = [
        # Roman numerals (I., II., III., etc.)
        (re.compile(r"^([IVXLC]+)\.\s+(.+)$"), 1),
        # Numbers with dots (1., 1.1, 1.1.1)
        (re.compile(r"^(\d+(?:\.\d+)*)\.\s+(.+)$"), 2),
        # Letters (A., B., a), b))
        (re.compile(r"^([A-Za-z])[.\)]\s+(.+)$"), 2),
        # All caps headings
        (re.compile(r"^([A-ZÄÖÜ][A-ZÄÖÜ\s]{5,})$"), 1),
    ]

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.min_section_length = self.config.get("min_section_length", 50)

    def detect_sections(self, document: Document) -> list[DocumentSection]:
        """
        Detect sections in a document.

        Args:
            document: The parsed document

        Returns:
            List of detected DocumentSection objects
        """
        text = document.raw_text
        lines = text.split("\n")

        # Find all potential headings
        headings = self._find_headings(lines)

        if not headings:
            logger.warning("No section headings detected in document")
            # Return entire document as single section
            return [
                DocumentSection(
                    section_id="main",
                    title="Gesamter Anhang",
                    content=text,
                    section_type=SectionType.UNKNOWN,
                    start_line=0,
                    end_line=len(lines),
                )
            ]

        # Build section structure
        sections = self._build_sections(lines, headings)

        logger.info(f"Detected {len(sections)} sections")

        return sections

    def _find_headings(self, lines: list[str]) -> list[DetectedHeading]:
        """Find all potential section headings."""
        headings = []

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            heading = self._analyze_line_as_heading(i, line)
            if heading:
                headings.append(heading)

        return headings

    def _analyze_line_as_heading(
        self,
        line_num: int,
        line: str
    ) -> Optional[DetectedHeading]:
        """Analyze a line to determine if it's a section heading."""
        # Check against patterns
        for pattern, level in self.HEADING_PATTERNS:
            match = pattern.match(line)
            if match:
                section_type = self._determine_section_type(line)
                return DetectedHeading(
                    line_number=line_num,
                    text=line,
                    level=level,
                    section_type=section_type,
                    confidence=0.8,
                )

        # Check against known keywords
        for category, keywords in SECTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in line.lower():
                    section_type = self._category_to_section_type(category)
                    return DetectedHeading(
                        line_number=line_num,
                        text=line,
                        level=2,
                        section_type=section_type,
                        confidence=0.6,
                    )

        return None

    def _determine_section_type(self, heading_text: str) -> SectionType:
        """Determine section type from heading text."""
        text_lower = heading_text.lower()

        # Map keywords to section types
        keyword_mapping = {
            SectionType.GENERAL_INFORMATION: [
                "allgemein", "grundlage", "einleitung"
            ],
            SectionType.ACCOUNTING_POLICIES: [
                "bilanzierung", "bewertung", "methoden",
                "rechnungslegung", "grundsätze"
            ],
            SectionType.BALANCE_SHEET_DISCLOSURES: [
                "bilanz", "aktiva", "passiva", "anlagevermögen",
                "umlaufvermögen", "eigenkapital", "verbindlichkeiten",
                "rückstellung", "forderung"
            ],
            SectionType.INCOME_STATEMENT_DISCLOSURES: [
                "guv", "gewinn", "verlust", "ertrag", "aufwand",
                "umsatz", "erlös"
            ],
            SectionType.RELATED_PARTIES: [
                "nahesteh", "verbunden", "beteiligung",
                "geschäftsführ", "vorstand", "aufsichtsrat"
            ],
            SectionType.EVENTS_AFTER_REPORTING: [
                "ereignis", "bilanzstichtag", "nachtrag"
            ],
        }

        for section_type, keywords in keyword_mapping.items():
            for kw in keywords:
                if kw in text_lower:
                    return section_type

        return SectionType.OTHER_DISCLOSURES

    def _category_to_section_type(self, category: str) -> SectionType:
        """Map config category to SectionType."""
        mapping = {
            "bilanzierung": SectionType.ACCOUNTING_POLICIES,
            "anlagevermoegen": SectionType.BALANCE_SHEET_DISCLOSURES,
            "finanzanlagen": SectionType.BALANCE_SHEET_DISCLOSURES,
            "forderungen": SectionType.BALANCE_SHEET_DISCLOSURES,
            "verbindlichkeiten": SectionType.BALANCE_SHEET_DISCLOSURES,
            "rueckstellungen": SectionType.BALANCE_SHEET_DISCLOSURES,
            "eigenkapital": SectionType.BALANCE_SHEET_DISCLOSURES,
            "haftung": SectionType.OTHER_DISCLOSURES,
            "personal": SectionType.OTHER_DISCLOSURES,
            "organe": SectionType.RELATED_PARTIES,
            "umsatz": SectionType.INCOME_STATEMENT_DISCLOSURES,
        }
        return mapping.get(category, SectionType.OTHER_DISCLOSURES)

    def _build_sections(
        self,
        lines: list[str],
        headings: list[DetectedHeading]
    ) -> list[DocumentSection]:
        """Build section objects from detected headings."""
        sections = []

        for i, heading in enumerate(headings):
            # Determine section end
            if i + 1 < len(headings):
                end_line = headings[i + 1].line_number
            else:
                end_line = len(lines)

            # Extract content
            content_lines = lines[heading.line_number:end_line]
            content = "\n".join(content_lines)

            # Skip sections that are too short
            if len(content.strip()) < self.min_section_length:
                continue

            section = DocumentSection(
                section_id=f"section_{i+1}",
                title=heading.text,
                content=content,
                section_type=heading.section_type,
                start_line=heading.line_number,
                end_line=end_line,
            )

            sections.append(section)

        return sections

    def find_section_for_topic(
        self,
        sections: list[DocumentSection],
        topic: str
    ) -> list[DocumentSection]:
        """
        Find sections that likely contain information about a topic.

        Args:
            sections: List of document sections
            topic: Topic to search for (e.g., "Anlagevermögen")

        Returns:
            List of matching sections, ordered by relevance
        """
        matches = []
        topic_lower = topic.lower()

        for section in sections:
            score = 0.0

            # Check title
            if topic_lower in section.title.lower():
                score += 0.5

            # Check content
            content_lower = section.content.lower()
            occurrences = content_lower.count(topic_lower)
            if occurrences > 0:
                score += min(0.5, occurrences * 0.1)

            if score > 0:
                matches.append((section, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return [section for section, _ in matches]
