"""Document data models."""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from datetime import datetime

from .enums import DocumentType, SectionType


@dataclass
class DocumentSection:
    """
    Represents a logical section within a notes document.

    Sections are identified by headings, numbering, or content patterns.
    """
    section_id: str
    title: str
    content: str
    section_type: SectionType
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    parent_section_id: Optional[str] = None
    subsections: list["DocumentSection"] = field(default_factory=list)

    def get_full_content(self) -> str:
        """Return section content including all subsections."""
        full_text = self.content
        for sub in self.subsections:
            full_text += "\n" + sub.get_full_content()
        return full_text

    def search_text(self, query: str, case_sensitive: bool = False) -> list[tuple[int, str]]:
        """
        Search for text within this section.

        Returns list of (line_number, matching_line) tuples.
        """
        content = self.content if case_sensitive else self.content.lower()
        query_normalized = query if case_sensitive else query.lower()

        matches = []
        for i, line in enumerate(content.split("\n")):
            if query_normalized in line:
                original_line = self.content.split("\n")[i]
                matches.append((i + 1, original_line.strip()))
        return matches


@dataclass
class Document:
    """
    Represents a parsed document.

    Can be a notes document (Anhang), UGB source, or checklist.
    """
    file_path: Path
    document_type: DocumentType
    raw_text: str
    sections: list[DocumentSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    parse_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def filename(self) -> str:
        return self.file_path.name

    @property
    def total_pages(self) -> Optional[int]:
        return self.metadata.get("total_pages")

    def get_section_by_id(self, section_id: str) -> Optional[DocumentSection]:
        """Find a section by its ID."""
        for section in self.sections:
            if section.section_id == section_id:
                return section
            for sub in section.subsections:
                if sub.section_id == section_id:
                    return sub
        return None

    def get_sections_by_type(self, section_type: SectionType) -> list[DocumentSection]:
        """Get all sections of a specific type."""
        result = []
        for section in self.sections:
            if section.section_type == section_type:
                result.append(section)
            for sub in section.subsections:
                if sub.section_type == section_type:
                    result.append(sub)
        return result

    def search_all(self, query: str, case_sensitive: bool = False) -> list[tuple[str, int, str]]:
        """
        Search entire document for text.

        Returns list of (section_id, line_number, matching_line) tuples.
        """
        results = []
        for section in self.sections:
            matches = section.search_text(query, case_sensitive)
            for line_num, line in matches:
                results.append((section.section_id, line_num, line))
        return results

    def get_full_text(self) -> str:
        """Return the complete document text."""
        return self.raw_text
