"""Tests für ComplianceEvaluator."""

from anhangspruefer.compliance.evaluator import (
    ComplianceEvaluator,
    EvaluationCriteria,
    EvaluationSummary,
)
from anhangspruefer.compliance.knowledge.requirement_matcher import MatchResult
from anhangspruefer.models.checklist import ChecklistItem
from anhangspruefer.models.enums import ComplianceStatus
from anhangspruefer.models.finding import EvidenceItem, Finding


def _item():
    return ChecklistItem(
        item_id="X1",
        category="Test",
        description="Erläuterungen zu Anlagevermögen",
        ugb_references=["§ 236"],
        search_keywords=["Anlagevermögen"],
    )


def _evidence(n=1):
    return [
        EvidenceItem(
            section_id=f"s{i}",
            section_title="Anlagevermögen",
            quote="Das Anlagevermögen wird gemäß § 236 erläutert.",
            relevance_score=0.9,
        )
        for i in range(n)
    ]


def test_evaluator_high_confidence_yields_compliant():
    ev = ComplianceEvaluator()
    match = MatchResult(
        checklist_item_id="X1",
        matched_sections=[],
        matched_quotes=[],
        ugb_references_found=["§ 236"],
        confidence=0.9,
    )
    finding = ev.evaluate(_item(), match, _evidence(2))
    assert finding.status == ComplianceStatus.COMPLIANT


def test_evaluator_zero_confidence_yields_not_compliant():
    ev = ComplianceEvaluator()
    match = MatchResult(
        checklist_item_id="X1",
        matched_sections=[],
        matched_quotes=[],
        ugb_references_found=[],
        confidence=0.0,
    )
    finding = ev.evaluate(_item(), match, [])
    assert finding.status == ComplianceStatus.NOT_COMPLIANT
    assert finding.requires_judgment is True


def test_evaluator_partial_for_medium_confidence():
    ev = ComplianceEvaluator()
    match = MatchResult(
        checklist_item_id="X1",
        matched_sections=[],
        matched_quotes=[],
        ugb_references_found=[],
        confidence=0.5,
    )
    finding = ev.evaluate(_item(), match, _evidence(1))
    assert finding.status == ComplianceStatus.PARTIALLY_COMPLIANT


def test_evaluation_summary():
    findings = [
        Finding("a", ComplianceStatus.COMPLIANT, []),
        Finding("b", ComplianceStatus.COMPLIANT, []),
        Finding("c", ComplianceStatus.NOT_COMPLIANT, []),
    ]
    summary = EvaluationSummary.summarize(findings)
    assert summary["total"] == 3
    assert summary["compliance_rate"] == 2 / 3
