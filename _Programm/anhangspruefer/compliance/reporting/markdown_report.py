"""Markdown report generator - Clean structured format."""

from pathlib import Path
from datetime import datetime
from typing import Optional

from ...models.finding import ReviewResult, Finding
from ...models.checklist import Checklist, ChecklistItem
from ...models.enums import ComplianceStatus
from .protocol_formatter import ProtocolFormatter
from ...utils.logging_config import get_logger
from ... import __version__

logger = get_logger("report")


class MarkdownReportGenerator:
    """
    Generates structured Markdown review protocols.

    Format:
    - Header with metadata
    - Executive summary with statistics
    - Overview table
    - Detailed findings (each with: Prüfungshandlung, Prüfungsergebnis, Begründung)
    - Footer with sign-off
    """

    def __init__(
        self,
        checklist: Optional[Checklist] = None,
        config: Optional[dict] = None
    ):
        self.checklist = checklist
        self.config = config or {}
        self.formatter = ProtocolFormatter()

    def generate(
        self,
        result: ReviewResult,
        output_path: Optional[Path] = None
    ) -> str:
        """Generate the complete review protocol."""
        sections = []

        # 1. Header
        sections.append(self._generate_header(result))

        # 2. Disclaimer (short)
        sections.append(self.formatter.format_disclaimer())

        # 3. Executive Summary
        sections.append(self._generate_summary(result))

        # 4. Overview Table
        sections.append(self._generate_overview(result))

        # 5. Detailed Findings
        sections.append(self._generate_findings(result))

        # 6. Footer
        sections.append(self._generate_footer(result))

        report = "\n\n".join(sections)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            logger.info(f"Report saved to: {output_path}")

        return report

    def _generate_header(self, result: ReviewResult) -> str:
        """Generate report header."""
        return f"""# Anhangsprüfungsprotokoll

| | |
|---|---|
| **Dokument** | {result.document_name} |
| **Prüfungsprogramm** | {result.checklist_name} |
| **Erstellt** | {result.review_timestamp.strftime('%d.%m.%Y %H:%M')} |
| **Tool-Version** | {result.tool_version or __version__} |"""

    def _generate_summary(self, result: ReviewResult) -> str:
        """Generate executive summary."""
        stats = result.summary_statistics
        total = stats.get("total_items", 0)
        status_counts = stats.get("status_counts", {})

        # Count by status
        ok = status_counts.get(ComplianceStatus.COMPLIANT.value, 0)
        partial = status_counts.get(ComplianceStatus.PARTIALLY_COMPLIANT.value, 0)
        missing = status_counts.get(ComplianceStatus.NOT_COMPLIANT.value, 0)
        unclear = status_counts.get(ComplianceStatus.NOT_ASSESSABLE.value, 0)

        critical = missing + unclear

        return f"""## Zusammenfassung

| Kategorie | Anzahl |
|-----------|:------:|
| Geprüfte Punkte | **{total}** |
| ✓ Entspricht | {ok} |
| ◐ Teilweise | {partial} |
| ✗ Nicht erfüllt | {missing} |
| ? Nicht beurteilbar | {unclear} |

{"**⚠ " + str(critical) + " kritische Punkte erfordern Prüferbeurteilung**" if critical > 0 else ""}

{self.formatter.format_status_summary(result)}"""

    def _generate_overview(self, result: ReviewResult) -> str:
        """Generate overview table."""
        return f"""## Übersicht

{self.formatter.format_summary_table(result)}

**Legende:** ✓ Entspricht | ◐ Teilweise | ✗ Nicht erfüllt | ? Nicht beurteilbar | ☐ Prüfung offen | ☑ Geprüft"""

    def _generate_findings(self, result: ReviewResult) -> str:
        """Generate detailed findings section."""
        lines = ["## Detaillierte Prüfungsfeststellungen"]
        lines.append("")
        lines.append("Jede Feststellung ist gegliedert in:")
        lines.append("1. **Prüfungshandlung** – Was wurde geprüft?")
        lines.append("2. **Prüfungsergebnis** – Was wurde festgestellt?")
        lines.append("3. **Begründung** – Warum diese Beurteilung?")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, finding in enumerate(result.findings, 1):
            item = None
            if self.checklist:
                item = self.checklist.get_item(finding.checklist_item_id)

            lines.append(self.formatter.format_finding_structured(finding, item, i))

        return "\n".join(lines)

    def _generate_footer(self, result: ReviewResult) -> str:
        """Generate report footer with sign-off section."""
        return f"""## Abschluss und Freigabe

### Gesamtbeurteilung

| | |
|---|---|
| ☐ Keine Beanstandungen | ☐ Beanstandungen (siehe oben) |
| ☐ Nachtrag erforderlich | ☐ Prüfungshemmnis |

### Unterschriften

| Rolle | Name | Datum | Unterschrift |
|-------|------|-------|--------------|
| Erstellt | _Auto-generiert_ | {result.review_timestamp.strftime('%d.%m.%Y')} | — |
| Geprüft | | | |
| Freigegeben | | | |

---

_Generiert mit Anhangsprüfer v{result.tool_version or __version__}_
_Dieses Protokoll dient der Prüfungsunterstützung und ersetzt nicht die fachliche Beurteilung._"""

    def generate_word_compatible(
        self,
        result: ReviewResult,
        output_path: Path
    ) -> None:
        """Generate Word-compatible HTML output."""
        markdown_content = self.generate(result)
        html_content = self._markdown_to_html(markdown_content)

        html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Anhangsprüfungsprotokoll</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
        th {{ background-color: #f5f5f5; font-weight: 600; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 30px; }}
        h3 {{ color: #444; margin-top: 25px; }}
        h4 {{ color: #555; margin-top: 15px; font-size: 1em; }}
        blockquote {{ border-left: 4px solid #007acc; padding-left: 15px; color: #555; margin: 15px 0; background: #f9f9f9; padding: 10px 15px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        hr {{ border: none; border-top: 1px solid #ddd; margin: 20px 0; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

        output_path = output_path.with_suffix(".html")
        output_path.write_text(html_doc, encoding="utf-8")
        logger.info(f"Word-compatible HTML saved to: {output_path}")

    def _markdown_to_html(self, markdown: str) -> str:
        """Basic markdown to HTML conversion."""
        import re

        html = markdown

        # Code blocks
        html = re.sub(r"```(.*?)```", r"<pre><code>\1</code></pre>", html, flags=re.DOTALL)

        # Headers
        html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

        # Italic
        html = re.sub(r"_(.+?)_", r"<em>\1</em>", html)

        # Blockquote
        html = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)

        # Lists
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>", html)

        # Horizontal rules
        html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)

        # Tables - simplified
        def convert_table(match):
            rows = match.group(0).strip().split('\n')
            html_rows = []
            for i, row in enumerate(rows):
                if '---' in row:
                    continue
                cells = [c.strip() for c in row.split('|')[1:-1]]
                tag = 'th' if i == 0 else 'td'
                html_cells = ''.join(f'<{tag}>{c}</{tag}>' for c in cells)
                html_rows.append(f'<tr>{html_cells}</tr>')
            return f'<table>{"".join(html_rows)}</table>'

        html = re.sub(r'(\|.+\|\n)+', convert_table, html)

        # Paragraphs
        html = re.sub(r'\n\n+', '</p><p>', html)
        html = f'<p>{html}</p>'

        return html
