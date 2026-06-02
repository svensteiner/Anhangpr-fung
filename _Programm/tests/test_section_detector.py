"""Tests für die heuristische Abschnittserkennung."""

from datetime import datetime
from pathlib import Path

from anhangspruefer.models.document import Document
from anhangspruefer.models.enums import DocumentType, SectionType
from anhangspruefer.parsers.section_detector import SectionDetector


SAMPLE_NOTES = """\
I. Allgemeine Angaben
Die Gesellschaft ist eine Kapitalgesellschaft mit Sitz in Wien. Der Anhang
wurde gemäß § 236 UGB aufgestellt und enthält die nach Gesetz erforderlichen
Angaben.

II. Bilanzierungs- und Bewertungsmethoden
Die Bewertung des Anlagevermögens erfolgt zu fortgeführten Anschaffungskosten.
Abschreibungen werden linear über die betriebsgewöhnliche Nutzungsdauer
vorgenommen. Vorräte werden zu Anschaffungs- oder Herstellungskosten bewertet.

III. Erläuterungen zur Bilanz
Das Anlagevermögen entwickelte sich gemäß beigefügtem Anlagenspiegel.
Die Forderungen aus Lieferungen und Leistungen weisen eine Restlaufzeit
von unter einem Jahr auf.
"""


def _doc():
    return Document(
        file_path=Path("dummy.pdf"),
        document_type=DocumentType.NOTES,
        raw_text=SAMPLE_NOTES,
        parse_timestamp=datetime.now(),
    )


def test_section_detector_finds_roman_headings():
    sd = SectionDetector(config={"min_section_length": 20})
    sections = sd.detect_sections(_doc())
    titles = [s.title for s in sections]
    assert any("Allgemeine Angaben" in t for t in titles)
    assert any("Bilanzierungs" in t for t in titles)
    assert any("Erläuterungen zur Bilanz" in t for t in titles)


def test_section_detector_assigns_types():
    sd = SectionDetector(config={"min_section_length": 20})
    sections = sd.detect_sections(_doc())
    types = {s.section_type for s in sections}
    # Mindestens Bilanzierungspolicies und Bilanz sollten erkannt sein
    assert SectionType.ACCOUNTING_POLICIES in types or \
           SectionType.GENERAL_INFORMATION in types


def test_section_detector_fallback_on_no_headings():
    sd = SectionDetector()
    doc = Document(
        file_path=Path("plain.pdf"),
        document_type=DocumentType.NOTES,
        raw_text="Nur Fließtext ohne irgendeine Überschrift.",
        parse_timestamp=datetime.now(),
    )
    sections = sd.detect_sections(doc)
    assert len(sections) == 1
    assert sections[0].section_id == "main"
