"""Finding and review result models."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from .enums import ComplianceStatus


@dataclass
class EvidenceItem:
    """
    Represents evidence found (or not found) in the notes document.
    """
    section_id: str
    section_title: str
    quote: str
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    relevance_score: float = 0.0  # 0.0 to 1.0, for ranking evidence
    is_supporting: bool = True    # True if supports compliance, False if contradicts

    def format_reference(self) -> str:
        """Format evidence as a citation."""
        ref = f"[{self.section_title}]"
        if self.page_number:
            ref += f" (Seite {self.page_number}"
            if self.line_number:
                ref += f", Zeile {self.line_number}"
            ref += ")"
        return ref


@dataclass
class Finding:
    """
    Represents the assessment of a single checklist item.

    IMPORTANT: All findings are preliminary and require auditor validation.
    """
    checklist_item_id: str
    status: ComplianceStatus
    ugb_references: list[str]
    evidence: list[EvidenceItem] = field(default_factory=list)
    missing_elements: list[str] = field(default_factory=list)
    technical_reasoning: str = ""

    # Auditor interaction fields
    auditor_comment: str = ""
    auditor_override_status: Optional[ComplianceStatus] = None
    auditor_reviewed: bool = False
    review_timestamp: Optional[datetime] = None

    # Markers for areas requiring professional judgment
    requires_judgment: bool = True
    judgment_areas: list[str] = field(default_factory=list)

    @property
    def effective_status(self) -> ComplianceStatus:
        """Return the effective status (auditor override if present)."""
        if self.auditor_override_status is not None:
            return self.auditor_override_status
        return self.status

    def add_evidence(self, evidence: EvidenceItem) -> None:
        """Add evidence to the finding."""
        self.evidence.append(evidence)

    def format_evidence_summary(self) -> str:
        """Format all evidence as a readable summary."""
        if not self.evidence:
            return "Keine automatisch identifizierten Nachweise gefunden."

        lines = []
        for i, ev in enumerate(self.evidence, 1):
            prefix = "+" if ev.is_supporting else "-"
            lines.append(f"  {prefix} {ev.format_reference()}")
            if ev.quote:
                # Truncate long quotes
                quote = ev.quote[:200] + "..." if len(ev.quote) > 200 else ev.quote
                lines.append(f'    "{quote}"')
        return "\n".join(lines)


@dataclass
class ReviewResult:
    """
    Complete result of reviewing a notes document against the checklist.
    """
    document_name: str
    checklist_name: str
    review_timestamp: datetime
    findings: list[Finding] = field(default_factory=list)
    summary_statistics: dict = field(default_factory=dict)

    # Review metadata
    tool_version: str = ""
    notes: str = ""

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the review."""
        self.findings.append(finding)
        self._update_statistics()

    def _update_statistics(self) -> None:
        """Update summary statistics."""
        status_counts = {}
        for finding in self.findings:
            status = finding.effective_status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        self.summary_statistics = {
            "total_items": len(self.findings),
            "status_counts": status_counts,
            "items_requiring_review": sum(
                1 for f in self.findings if not f.auditor_reviewed
            ),
            "items_requiring_judgment": sum(
                1 for f in self.findings if f.requires_judgment
            ),
        }

    def get_findings_by_status(self, status: ComplianceStatus) -> list[Finding]:
        """Get all findings with a specific status."""
        return [f for f in self.findings if f.effective_status == status]

    def get_unreviewed_findings(self) -> list[Finding]:
        """Get findings not yet reviewed by auditor."""
        return [f for f in self.findings if not f.auditor_reviewed]

    def get_critical_findings(self) -> list[Finding]:
        """Get findings that are NOT_COMPLIANT or NOT_ASSESSABLE."""
        return [
            f for f in self.findings
            if f.effective_status in (
                ComplianceStatus.NOT_COMPLIANT,
                ComplianceStatus.NOT_ASSESSABLE
            )
        ]
