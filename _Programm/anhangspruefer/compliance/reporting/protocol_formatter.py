"""Protocol formatting utilities - Structured audit format."""

from datetime import datetime
from typing import Optional

from ...models.finding import Finding, ReviewResult
from ...models.enums import ComplianceStatus
from ...models.checklist import Checklist, ChecklistItem


class ProtocolFormatter:
    """
    Formats review findings into structured protocol sections.

    Each finding is presented in three clear sections:
    1. PRÜFUNGSHANDLUNG - What was checked
    2. PRÜFUNGSERGEBNIS - The result
    3. BEGRÜNDUNG - The reasoning
    """

    STATUS_DISPLAY = {
        ComplianceStatus.COMPLIANT: ("ENTSPRICHT", "✓"),
        ComplianceStatus.PARTIALLY_COMPLIANT: ("TEILWEISE", "◐"),
        ComplianceStatus.NOT_COMPLIANT: ("NICHT ERFÜLLT", "✗"),
        ComplianceStatus.NOT_ASSESSABLE: ("NICHT BEURTEILBAR", "?"),
        ComplianceStatus.NOT_APPLICABLE: ("NICHT ANWENDBAR", "—"),
        ComplianceStatus.PENDING_REVIEW: ("OFFEN", "○"),
    }

    def format_finding_structured(
        self,
        finding: Finding,
        item: Optional[ChecklistItem],
        number: int
    ) -> str:
        """
        Format a finding in the structured three-part format.
        """
        lines = []

        # Header with number and title
        item_id = item.item_id if item else finding.checklist_item_id
        description = item.description if item else finding.checklist_item_id
        ugb_ref = ", ".join(finding.ugb_references) if finding.ugb_references else "—"

        status_text, status_symbol = self.STATUS_DISPLAY.get(
            finding.effective_status,
            ("UNBEKANNT", "?")
        )

        lines.append(f"### {number}. {description}")
        lines.append("")
        lines.append(f"**Referenz:** {item_id} | **UGB:** {ugb_ref}")
        lines.append("")

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 1: PRÜFUNGSHANDLUNG
        # ═══════════════════════════════════════════════════════════════════
        lines.append("#### Prüfungshandlung")
        lines.append("")

        if item and item.search_keywords:
            keywords_display = ", ".join(item.search_keywords[:5])
            lines.append(f"Automatische Durchsuchung des Anhangs nach Angaben zu: **{keywords_display}**")
        else:
            lines.append(f"Automatische Prüfung auf Vorhandensein der Angabe gemäß {ugb_ref}")

        lines.append("")

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 2: PRÜFUNGSERGEBNIS
        # ═══════════════════════════════════════════════════════════════════
        lines.append("#### Prüfungsergebnis")
        lines.append("")
        lines.append(f"| Status | {status_symbol} **{status_text}** |")
        lines.append("|--------|" + "-" * (len(status_text) + 6) + "|")
        lines.append("")

        # Evidence found
        if finding.evidence:
            lines.append("**Identifizierte Angaben:**")
            lines.append("")
            for ev in finding.evidence:
                lines.append(f"- **{ev.section_title}**")
                if ev.quote:
                    quote = ev.quote[:300] + "..." if len(ev.quote) > 300 else ev.quote
                    lines.append(f'  > "{quote}"')
            lines.append("")

        # Missing elements
        if finding.missing_elements:
            lines.append("**Nicht identifiziert:**")
            lines.append("")
            for elem in finding.missing_elements:
                lines.append(f"- {elem}")
            lines.append("")

        # ═══════════════════════════════════════════════════════════════════
        # SECTION 3: BEGRÜNDUNG
        # ═══════════════════════════════════════════════════════════════════
        lines.append("#### Begründung")
        lines.append("")
        lines.append(finding.technical_reasoning)
        lines.append("")

        # Judgment areas (if any)
        if finding.judgment_areas:
            lines.append("**Bereiche für Prüferbeurteilung:**")
            lines.append("")
            for area in finding.judgment_areas:
                lines.append(f"- {area}")
            lines.append("")

        # ═══════════════════════════════════════════════════════════════════
        # AUDITOR SECTION
        # ═══════════════════════════════════════════════════════════════════
        lines.append("#### Prüfervermerk")
        lines.append("")
        lines.append("| Feld | Eintrag |")
        lines.append("|------|---------|")
        lines.append(f"| Prüferkommentar | {finding.auditor_comment or '_________________'} |")
        lines.append(f"| Finale Beurteilung | ☐ Entspricht ☐ Beanstandung ☐ N/A |")
        lines.append(f"| Geprüft von | _________________ |")
        lines.append(f"| Datum | _________________ |")
        lines.append("")

        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def format_summary_table(self, result: ReviewResult) -> str:
        """Format a compact summary table."""
        lines = []
        lines.append("| Nr. | Prüfungspunkt | Ergebnis | UGB | Prüfer |")
        lines.append("|:---:|---------------|:--------:|-----|:------:|")

        for i, finding in enumerate(result.findings, 1):
            status_text, status_symbol = self.STATUS_DISPLAY.get(
                finding.effective_status, ("?", "?")
            )
            ugb = ", ".join(finding.ugb_references[:2]) if finding.ugb_references else "—"
            reviewed = "☑" if finding.auditor_reviewed else "☐"

            # Truncate description
            desc = finding.checklist_item_id
            if len(desc) > 30:
                desc = desc[:27] + "..."

            lines.append(
                f"| {i} | {desc} | {status_symbol} | {ugb} | {reviewed} |"
            )

        return "\n".join(lines)

    def format_status_summary(self, result: ReviewResult) -> str:
        """Format status summary as visual overview."""
        stats = result.summary_statistics
        total = stats.get("total_items", 0)

        if total == 0:
            return "_Keine Prüfungspunkte_"

        status_counts = stats.get("status_counts", {})
        lines = []

        lines.append("```")
        lines.append("┌─────────────────────────────────────────────────┐")
        lines.append("│           STATUSÜBERSICHT                       │")
        lines.append("├─────────────────────────────────────────────────┤")

        for status in ComplianceStatus:
            count = status_counts.get(status.value, 0)
            if count > 0:
                text, symbol = self.STATUS_DISPLAY.get(status, ("?", "?"))
                bar_length = int(count / total * 30)
                bar = "█" * bar_length + "░" * (30 - bar_length)
                lines.append(f"│ {symbol} {text:20} {bar} {count:2}/{total} │")

        lines.append("└─────────────────────────────────────────────────┘")
        lines.append("```")

        return "\n".join(lines)

    def format_disclaimer(self) -> str:
        """Format the standard disclaimer - compact version."""
        return """---

> **HAFTUNGSAUSSCHLUSS:** Dieses Protokoll dient ausschließlich der
> Prüfungsunterstützung. Es ersetzt NICHT die fachliche Beurteilung durch
> den Wirtschaftsprüfer. Alle Feststellungen sind vorläufig und erfordern
> manuelle Validierung.

---"""
