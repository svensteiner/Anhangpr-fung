"""
Source Storage Management.

Defines the local folder structure and manages storage operations
for all source materials used by the Anhangsprüfer tool.

Folder Structure:
    sources/
    ├── ugb/                      # Statutory law (UGB full texts)
    │   └── paragraphs/           # Individual sections
    ├── official_guidance/        # FMA, BMF publications
    │   ├── fma/
    │   └── bmf/
    ├── professional_guidance/    # KSW, IWP publications
    │   ├── ksw/
    │   └── iwp/
    ├── commentaries/             # Academic commentaries (excerpts only)
    │   ├── doralt/
    │   ├── nowotny/
    │   └── other/
    ├── practice_notes/           # Big 4 and other practice materials
    │   └── summaries/
    ├── tool_derived/             # Tool's own interpretations
    │   ├── rules/
    │   └── mappings/
    └── metadata/                 # JSON metadata files
        └── registry.json
"""

from pathlib import Path
from datetime import date
import json
import shutil
from typing import Optional

from .classification import (
    SourceAuthority,
    StoragePermission,
    get_classification,
    validate_storage_permission,
)
from .metadata import (
    SourceMetadata,
    metadata_to_dict,
    metadata_from_dict,
    compute_content_hash,
)


# =============================================================================
# STORAGE ROOT CONFIGURATION
# =============================================================================

# Default storage root - can be overridden via config
STORAGE_ROOT = Path(r"C:\automatisierungen\Anhangsprüfer\sources")

# Subfolder structure
FOLDER_STRUCTURE = {
    SourceAuthority.STATUTORY_LAW: "ugb/paragraphs",
    SourceAuthority.OFFICIAL_GUIDANCE: "official_guidance",
    SourceAuthority.CHAMBER_PUBLICATION: "professional_guidance",
    SourceAuthority.ACADEMIC_COMMENTARY: "commentaries",
    SourceAuthority.PRACTICE_NOTE: "practice_notes/summaries",
    SourceAuthority.TOOL_DERIVED: "tool_derived",
    SourceAuthority.UNVERIFIED: None,  # Not permitted
}

# Publisher-specific subfolders
PUBLISHER_FOLDERS = {
    "FMA": "official_guidance/fma",
    "BMF": "official_guidance/bmf",
    "KSW": "professional_guidance/ksw",
    "IWP": "professional_guidance/iwp",
    "Doralt": "commentaries/doralt",
    "Nowotny": "commentaries/nowotny",
}


def get_storage_path(
    authority: SourceAuthority,
    publisher: Optional[str] = None
) -> Optional[Path]:
    """
    Get the appropriate storage path for a source type.

    Returns None if storage is not permitted.
    """
    base_folder = FOLDER_STRUCTURE.get(authority)
    if base_folder is None:
        return None

    # Check for publisher-specific subfolder
    if publisher and publisher in PUBLISHER_FOLDERS:
        return STORAGE_ROOT / PUBLISHER_FOLDERS[publisher]

    return STORAGE_ROOT / base_folder


def initialize_storage_structure() -> None:
    """Create the complete folder structure if it doesn't exist."""
    folders = [
        "ugb/paragraphs",
        "official_guidance/fma",
        "official_guidance/bmf",
        "professional_guidance/ksw",
        "professional_guidance/iwp",
        "commentaries/doralt",
        "commentaries/nowotny",
        "commentaries/other",
        "practice_notes/summaries",
        "tool_derived/rules",
        "tool_derived/mappings",
        "metadata",
    ]

    for folder in folders:
        path = STORAGE_ROOT / folder
        path.mkdir(parents=True, exist_ok=True)

    # Create registry file if not exists
    registry_path = STORAGE_ROOT / "metadata" / "registry.json"
    if not registry_path.exists():
        registry_path.write_text(json.dumps({
            "version": "1.0",
            "created": date.today().isoformat(),
            "sources": {}
        }, indent=2, ensure_ascii=False), encoding="utf-8")


