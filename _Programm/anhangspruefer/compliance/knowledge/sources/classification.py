"""
Source Classification System for Audit-Proof Knowledge Management

This module defines the strict classification of knowledge sources
used by the Anhangsprüfer tool. Each classification carries specific
authority levels, storage rules, and referencing requirements.

Principle: The tool must never claim authority beyond its cited sources.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import date


class SourceAuthority(Enum):
    """
    Authority level of a knowledge source.

    Higher authority = more reliable for audit purposes.
    Lower authority = requires more explicit caveats.
    """

    # Level 1: Primary Law (höchste Autorität)
    STATUTORY_LAW = "statutory_law"
    # Full legal text as published in official gazette (BGBl.)
    # May be cited as authoritative legal requirement
    # Storage: Full text permitted (public domain)

    # Level 2: Official Guidance (behördliche Stellungnahmen)
    OFFICIAL_GUIDANCE = "official_guidance"
    # Published by regulatory bodies (FMA, BMF, etc.)
    # May be cited as authoritative interpretation
    # Storage: Full text if publicly available

    # Level 3: Professional Chamber Publications
    CHAMBER_PUBLICATION = "chamber_publication"
    # KSW (Kammer der Steuerberater und Wirtschaftsprüfer)
    # IWP (Institut Österreichischer Wirtschaftsprüfer)
    # May be cited as professional consensus
    # Storage: Excerpts with proper attribution

    # Level 4: Academic Commentary (Kommentarliteratur)
    ACADEMIC_COMMENTARY = "academic_commentary"
    # Published legal commentaries (Doralt, Nowotny, etc.)
    # May be cited as scholarly interpretation
    # Storage: Brief excerpts only, no full reproduction

    # Level 5: Practice Notes
    PRACTICE_NOTE = "practice_note"
    # Big 4 publications, audit firm guidance
    # May be cited as industry practice reference
    # Storage: Summaries with attribution, no proprietary content

    # Level 6: Tool-Derived Knowledge
    TOOL_DERIVED = "tool_derived"
    # Interpretations made by tool developers
    # MUST be explicitly marked as non-authoritative
    # Storage: Full documentation of derivation logic

    # Level 7: Unverified (must not be used)
    UNVERIFIED = "unverified"
    # Forum posts, blogs, undated materials
    # CANNOT be cited, MUST NOT influence rules
    # Storage: Not permitted


class StoragePermission(Enum):
    """What may be stored locally for this source type."""

    FULL_TEXT = "full_text"              # Complete document
    SUBSTANTIAL_EXCERPT = "excerpt"       # Longer passages with attribution
    BRIEF_QUOTE = "brief_quote"          # Short quotes (< 100 words)
    SUMMARY_ONLY = "summary_only"        # Paraphrased summary, no direct quotes
    METADATA_ONLY = "metadata_only"      # Only reference, no content
    NOT_PERMITTED = "not_permitted"      # Cannot be stored


class CitationRequirement(Enum):
    """How this source must be referenced when used."""

    AUTHORITATIVE = "authoritative"
    # "Gemäß § X UGB..."
    # Direct legal citation permitted

    INTERPRETATIVE = "interpretative"
    # "Nach Auffassung des IWP..."
    # Must attribute interpretation to source

    INFORMATIVE = "informative"
    # "In der Praxis wird vertreten..."
    # Must indicate non-binding character

    INTERNAL = "internal"
    # "Tool-interne Ableitung (nicht autoritativ)..."
    # Must explicitly disclaim authority


@dataclass(frozen=True)
class SourceClassification:
    """Complete classification profile for a source type."""

    authority: SourceAuthority
    storage_permission: StoragePermission
    citation_requirement: CitationRequirement
    requires_retrieval_date: bool
    requires_verification: bool
    max_excerpt_words: Optional[int]
    legal_basis_for_storage: str
    usage_caveat: str


# =============================================================================
# CLASSIFICATION DEFINITIONS
# =============================================================================

SOURCE_CLASSIFICATIONS = {
    SourceAuthority.STATUTORY_LAW: SourceClassification(
        authority=SourceAuthority.STATUTORY_LAW,
        storage_permission=StoragePermission.FULL_TEXT,
        citation_requirement=CitationRequirement.AUTHORITATIVE,
        requires_retrieval_date=True,
        requires_verification=False,  # Official text is self-verifying
        max_excerpt_words=None,  # No limit
        legal_basis_for_storage="Amtliche Werke sind gemeinfrei (§ 7 UrhG)",
        usage_caveat="",  # No caveat needed for law
    ),

    SourceAuthority.OFFICIAL_GUIDANCE: SourceClassification(
        authority=SourceAuthority.OFFICIAL_GUIDANCE,
        storage_permission=StoragePermission.FULL_TEXT,
        citation_requirement=CitationRequirement.INTERPRETATIVE,
        requires_retrieval_date=True,
        requires_verification=True,
        max_excerpt_words=None,
        legal_basis_for_storage="Behördliche Veröffentlichungen zur Rechtsanwendung",
        usage_caveat="Behördliche Auffassung, keine Rechtsnorm",
    ),

    SourceAuthority.CHAMBER_PUBLICATION: SourceClassification(
        authority=SourceAuthority.CHAMBER_PUBLICATION,
        storage_permission=StoragePermission.SUBSTANTIAL_EXCERPT,
        citation_requirement=CitationRequirement.INTERPRETATIVE,
        requires_retrieval_date=True,
        requires_verification=True,
        max_excerpt_words=500,
        legal_basis_for_storage="Zitatrecht (§ 42f UrhG) für fachliche Auseinandersetzung",
        usage_caveat="Berufsständische Auffassung, nicht rechtsverbindlich",
    ),

    SourceAuthority.ACADEMIC_COMMENTARY: SourceClassification(
        authority=SourceAuthority.ACADEMIC_COMMENTARY,
        storage_permission=StoragePermission.BRIEF_QUOTE,
        citation_requirement=CitationRequirement.INTERPRETATIVE,
        requires_retrieval_date=True,
        requires_verification=True,
        max_excerpt_words=100,
        legal_basis_for_storage="Zitatrecht (§ 42f UrhG) für wissenschaftliche Zwecke",
        usage_caveat="Kommentarmeinung, abweichende Auffassungen möglich",
    ),

    SourceAuthority.PRACTICE_NOTE: SourceClassification(
        authority=SourceAuthority.PRACTICE_NOTE,
        storage_permission=StoragePermission.SUMMARY_ONLY,
        citation_requirement=CitationRequirement.INFORMATIVE,
        requires_retrieval_date=True,
        requires_verification=True,
        max_excerpt_words=50,
        legal_basis_for_storage="Keine Speicherung urheberrechtlich geschützter Inhalte",
        usage_caveat="Praxishinweis ohne normative Wirkung",
    ),

    SourceAuthority.TOOL_DERIVED: SourceClassification(
        authority=SourceAuthority.TOOL_DERIVED,
        storage_permission=StoragePermission.FULL_TEXT,
        citation_requirement=CitationRequirement.INTERNAL,
        requires_retrieval_date=False,
        requires_verification=False,
        max_excerpt_words=None,
        legal_basis_for_storage="Eigene Ableitung, kein Urheberrechtsschutz Dritter",
        usage_caveat="ACHTUNG: Tool-interne Interpretation, nicht autoritativ, "
                     "ersetzt nicht fachliche Beurteilung",
    ),

    SourceAuthority.UNVERIFIED: SourceClassification(
        authority=SourceAuthority.UNVERIFIED,
        storage_permission=StoragePermission.NOT_PERMITTED,
        citation_requirement=CitationRequirement.INTERNAL,
        requires_retrieval_date=True,
        requires_verification=True,
        max_excerpt_words=0,
        legal_basis_for_storage="NICHT ZULÄSSIG",
        usage_caveat="QUELLE NICHT VERWENDBAR",
    ),
}


def get_classification(authority: SourceAuthority) -> SourceClassification:
    """Get the classification profile for a source authority level."""
    return SOURCE_CLASSIFICATIONS[authority]


def validate_storage_permission(
    authority: SourceAuthority,
    content_word_count: int
) -> tuple[bool, str]:
    """
    Validate whether content may be stored for this source type.

    Returns: (is_permitted, reason)
    """
    classification = get_classification(authority)

    if classification.storage_permission == StoragePermission.NOT_PERMITTED:
        return False, "Speicherung für diese Quellenart nicht zulässig"

    if classification.storage_permission == StoragePermission.METADATA_ONLY:
        if content_word_count > 0:
            return False, "Nur Metadaten dürfen gespeichert werden"

    if classification.max_excerpt_words is not None:
        if content_word_count > classification.max_excerpt_words:
            return False, (
                f"Maximale Wortanzahl überschritten: "
                f"{content_word_count} > {classification.max_excerpt_words}"
            )

    return True, "Speicherung zulässig"
