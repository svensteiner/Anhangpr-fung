"""Base parser interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models.document import Document, DocumentSection
from ..models.enums import DocumentType


class BaseParser(ABC):
    """
    Abstract base class for document parsers.

    All document parsers must implement this interface to ensure
    consistent handling across different file formats.
    """

    SUPPORTED_EXTENSIONS: list[str] = []

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the parser.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    @abstractmethod
    def parse(self, file_path: Path) -> Document:
        """
        Parse a document file.

        Args:
            file_path: Path to the document file

        Returns:
            Parsed Document object

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file format is not supported
            ParseError: If parsing fails
        """
        pass

    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """
        Extract raw text from a document.

        Args:
            file_path: Path to the document file

        Returns:
            Extracted text content
        """
        pass

    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if this parser supports the file format
        """
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def validate_file(self, file_path: Path) -> None:
        """
        Validate that the file exists and is readable.

        Args:
            file_path: Path to the file

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If file is not readable
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

    @staticmethod
    def detect_document_type(file_path: Path, content: str = "") -> DocumentType:
        """
        Detect the type of document based on filename and content.

        Args:
            file_path: Path to the document
            content: Optional document content for analysis

        Returns:
            Detected DocumentType
        """
        filename_lower = file_path.name.lower()

        # Check filename patterns
        if "anhang" in filename_lower:
            return DocumentType.NOTES
        if "ugb" in filename_lower:
            return DocumentType.UGB_SOURCE
        if "checkliste" in filename_lower or "checklist" in filename_lower:
            return DocumentType.CHECKLIST

        # Check content patterns
        if content:
            content_lower = content.lower()
            if "unternehmensgesetzbuch" in content_lower or "ugb" in content_lower:
                if "§ 236" in content or "§ 237" in content:
                    return DocumentType.UGB_SOURCE

        return DocumentType.OTHER


class ParseError(Exception):
    """Exception raised when document parsing fails."""
    pass