class SourceStorageManager:
    """
    Manages storage of source materials with strict compliance checking.

    NEVER stores content that exceeds permitted limits.
    ALWAYS creates metadata for stored content.
    """

    def __init__(self, storage_root: Optional[Path] = None):
        self.root = storage_root or STORAGE_ROOT
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        """Ensure folder structure exists."""
        if not self.root.exists():
            initialize_storage_structure()

    def can_store(
        self,
        authority: SourceAuthority,
        content_word_count: int
    ) -> tuple[bool, str]:
        """
        Check if content may be stored for this source type.

        Returns: (is_permitted, reason)
        """
        return validate_storage_permission(authority, content_word_count)

    def store_source(
        self,
        metadata: SourceMetadata,
        content: str,
        force: bool = False
    ) -> tuple[bool, str, Optional[Path]]:
        """
        Store source content with full compliance checking.

        Args:
            metadata: Complete metadata record
            content: Content to store
            force: If True, skip word count validation (use with caution)

        Returns: (success, message, stored_path)

        IMPORTANT: This method WILL NOT store content that violates
        storage permissions unless force=True.
        """
        # Validate storage permission
        word_count = len(content.split())

        if not force:
            can_store, reason = self.can_store(metadata.authority, word_count)
            if not can_store:
                return False, f"Speicherung nicht zulässig: {reason}", None

        # Get storage path
        storage_path = get_storage_path(metadata.authority, metadata.publisher)
        if storage_path is None:
            return False, "Kein Speicherort für diese Quellenart definiert", None

        # Ensure directory exists
        storage_path.mkdir(parents=True, exist_ok=True)

        # Create filename from source_id
        safe_id = metadata.source_id.replace("/", "_").replace("\\", "_")
        content_file = storage_path / f"{safe_id}.txt"
        metadata_file = self.root / "metadata" / f"{safe_id}.json"

        # Compute content hash
        metadata.content_hash = compute_content_hash(content)
        metadata.content_word_count = word_count

        # Determine content type based on what we're storing
        classification = get_classification(metadata.authority)
        if classification.max_excerpt_words is None:
            metadata.content_type = "full_text"
        elif word_count <= 100:
            metadata.content_type = "excerpt"
        else:
            metadata.content_type = "summary"

        # Write content file
        content_file.write_text(content, encoding="utf-8")

        # Write metadata file
        metadata_dict = metadata_to_dict(metadata)
        metadata_file.write_text(
            json.dumps(metadata_dict, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Update registry
        self._update_registry(metadata)

        return True, "Quelle erfolgreich gespeichert", content_file

    def store_metadata_only(
        self,
        metadata: SourceMetadata
    ) -> tuple[bool, str, Path]:
        """
        Store only metadata without content.

        Use this for sources where content storage is not permitted
        but reference tracking is still needed.
        """
        metadata.content_type = "metadata_only"
        metadata.content_word_count = 0
        metadata.content_hash = None

        # Create metadata file
        safe_id = metadata.source_id.replace("/", "_").replace("\\", "_")
        metadata_file = self.root / "metadata" / f"{safe_id}.json"

        metadata_dict = metadata_to_dict(metadata)
        metadata_file.write_text(
            json.dumps(metadata_dict, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # Update registry
        self._update_registry(metadata)

        return True, "Metadaten gespeichert (ohne Inhalt)", metadata_file

    def _update_registry(self, metadata: SourceMetadata) -> None:
        """Update the central registry with this source."""
        registry_path = self.root / "metadata" / "registry.json"

        if registry_path.exists():
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        else:
            registry = {"version": "1.0", "sources": {}}

        registry["sources"][metadata.source_id] = {
            "title": metadata.title,
            "authority": metadata.authority.value,
            "retrieval_date": metadata.retrieval_date.isoformat() if metadata.retrieval_date else None,
            "linked_rules": metadata.linked_rules,
        }
        registry["last_updated"] = date.today().isoformat()

        registry_path.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get_source_metadata(self, source_id: str) -> Optional[SourceMetadata]:
        """Retrieve metadata for a stored source."""
        safe_id = source_id.replace("/", "_").replace("\\", "_")
        metadata_file = self.root / "metadata" / f"{safe_id}.json"

        if not metadata_file.exists():
            return None

        data = json.loads(metadata_file.read_text(encoding="utf-8"))
        return metadata_from_dict(data)

    def get_source_content(self, source_id: str) -> Optional[str]:
        """Retrieve stored content for a source."""
        metadata = self.get_source_metadata(source_id)
        if metadata is None:
            return None

        storage_path = get_storage_path(metadata.authority, metadata.publisher)
        if storage_path is None:
            return None

        safe_id = source_id.replace("/", "_").replace("\\", "_")
        content_file = storage_path / f"{safe_id}.txt"

        if not content_file.exists():
            return None

        return content_file.read_text(encoding="utf-8")

    def list_sources_by_authority(
        self,
        authority: SourceAuthority
    ) -> list[SourceMetadata]:
        """List all stored sources of a given authority level."""
        results = []
        registry_path = self.root / "metadata" / "registry.json"

        if not registry_path.exists():
            return results

        registry = json.loads(registry_path.read_text(encoding="utf-8"))

        for source_id, info in registry.get("sources", {}).items():
            if info.get("authority") == authority.value:
                metadata = self.get_source_metadata(source_id)
                if metadata:
                    results.append(metadata)

        return results

    def verify_integrity(self, source_id: str) -> tuple[bool, str]:
        """
        Verify that stored content matches its recorded hash.

        Returns: (is_valid, message)
        """
        metadata = self.get_source_metadata(source_id)
        if metadata is None:
            return False, "Quelle nicht gefunden"

        if metadata.content_type == "metadata_only":
            return True, "Nur Metadaten gespeichert, keine Inhaltsprüfung erforderlich"

        content = self.get_source_content(source_id)
        if content is None:
            return False, "Inhalt nicht gefunden"

        if metadata.content_hash is None:
            return False, "Kein Hash gespeichert, Integrität nicht prüfbar"

        current_hash = compute_content_hash(content)
        if current_hash != metadata.content_hash:
            return False, f"Hash-Mismatch: Inhalt wurde verändert"

        return True, "Integrität bestätigt"
