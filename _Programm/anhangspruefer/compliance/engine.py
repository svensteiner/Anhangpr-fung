"""Core review engine orchestrating the review process."""

from pathlib import Path
from datetime import datetime
from typing import Optional

from ..models.document import Document
from ..models.checklist import Checklist
from ..models.finding import ReviewResult
from ..models.enums import DocumentType
from ..parsers.pdf_parser import PDFParser
from ..parsers.rtf_parser import RTFParser
from ..parsers.section_detector import SectionDetector
from .knowledge.checklist_loader import ChecklistLoader
from .knowledge.requirement_matcher import RequirementMatcher
from .evaluator import ComplianceEvaluator
from .evidence import EvidenceExtractor
from ..config import Config
from ..utils.logging_config import get_logger, setup_logging
from .. import __version__, DISCLAIMER

logger = get_logger("engine")


class ReviewEngine:
    """
    Main engine for reviewing notes to financial statements.

    Orchestrates the document parsing, requirement matching,
    compliance evaluation, and evidence extraction processes.

    IMPORTANT DISCLAIMER:
    This tool provides audit SUPPORT functionality only. It does NOT
    perform a UGB-compliant audit. All assessments are preliminary
    and require validation by a qualified auditor.

    Usage:
        engine = ReviewEngine()
        result = engine.review(
            notes_path="Anhang_2024.pdf",
            checklist_path="checklist.json"  # optional
        )
        engine.print_summary(result)
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the review engine.

        Args:
            config: Optional configuration object
        """
        self.config = config or Config.default()

        # Initialize components
        self.pdf_parser = PDFParser()
        self.rtf_parser = RTFParser()
        self.section_detector = SectionDetector()
        self.checklist_loader = ChecklistLoader()
        self.requirement_matcher = RequirementMatcher()
        self.evaluator = ComplianceEvaluator()
        self.evidence_extractor = EvidenceExtractor()

        logger.info(f"ReviewEngine initialized (version {__version__})")

    def review(
        self,
        notes_path: str | Path,
        checklist_path: Optional[str | Path] = None,
        ugb_source_path: Optional[str | Path] = None,
        checklist=None,
    ) -> ReviewResult:
        """Alte Keyword-Prüfung – absichtlich tot. Nur noch review_checklist."""
        raise RuntimeError(
            "Die alte Keyword-Prüfung ist abgeschaltet. "
            "Bitte Starten.bat verwenden. Modus 3 braucht GmbH/AG und "
            "klein/mittel/groß – sonst startet nichts, kein stilles unbekannt."
        )

    def _parse_document(self, file_path: Path) -> Document:
        """Parse a document based on its file type."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return self.pdf_parser.parse(file_path)
        elif suffix == ".rtf":
            return self.rtf_parser.parse(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def print_summary(self, result: ReviewResult) -> None:
        """Print a summary of the review results to console."""
        print("\n" + "=" * 70)
        print("PRÜFUNGSZUSAMMENFASSUNG / REVIEW SUMMARY")
        print("=" * 70)
        print(f"Dokument: {result.document_name}")
        print(f"Checkliste: {result.checklist_name}")
        print(f"Zeitstempel: {result.review_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 70)

        stats = result.summary_statistics
        print(f"Geprüfte Punkte: {stats.get('total_items', 0)}")

        if 'status_counts' in stats:
            print("\nStatus-Verteilung:")
            for status, count in stats['status_counts'].items():
                print(f"  {status}: {count}")

        print(f"\nPunkte mit Prüferbedarf: {stats.get('items_requiring_review', 0)}")
        print("=" * 70)

        print("\nHINWEIS: Alle Bewertungen sind vorläufig und erfordern")
        print("die Validierung durch einen qualifizierten Wirtschaftsprüfer.")

    def get_critical_findings(self, result: ReviewResult) -> list:
        """Get findings requiring immediate attention."""
        return result.get_critical_findings()

    def validate_inputs(
        self,
        notes_path: str | Path,
        checklist_path: Optional[str | Path] = None
    ) -> dict:
        """
        Validate input files before processing.

        Returns dict with validation results.
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        notes_path = Path(notes_path)
        if not notes_path.exists():
            validation["valid"] = False
            validation["errors"].append(f"Notes file not found: {notes_path}")

        if checklist_path:
            checklist_path = Path(checklist_path)
            if not checklist_path.exists():
                validation["valid"] = False
                validation["errors"].append(
                    f"Checklist file not found: {checklist_path}"
                )

        return validation
