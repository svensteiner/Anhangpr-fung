"""RTF document parser."""

import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from .base import BaseParser, ParseError
from ..models.document import Document, DocumentSection
from ..models.enums import DocumentType, SectionType
from ..utils.text_processing import normalize_text
from ..utils.logging_config import get_logger

logger = get_logger("rtf_parser")


class RTFParser(BaseParser):
    """
    Parser for RTF (Rich Text Format) documents.

    Used primarily for parsing UGB legal text files.
    Uses a simple RTF-to-text converter that handles common RTF constructs.
    """

    SUPPORTED_EXTENSIONS = [".rtf"]

    def parse(self, file_path: Path) -> Document:
        """
        Parse an RTF document.

        Args:
            file_path: Path to the RTF file

        Returns:
            Parsed Document object
        """
        self.validate_file(file_path)

        try:
            raw_text = self.extract_text(file_path)
        except Exception as e:
            raise ParseError(f"Failed to parse RTF: {e}") from e

        # Detect document type
        doc_type = self.detect_document_type(file_path, raw_text)

        # Create document
        document = Document(
            file_path=file_path,
            document_type=doc_type,
            raw_text=raw_text,
            metadata={"format": "RTF"},
            parse_timestamp=datetime.now(),
        )

        logger.info(
            f"Parsed RTF: {file_path.name}, {len(raw_text)} characters"
        )

        return document

    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from RTF file.

        This is a simplified RTF parser that handles common constructs.
        For complex RTF files, consider using striprtf library.
        """
        self.validate_file(file_path)

        # Try to use striprtf if available
        try:
            from striprtf.striprtf import rtf_to_text

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                rtf_content = f.read()
            return normalize_text(rtf_to_text(rtf_content))

        except ImportError:
            logger.info("striprtf not available, using basic RTF parser")

        # Fallback to basic RTF parsing
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            rtf_content = f.read()

        return normalize_text(self._basic_rtf_to_text(rtf_content))

    def _basic_rtf_to_text(self, rtf: str) -> str:
        """
        Basic RTF to text conversion.

        Handles common RTF constructs but may not work for all files.
        """
        # Remove RTF header
        rtf = re.sub(r"^\{\\rtf1.*?(?=\\)", "", rtf, count=1)

        # Common RTF escape sequences
        replacements = [
            (r"\\par\b", "\n"),           # Paragraph
            (r"\\line\b", "\n"),          # Line break
            (r"\\tab\b", "\t"),           # Tab
            (r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16))),  # Hex chars
            (r"\\u(\d+)\??", lambda m: chr(int(m.group(1)))),  # Unicode
            (r"\\~", "\u00A0"),           # Non-breaking space
            (r"\\_", "\u2011"),           # Non-breaking hyphen
            (r"\\-", "\u00AD"),           # Soft hyphen
            (r"\\bullet\b", "\u2022"),    # Bullet
            (r"\\endash\b", "\u2013"),    # En-dash
            (r"\\emdash\b", "\u2014"),    # Em-dash
            (r"\\lquote\b", "\u2018"),    # Left single quote
            (r"\\rquote\b", "\u2019"),    # Right single quote
            (r"\\ldblquote\b", "\u201C"), # Left double quote
            (r"\\rdblquote\b", "\u201D"), # Right double quote
        ]

        for pattern, replacement in replacements:
            if callable(replacement):
                rtf = re.sub(pattern, replacement, rtf)
            else:
                rtf = re.sub(pattern, replacement, rtf)

        # Remove formatting commands
        rtf = re.sub(r"\\[a-z]+\d*\s?", "", rtf)

        # Remove groups (including font tables, color tables, etc.)
        # This is simplified and may not handle nested groups perfectly
        depth = 0
        result = []
        i = 0
        while i < len(rtf):
            if rtf[i] == "{":
                depth += 1
            elif rtf[i] == "}":
                depth -= 1
            elif depth == 0:
                result.append(rtf[i])
            i += 1

        text = "".join(result)

        # Clean up remaining artifacts
        text = re.sub(r"[{}]", "", text)
        text = re.sub(r"\s+", " ", text)

        # Restore paragraph structure
        text = text.replace(". ", ".\n")

        return text.strip()

    def extract_ugb_paragraphs(self, file_path: Path) -> dict[str, str]:
        """
        Extract UGB paragraphs from the legal text file.

        Returns:
            Dictionary mapping paragraph numbers to their text.
            E.g., {"§ 236": "text...", "§ 237": "text..."}
        """
        text = self.extract_text(file_path)

        paragraphs = {}
        current_para = None
        current_text = []

        # Pattern for UGB paragraph headers
        para_pattern = re.compile(r"^(§\s*\d+[a-z]?)\b", re.MULTILINE)

        lines = text.split("\n")
        for line in lines:
            match = para_pattern.match(line.strip())
            if match:
                # Save previous paragraph
                if current_para:
                    paragraphs[current_para] = "\n".join(current_text).strip()

                # Start new paragraph
                current_para = match.group(1).replace(" ", " ")
                current_text = [line]
            elif current_para:
                current_text.append(line)

        # Save last paragraph
        if current_para:
            paragraphs[current_para] = "\n".join(current_text).strip()

        logger.info(f"Extracted {len(paragraphs)} UGB paragraphs")

        return paragraphs
