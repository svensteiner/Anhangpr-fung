"""
Citation and Reference Formatting.

Defines how the tool must reference sources in its output.
Ensures proper attribution and appropriate caveats based on source authority.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import date

from .classification import (
    SourceAuthority,
    CitationRequirement,
    get_classification,
)
from .metadata import SourceMetadata
from .registry import SourceReference


# =============================================================================
# CITATION TEMPLATES BY AUTHORITY
# =============================================================================

CITATION_TEMPLATES = {
    SourceAuthority.STATUTORY_LAW: {
        # Authoritative citations - no hedging needed
        "prefix": "Gemäß",
        "template": "{legal_reference}",
        "suffix": "",
        "caveat": None,
        "example": "Gemäß § 238 Abs 1 Z 2 UGB",
    },

    SourceAuthority.OFFICIAL_GUIDANCE: {
        # Interpretative but authoritative
        "prefix": "Nach Auffassung",
        "template": "{publisher} ({publication_year})",
        "suffix": "",
        "caveat": "behördliche Auffassung, keine Rechtsnorm",
        "example": "Nach Auffassung der FMA (2023)",
    },

    SourceAuthority.CHAMBER_PUBLICATION: {
        # Professional consensus
        "prefix": "Nach",
        "template": "{publisher}, {title} ({publication_year})",
        "suffix": "",
        "caveat": "berufsständische Auffassung",
        "example": "Nach IWP, Fachgutachten (2024)",
    },

    SourceAuthority.ACADEMIC_COMMENTARY: {
        # Scholarly interpretation
        "prefix": "Nach",
        "template": "{author} in {publisher}, {edition}",
        "suffix": "{specific_location}",
        "caveat": "Kommentarmeinung, abweichende Auffassungen möglich",
        "example": "Nach Doralt in Doralt/Nowotny/Kalss, UGB, 4. Aufl., § 238 Rz 15",
    },

    SourceAuthority.PRACTICE_NOTE: {
        # Industry practice
        "prefix": "In der Praxis wird vertreten",
        "template": "(vgl. {publisher}, {title})",
        "suffix": "",
        "caveat": "Praxishinweis, nicht normativ",
        "example": "In der Praxis wird vertreten (vgl. PwC, Anhangscheckliste 2024)",
    },

    SourceAuthority.TOOL_DERIVED: {
        # Tool's own interpretation - MUST be clearly marked
        "prefix": "Tool-interne Ableitung:",
        "template": "{title}",
        "suffix": "",
        "caveat": "NICHT AUTORITATIV - ersetzt nicht fachliche Beurteilung",
        "example": "Tool-interne Ableitung: Schwellenwertprüfung",
    },

    SourceAuthority.UNVERIFIED: {
        # Should never be used in output
        "prefix": "[QUELLE NICHT ZULÄSSIG]",
        "template": "",
        "suffix": "",
        "caveat": "QUELLE DARF NICHT ZITIERT WERDEN",
        "example": None,
    },
}


# =============================================================================
# CAVEAT REQUIREMENTS BY CONTEXT
# =============================================================================

CAVEATS = {
    "completeness_check": (
        "Vollständigkeit der vom Tool identifizierten Angaben nicht gewährleistet. "
        "Manuelle Prüfung durch den Wirtschaftsprüfer erforderlich."
    ),

    "interpretation_applied": (
        "Basierend auf Tool-interner Interpretation. "
        "Abweichende Auslegungen möglich."
    ),

    "threshold_derived": (
        "Schwellenwert aus rechtlicher Regelung abgeleitet. "
        "Grenzfälle erfordern fachliche Beurteilung."
    ),

    "protective_clause": (
        "Angemessenheit der Schutzklausel-Anwendung nicht automatisch beurteilbar. "
        "Ermessensentscheidung des Prüfers erforderlich."
    ),

    "no_legal_advice": (
        "Dieses Tool ersetzt nicht die rechtliche oder fachliche Beratung. "
        "Alle Aussagen sind als Prüfungsunterstützung zu verstehen."
    ),

    "source_age": (
        "Quelle möglicherweise nicht mehr aktuell. "
        "Prüfung auf zwischenzeitliche Rechtsänderungen erforderlich."
    ),
}


class CitationGenerator:
    """
    Generates properly formatted citations with appropriate caveats.
    """

    def __init__(self):
        self.templates = CITATION_TEMPLATES
        self.caveats = CAVEATS

    def format_citation(
        self,
        metadata: SourceMetadata,
        specific_location: Optional[str] = None,
        include_caveat: bool = True
    ) -> str:
        """
        Format a complete citation for a source.

        Args:
            metadata: Source metadata
            specific_location: Page, paragraph reference
            include_caveat: Whether to append the authority-level caveat

        Returns:
            Formatted citation string
        """
        template_info = self.templates.get(metadata.authority, self.templates[SourceAuthority.UNVERIFIED])

        # Build citation parts
        parts = []

        # Prefix
        if template_info["prefix"]:
            parts.append(template_info["prefix"])

        # Main template
        template = template_info["template"]
        if template:
            formatted = template.format(
                legal_reference=metadata.legal_reference or "",
                publisher=metadata.publisher or "",
                publication_year=metadata.publication_date.year if metadata.publication_date else "",
                author=metadata.author or "",
                title=metadata.title or "",
                edition=metadata.edition or "",
                specific_location=specific_location or metadata.excerpt_pages or "",
            )
            parts.append(formatted.strip())

        # Suffix (specific location)
        if template_info["suffix"] and specific_location:
            suffix = template_info["suffix"].format(specific_location=specific_location)
            parts.append(suffix)

        citation = " ".join(filter(None, parts))

        # Add caveat if requested
        if include_caveat and template_info["caveat"]:
            citation = f"{citation} [{template_info['caveat']}]"

        return citation

    def format_from_reference(
        self,
        reference: SourceReference,
        metadata: Optional[SourceMetadata] = None,
        include_caveat: bool = True
    ) -> str:
        """
        Format a citation from a SourceReference.

        If metadata is not provided, generates a minimal citation.
        """
        if metadata:
            return self.format_citation(
                metadata,
                specific_location=reference.specific_location,
                include_caveat=include_caveat
            )

        # Minimal citation without full metadata
        template_info = self.templates.get(reference.authority, self.templates[SourceAuthority.UNVERIFIED])

        citation = f"{template_info['prefix']} {reference.source_id}"
        if reference.specific_location:
            citation += f", {reference.specific_location}"

        if include_caveat and template_info["caveat"]:
            citation += f" [{template_info['caveat']}]"

        return citation

    def format_caveat(
        self,
        caveat_type: str,
        custom_text: Optional[str] = None
    ) -> str:
        """
        Format a caveat for inclusion in output.

        Args:
            caveat_type: Key from CAVEATS dictionary
            custom_text: Optional custom text to append

        Returns:
            Formatted caveat string
        """
        base_caveat = self.caveats.get(caveat_type, "")
        if custom_text:
            return f"{base_caveat} {custom_text}"
        return base_caveat

    def format_multi_source_citation(
        self,
        references: list[SourceReference],
        metadata_lookup: dict[str, SourceMetadata]
    ) -> str:
        """
        Format a citation combining multiple sources.

        Groups by authority level and presents in hierarchical order.
        """
        if not references:
            return "[Keine Quellen dokumentiert]"

        # Group by authority
        by_authority: dict[SourceAuthority, list[SourceReference]] = {}
        for ref in references:
            if ref.authority not in by_authority:
                by_authority[ref.authority] = []
            by_authority[ref.authority].append(ref)

        parts = []

        # Process in authority order (highest first)
        for authority in SourceAuthority:
            if authority in by_authority:
                refs = by_authority[authority]

                for ref in refs:
                    metadata = metadata_lookup.get(ref.source_id)
                    citation = self.format_from_reference(
                        ref, metadata, include_caveat=False
                    )
                    parts.append(citation)

        # Single combined caveat at the end
        lowest_authority = min(by_authority.keys(), key=lambda a: list(SourceAuthority).index(a))
        template_info = self.templates.get(lowest_authority)
        if template_info and template_info["caveat"]:
            combined = "; ".join(parts)
            return f"{combined} [{template_info['caveat']}]"

        return "; ".join(parts)


def format_citation(
    metadata: SourceMetadata,
    specific_location: Optional[str] = None,
    include_caveat: bool = True
) -> str:
    """Convenience function for single citation formatting."""
    generator = CitationGenerator()
    return generator.format_citation(metadata, specific_location, include_caveat)


def format_caveat(caveat_type: str, custom_text: Optional[str] = None) -> str:
    """Convenience function for caveat formatting."""
    generator = CitationGenerator()
    return generator.format_caveat(caveat_type, custom_text)


# =============================================================================
# OUTPUT FORMATTING HELPERS
# =============================================================================

def format_source_block_for_protocol(
    rule_id: str,
    references: list[SourceReference],
    metadata_lookup: dict[str, SourceMetadata]
) -> str:
    """
    Format a complete source documentation block for a review protocol.

    Returns Markdown-formatted text.
    """
    lines = [
        "#### Quellenangaben",
        "",
    ]

    if not references:
        lines.append("_Keine Quellen dokumentiert für diese Regel._")
        lines.append("")
        lines.append("**WARNUNG:** Regel ohne dokumentierte Quellengrundlage.")
        return "\n".join(lines)

    # Group by reference type
    legal_basis = [r for r in references if r.reference_type == "legal_basis"]
    interpretations = [r for r in references if r.reference_type in ("interpretation", "terminology")]
    examples = [r for r in references if r.reference_type == "example"]

    generator = CitationGenerator()

    if legal_basis:
        lines.append("**Rechtliche Grundlage:**")
        for ref in legal_basis:
            metadata = metadata_lookup.get(ref.source_id)
            citation = generator.format_from_reference(ref, metadata, include_caveat=False)
            lines.append(f"- {citation}")
        lines.append("")

    if interpretations:
        lines.append("**Interpretationsquellen:**")
        for ref in interpretations:
            metadata = metadata_lookup.get(ref.source_id)
            citation = generator.format_from_reference(ref, metadata, include_caveat=True)
            lines.append(f"- {citation}")
        lines.append("")

    if examples:
        lines.append("**Beispiele/Erläuterungen:**")
        for ref in examples:
            metadata = metadata_lookup.get(ref.source_id)
            citation = generator.format_from_reference(ref, metadata, include_caveat=True)
            lines.append(f"- {citation}")
        lines.append("")

    # Standard caveat
    lines.append("---")
    lines.append(f"_{CAVEATS['no_legal_advice']}_")

    return "\n".join(lines)
