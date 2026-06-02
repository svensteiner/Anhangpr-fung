"""Tests für den Arbeitnehmer-Evaluator (§ 237 Abs 1 Z 1)."""

from datetime import datetime
from pathlib import Path

from anhangspruefer.compliance.rules.arbeitnehmer_evaluator import (
    ArbeitnehmerEvaluator,
    evaluate_arbeitnehmer,
)
from anhangspruefer.models.document import Document, DocumentSection
from anhangspruefer.models.enums import ComplianceStatus, DocumentType, SectionType


def _doc(text: str, sections: list[DocumentSection] | None = None) -> Document:
    return Document(
        file_path=Path("dummy.pdf"),
        document_type=DocumentType.NOTES,
        raw_text=text,
        sections=sections or [],
        parse_timestamp=datetime.now(),
    )


def test_no_section_yields_not_compliant():
    finding = evaluate_arbeitnehmer(_doc("Bilanz und sonstige Angaben."))
    assert finding.status == ComplianceStatus.NOT_COMPLIANT
    assert "kein personalstand" in finding.missing_elements[0].lower()


def test_complete_disclosure_yields_compliant():
    text = (
        "Personalstand\n"
        "Die durchschnittliche Anzahl der während des Geschäftsjahres "
        "beschäftigten Arbeitnehmer beträgt im Jahresdurchschnitt 142 Personen, "
        "davon 95 Angestellte und 47 Arbeiter (Vorjahr: 138).\n"
    )
    section = DocumentSection(
        section_id="s1",
        title="Personalstand",
        content=text,
        section_type=SectionType.OTHER_DISCLOSURES,
    )
    finding = evaluate_arbeitnehmer(_doc(text, [section]))
    assert finding.status == ComplianceStatus.COMPLIANT
    assert finding.evidence  # Beleg vorhanden


def test_partial_disclosure_yields_partially():
    text = (
        "Mitarbeiter\n"
        "Im Geschäftsjahr waren durchschnittlich 80 Mitarbeiter beschäftigt. "
        "Eine Aufgliederung erfolgt nicht.\n"
    )
    section = DocumentSection(
        section_id="s1",
        title="Mitarbeiter",
        content=text,
        section_type=SectionType.OTHER_DISCLOSURES,
    )
    finding = evaluate_arbeitnehmer(_doc(text, [section]))
    assert finding.status == ComplianceStatus.PARTIALLY_COMPLIANT
    assert any("aufgliederung" in m.lower() for m in finding.missing_elements)


def test_section_without_clear_data_yields_not_assessable():
    text = (
        "Beschäftigte\n"
        "Hinsichtlich der Beschäftigtenstruktur verweisen wir auf die "
        "internen Personalberichte.\n"
    )
    section = DocumentSection(
        section_id="s1",
        title="Beschäftigte",
        content=text,
        section_type=SectionType.OTHER_DISCLOSURES,
    )
    finding = evaluate_arbeitnehmer(_doc(text, [section]))
    assert finding.status == ComplianceStatus.NOT_ASSESSABLE


def test_evaluator_uses_section_title_in_evidence():
    text = (
        "Personalstand: Im Jahresdurchschnitt beschäftigte die Gesellschaft "
        "55 Angestellte und 12 Arbeiter."
    )
    section = DocumentSection(
        section_id="s1",
        title="Personalstand",
        content=text,
        section_type=SectionType.OTHER_DISCLOSURES,
    )
    ev = ArbeitnehmerEvaluator().evaluate(_doc(text, [section]))
    assert ev.evidence[0].section_title == "Personalstand"
    assert ev.ugb_references == ["§ 237 Abs 1 Z 1 UGB"]
