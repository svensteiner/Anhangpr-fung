"""PDF document parser."""

from pathlib import Path
from typing import Optional
from datetime import datetime

from .base import BaseParser, ParseError
from ..models.document import Document, DocumentSection
from ..models.enums import DocumentType, SectionType
from ..utils.text_processing import clean_extracted_text, normalize_text
from ..utils.logging_config import get_logger

logger = get_logger("pdf_parser")


class PDFParser(BaseParser):
    """
    Parser for PDF documents.

    Uses pypdf for text extraction. For scanned PDFs (image-based),
    OCR would be required (not implemented in this baseline version).
    """

    SUPPORTED_EXTENSIONS = [".pdf"]

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._pypdf_available = self._check_pypdf()

    def _check_pypdf(self) -> bool:
        """Check if pypdf is available."""
        try:
            import pypdf
            return True
        except ImportError:
            logger.warning(
                "pypdf not installed. Install with: pip install pypdf"
            )
            return False

    def parse(self, file_path: Path) -> Document:
        """
        Parse a PDF document.

        Args:
            file_path: Path to the PDF file

        Returns:
            Parsed Document object
        """
        self.validate_file(file_path)

        if not self._pypdf_available:
            raise ParseError(
                "pypdf library not available. Install with: pip install pypdf"
            )

        try:
            raw_text, metadata = self._extract_with_metadata(file_path)
        except Exception as e:
            raise ParseError(f"Failed to parse PDF: {e}") from e

        # Detect document type
        doc_type = self.detect_document_type(file_path, raw_text)

        # Create document
        document = Document(
            file_path=file_path,
            document_type=doc_type,
            raw_text=raw_text,
            metadata=metadata,
            parse_timestamp=datetime.now(),
        )

        logger.info(
            f"Parsed PDF: {file_path.name}, "
            f"{metadata.get('total_pages', '?')} pages, "
            f"{len(raw_text)} characters"
        )

        return document

    def extract_text(self, file_path: Path) -> str:
        """Extract raw text from PDF."""
        self.validate_file(file_path)

        if not self._pypdf_available:
            raise ParseError("pypdf library not available")

        try:
            import pypdf

            text_parts = []
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)

                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            raw_text = "\n\n".join(text_parts)
            return clean_extracted_text(raw_text)

        except Exception as e:
            raise ParseError(f"Failed to extract text from PDF: {e}") from e

    def _extract_with_metadata(self, file_path: Path) -> tuple[str, dict]:
        """
        Extract text and metadata from PDF.

        Returns:
            Tuple of (extracted_text, metadata_dict)
        """
        import pypdf

        metadata = {}
        text_parts = []
        page_texts = []

        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)

            # Extract metadata
            if reader.metadata:
                metadata["title"] = reader.metadata.get("/Title", "")
                metadata["author"] = reader.metadata.get("/Author", "")
                metadata["creation_date"] = reader.metadata.get("/CreationDate", "")

            metadata["total_pages"] = len(reader.pages)

            # Extract text page by page
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                    page_texts.append({
                        "page_number": i + 1,
                        "text": page_text,
                        "char_count": len(page_text),
                    })

        metadata["pages"] = page_texts

        raw_text = "\n\n".join(text_parts)
        cleaned_text = clean_extracted_text(raw_text)

        return cleaned_text, metadata

    def extract_text_by_page(self, file_path: Path) -> list[tuple[int, str]]:
        """
        Extract text from PDF with page numbers.

        Returns:
            List of (page_number, page_text) tuples
        """
        self.validate_file(file_path)

        if not self._pypdf_available:
            raise ParseError("pypdf library not available")

        import pypdf

        pages = []
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    pages.append((i + 1, clean_extracted_text(page_text)))

        return pages
