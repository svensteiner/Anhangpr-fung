"""
Source-Governed Knowledge Management System.

This module provides audit-proof management of knowledge sources used by the
Anhangsprüfer tool. All interpretations, guidance, and derived rules must be
traceable to classified, properly stored sources.

Key Principle: The tool may never claim authority beyond its cited sources.
"""

from .classification import (
    SourceAuthority,
    StoragePermission,
    CitationRequirement,
    SourceClassification,
    SOURCE_CLASSIFICATIONS,
    get_classification,
    validate_storage_permission,
)

from .metadata import (
    SourceMetadata,
    create_source_metadata,
    validate_metadata_completeness,
)

from .storage import (
    SourceStorageManager,
    STORAGE_ROOT,
    get_storage_path,
)

from .registry import (
    SourceRegistry,
    SourceReference,
    link_source_to_rule,
)

from .citation import (
    CitationGenerator,
    format_citation,
    format_caveat,
)

__all__ = [
    # Classification
    "SourceAuthority",
    "StoragePermission",
    "CitationRequirement",
    "SourceClassification",
    "SOURCE_CLASSIFICATIONS",
    "get_classification",
    "validate_storage_permission",
    # Metadata
    "SourceMetadata",
    "create_source_metadata",
    "validate_metadata_completeness",
    # Storage
    "SourceStorageManager",
    "STORAGE_ROOT",
    "get_storage_path",
    # Registry
    "SourceRegistry",
    "SourceReference",
    "link_source_to_rule",
    # Citation
    "CitationGenerator",
    "format_citation",
    "format_caveat",
]
