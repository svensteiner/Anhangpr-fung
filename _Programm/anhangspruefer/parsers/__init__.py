"""Document parsers for Anhangsprüfer."""

from .base import BaseParser
from .pdf_parser import PDFParser
from .rtf_parser import RTFParser
from .section_detector import SectionDetector

__all__ = [
    "BaseParser",
    "PDFParser",
    "RTFParser",
    "SectionDetector",
]
