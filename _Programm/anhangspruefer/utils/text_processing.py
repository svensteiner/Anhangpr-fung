"""Text processing utilities."""

import re
import unicodedata
from typing import Optional


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent processing.

    - Normalize Unicode
    - Remove excessive whitespace
    - Standardize line endings
    """
    # Normalize Unicode to NFC form
    text = unicodedata.normalize("NFC", text)

    # Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive whitespace while preserving paragraph structure
    lines = []
    for line in text.split("\n"):
        # Collapse multiple spaces to single space
        line = re.sub(r"[ \t]+", " ", line)
        lines.append(line.strip())

    return "\n".join(lines)


def fuzzy_match(text: str, pattern: str, threshold: float = 0.75) -> tuple[bool, float]:
    """
    Perform fuzzy text matching.

    Returns (is_match, similarity_score).

    NOTE: This is a simplified implementation using character-level
    similarity. For production use, consider using dedicated libraries
    like rapidfuzz or python-Levenshtein.
    """
    text_lower = text.lower()
    pattern_lower = pattern.lower()

    # Exact match
    if pattern_lower in text_lower:
        return True, 1.0

    # Word-by-word matching
    pattern_words = set(pattern_lower.split())
    text_words = set(text_lower.split())

    if not pattern_words:
        return False, 0.0

    # Calculate Jaccard similarity for word overlap
    intersection = pattern_words & text_words
    union = pattern_words | text_words

    if not union:
        return False, 0.0

    similarity = len(intersection) / len(union)

    return similarity >= threshold, similarity


def extract_paragraphs(text: str) -> list[str]:
    """
    Extract paragraphs from text.

    Paragraphs are separated by blank lines or specific patterns.
    """
    # Split by double newlines (blank lines)
    raw_paragraphs = re.split(r"\n\s*\n", text)

    paragraphs = []
    for para in raw_paragraphs:
        para = para.strip()
        if para and len(para) > 10:  # Ignore very short fragments
            paragraphs.append(para)

    return paragraphs


def extract_ugb_reference(text: str) -> list[str]:
    """
    Extract UGB paragraph references from text.

    Matches patterns like:
    - § 236
    - §§ 236 ff
    - § 236 Abs 1
    - § 236 Abs 1 Z 2
    """
    patterns = [
        r"§§?\s*\d+(?:\s*(?:ff|Abs|Z|lit)\s*\d*)*",
        r"Paragraph\s*\d+",
    ]

    references = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        references.extend(matches)

    # Normalize references
    normalized = []
    for ref in references:
        ref = re.sub(r"\s+", " ", ref.strip())
        if ref not in normalized:
            normalized.append(ref)

    return normalized


def extract_amounts(text: str) -> list[tuple[str, Optional[float]]]:
    """
    Extract monetary amounts from text.

    Returns list of (original_text, parsed_value) tuples.

    NOTE: This is a simplified implementation. Currency parsing
    is complex and may require domain-specific adjustments.
    """
    # Pattern for German number format (1.234.567,89)
    pattern = r"(?:EUR|€|TEUR|Mio\.?\s*€?)?\s*([\d.,]+)\s*(?:EUR|€|TEUR|Mio\.?\s*€?)?"

    amounts = []
    for match in re.finditer(pattern, text):
        original = match.group(0).strip()
        number_str = match.group(1)

        try:
            # Convert German format to float
            # Replace thousand separators, then decimal comma
            cleaned = number_str.replace(".", "").replace(",", ".")
            value = float(cleaned)
            amounts.append((original, value))
        except ValueError:
            amounts.append((original, None))

    return amounts


def find_section_boundaries(text: str) -> list[tuple[int, str]]:
    """
    Find potential section boundaries in text.

    Returns list of (line_number, heading_text) tuples.
    """
    boundaries = []

    lines = text.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Check for numbered headings (e.g., "1.", "1.1", "A.", "A.1")
        if re.match(r"^[\dA-Z]+[.\)]\s+\w", line):
            boundaries.append((i, line))
            continue

        # Check for all-caps headings (common in legal documents)
        if line.isupper() and len(line) > 5 and len(line) < 100:
            boundaries.append((i, line))
            continue

        # Check for headings followed by colon
        if line.endswith(":") and len(line) > 10 and len(line) < 80:
            boundaries.append((i, line))
            continue

    return boundaries


def clean_extracted_text(text: str) -> str:
    """
    Clean text extracted from PDF/documents.

    Handles common extraction artifacts.
    """
    # Remove page numbers (common patterns)
    text = re.sub(r"\n\s*Seite\s+\d+\s*(?:von\s+\d+)?\s*\n", "\n", text)
    text = re.sub(r"\n\s*-\s*\d+\s*-\s*\n", "\n", text)

    # Remove header/footer repetitions (simplified)
    # This would need to be enhanced based on actual document patterns

    # Remove hyphenation artifacts
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Normalize whitespace
    text = normalize_text(text)

    return text
