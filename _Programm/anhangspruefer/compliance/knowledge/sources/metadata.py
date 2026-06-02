"""
Mandatory Metadata Schema for Stored Sources.

Every stored source MUST have complete metadata to ensure traceability,
proper attribution, and audit-proof documentation of knowledge origins.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Literal
from pathlib import Path
import json
import hashlib

from .classification import SourceAuthority, StoragePermission


@dataclass
class SourceMetadata:
    """
    Complete metadata record for a stored source.

    All fields marked as required MUST be populated before storage.
    Missing required fields = storage NOT permitted.
    """

    # ==========================================================================
    # IDENTIFICATION (all required)
    # ==========================================================================

    source_id: str
    # Unique identifier, format: {authority}_{year}_{sequence}
    # Example: "STATUTORY_LAW_2024_001"

    authority: SourceAuthority
    # Classification level - determines storage rules

    title: str
    # Full title as published
    # Example: "Unternehmensgesetzbuch (UGB) - § 238 Anteilsbesitz"

    # ==========================================================================
    # BIBLIOGRAPHIC DATA (conditional requirements)
    # ==========================================================================

    author: Optional[str] = None
    # Required for: ACADEMIC_COMMENTARY, PRACTICE_NOTE
    # Not applicable for: STATUTORY_LAW

    publisher: Optional[str] = None
    # Required for: ACADEMIC_COMMENTARY, CHAMBER_PUBLICATION
    # Example: "Verlag Österreich" or "IWP"

    publication_date: Optional[date] = None
    # Required for all except TOOL_DERIVED
    # Date of original publication

    edition: Optional[str] = None
    # Required for: ACADEMIC_COMMENTARY
    # Example: "4. Auflage"

    isbn_issn: Optional[str] = None
    # If available

    url: Optional[str] = None
    # For online sources

    # ==========================================================================
    # LEGAL REFERENCE (for statutory sources)
    # ==========================================================================

    legal_reference: Optional[str] = None
    # Required for: STATUTORY_LAW, OFFICIAL_GUIDANCE
    # Example: "§ 238 Abs 1 Z 2 UGB"

    bgbl_reference: Optional[str] = None
    # For Austrian federal law
    # Example: "BGBl. I Nr. 120/2005"

    effective_date: Optional[date] = None
    # When the law/regulation became effective

    # ==========================================================================
    # RETRIEVAL DOCUMENTATION (required for external sources)
    # ==========================================================================

    retrieval_date: date = field(default_factory=date.today)
    # When content was retrieved

    retrieval_url: Optional[str] = None
    # URL used for retrieval (may differ from canonical URL)

    retrieval_method: Literal["manual", "api", "scrape", "archive"] = "manual"
    # How content was obtained

    # ==========================================================================
    # CONTENT DESCRIPTION
    # ==========================================================================

    content_summary: str = ""
    # Brief description of what the source contains
    # Required for all sources

    content_word_count: int = 0
    # Word count of stored content (not original)

    content_type: Literal["full_text", "excerpt", "summary", "metadata_only"] = "metadata_only"
    # What is actually stored

    excerpt_pages: Optional[str] = None
    # If excerpt: "pp. 45-52" or "Rz. 123-145"

    # ==========================================================================
    # STORAGE COMPLIANCE
    # ==========================================================================

    storage_permission: StoragePermission = StoragePermission.METADATA_ONLY
    # What is permitted to be stored

    storage_legal_basis: str = ""
    # Legal justification for storage
    # Example: "§ 7 UrhG (amtliche Werke)" or "§ 42f UrhG (Zitatrecht)"

    copyright_status: Literal["public_domain", "licensed", "fair_use", "restricted"] = "restricted"
    # Default to most restrictive

    # ==========================================================================
    # VERIFICATION
    # ==========================================================================

    verified_by: Optional[str] = None
    # Who verified the content accuracy

    verification_date: Optional[date] = None
    # When verification was performed

    verification_method: Optional[str] = None
    # How verification was performed
    # Example: "Abgleich mit RIS-Datenbank"

    # ==========================================================================
    # INTERNAL TRACKING
    # ==========================================================================

    created_at: datetime = field(default_factory=datetime.now)
    # When this metadata record was created

    updated_at: datetime = field(default_factory=datetime.now)
    # Last update to metadata

    content_hash: Optional[str] = None
    # SHA-256 hash of stored content for integrity verification

    linked_rules: list[str] = field(default_factory=list)
    # Rule IDs that reference this source
    # Example: ["UGB_238_1_Z2_ANTEILSBESITZ"]

    superseded_by: Optional[str] = None
    # If this source has been replaced by a newer version

    notes: str = ""
    # Internal notes about this source


def create_source_metadata(
    source_id: str,
    authority: SourceAuthority,
    title: str,
    **kwargs
) -> SourceMetadata:
    """
    Create a new source metadata record with validation.

    Raises ValueError if required fields for the authority level are missing.
    """
    metadata = SourceMetadata(
        source_id=source_id,
        authority=authority,
        title=title,
        **kwargs
    )

    # Validate completeness
    is_valid, errors = validate_metadata_completeness(metadata)
    if not is_valid:
        raise ValueError(f"Incomplete metadata: {'; '.join(errors)}")

    return metadata


def validate_metadata_completeness(metadata: SourceMetadata) -> tuple[bool, list[str]]:
    """
    Validate that all required fields for the authority level are present.

    Returns: (is_complete, list_of_errors)
    """
    errors = []

    # Universal requirements
    if not metadata.source_id:
        errors.append("source_id is required")
    if not metadata.title:
        errors.append("title is required")
    if not metadata.content_summary:
        errors.append("content_summary is required")

    # Authority-specific requirements
    if metadata.authority == SourceAuthority.STATUTORY_LAW:
        if not metadata.legal_reference:
            errors.append("legal_reference required for STATUTORY_LAW")
        if not metadata.bgbl_reference and not metadata.effective_date:
            errors.append("bgbl_reference or effective_date required for STATUTORY_LAW")

    elif metadata.authority == SourceAuthority.OFFICIAL_GUIDANCE:
        if not metadata.publisher:
            errors.append("publisher required for OFFICIAL_GUIDANCE")
        if not metadata.publication_date:
            errors.append("publication_date required for OFFICIAL_GUIDANCE")

    elif metadata.authority == SourceAuthority.CHAMBER_PUBLICATION:
        if not metadata.publisher:
            errors.append("publisher required for CHAMBER_PUBLICATION")
        if not metadata.publication_date:
            errors.append("publication_date required for CHAMBER_PUBLICATION")

    elif metadata.authority == SourceAuthority.ACADEMIC_COMMENTARY:
        if not metadata.author:
            errors.append("author required for ACADEMIC_COMMENTARY")
        if not metadata.publisher:
            errors.append("publisher required for ACADEMIC_COMMENTARY")
        if not metadata.edition:
            errors.append("edition required for ACADEMIC_COMMENTARY")

    elif metadata.authority == SourceAuthority.PRACTICE_NOTE:
        if not metadata.author or not metadata.publisher:
            errors.append("author and publisher required for PRACTICE_NOTE")

    elif metadata.authority == SourceAuthority.UNVERIFIED:
        errors.append("UNVERIFIED sources may not be stored")

    # Retrieval date requirement
    if metadata.authority != SourceAuthority.TOOL_DERIVED:
        if not metadata.retrieval_date:
            errors.append("retrieval_date required for external sources")

    return len(errors) == 0, errors


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content for integrity verification."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def metadata_to_dict(metadata: SourceMetadata) -> dict:
    """Convert metadata to dictionary for JSON serialization."""
    result = {}
    for key, value in metadata.__dict__.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, SourceAuthority):
            result[key] = value.value
        elif isinstance(value, StoragePermission):
            result[key] = value.value
        else:
            result[key] = value
    return result


def metadata_from_dict(data: dict) -> SourceMetadata:
    """Reconstruct metadata from dictionary."""
    # Convert string dates back to date objects
    date_fields = ["publication_date", "effective_date", "retrieval_date", "verification_date"]
    for field_name in date_fields:
        if data.get(field_name):
            data[field_name] = date.fromisoformat(data[field_name])

    datetime_fields = ["created_at", "updated_at"]
    for field_name in datetime_fields:
        if data.get(field_name):
            data[field_name] = datetime.fromisoformat(data[field_name])

    # Convert enums
    if data.get("authority"):
        data["authority"] = SourceAuthority(data["authority"])
    if data.get("storage_permission"):
        data["storage_permission"] = StoragePermission(data["storage_permission"])

    return SourceMetadata(**data)
