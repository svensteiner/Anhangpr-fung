"""Tests für Datenmodelle."""

from datetime import datetime

from anhangspruefer.models.enums import ComplianceStatus, SectionType
from anhangspruefer.models.checklist import Checklist, ChecklistItem
from anhangspruefer.models.finding import Finding, EvidenceItem, ReviewResult


def test_compliance_status_display_text():
    assert "erfüllt" in ComplianceStatus.COMPLIANT.to_display_text().lower()
    assert ComplianceStatus.NOT_COMPLIANT.value == "NICHT ENTSPRECHEND"


def test_checklist_add_and_lookup():
    cl = Checklist(name="Test", version="2025")
    item = ChecklistItem(
        item_id="A1",
        category="Allgemein",
        description="Bilanzierungsmethoden angeben",
        ugb_references=["§ 236"],
        search_keywords=["Bilanzierung"],
    )
    cl.add_item(item)
    assert cl.get_item("A1") is item
    assert cl.get_items_by_category("Allgemein") == [item]
    assert cl.get_items_for_ugb_reference("§ 236") == [item]
    assert cl.get_mandatory_items() == [item]


def test_checklist_item_search_patterns_include_ugb():
    item = ChecklistItem(
        item_id="X",
        category="Cat",
        description="d",
        ugb_references=["§ 239"],
        search_keywords=["Geschäftsführer"],
    )
    patterns = item.get_search_patterns()
    assert "Geschäftsführer" in patterns
    assert "§ 239" in patterns


def test_finding_effective_status_uses_override():
    f = Finding(
        checklist_item_id="X",
        status=ComplianceStatus.NOT_COMPLIANT,
        ugb_references=["§ 236"],
    )
    assert f.effective_status == ComplianceStatus.NOT_COMPLIANT
    f.auditor_override_status = ComplianceStatus.COMPLIANT
    assert f.effective_status == ComplianceStatus.COMPLIANT


def test_review_result_critical_findings():
    rr = ReviewResult(
        document_name="anhang.pdf",
        checklist_name="cl",
        review_timestamp=datetime.now(),
    )
    rr.add_finding(Finding("a", ComplianceStatus.COMPLIANT, []))
    rr.add_finding(Finding("b", ComplianceStatus.NOT_COMPLIANT, []))
    rr.add_finding(Finding("c", ComplianceStatus.NOT_ASSESSABLE, []))

    crit = rr.get_critical_findings()
    assert len(crit) == 2
    assert rr.summary_statistics["total_items"] == 3


def test_evidence_format_reference_with_page():
    ev = EvidenceItem(
        section_id="s1",
        section_title="Anlagevermögen",
        quote="…",
        page_number=12,
        line_number=3,
    )
    ref = ev.format_reference()
    assert "Anlagevermögen" in ref
    assert "Seite 12" in ref
