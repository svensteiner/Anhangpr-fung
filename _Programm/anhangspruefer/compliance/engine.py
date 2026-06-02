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
        ugb_source_path: Optional[str | Path] = None
    ) -> ReviewResult:
        """
        Perform a review of the notes document.

        Args:
            notes_path: Path to the notes document (PDF/DOCX)
            checklist_path: Optional path to checklist JSON file
            ugb_source_path: Optional path to UGB source file

        Returns:
            ReviewResult containing all findings

        Raises:
            FileNotFoundError: If input files not found
            ParseError: If document parsing fails
        """
        print(DISCLAIMER)

        notes_path = Path(notes_path)
        logger.info(f"Starting review of: {notes_path.name}")

        # Step 1: Parse the notes document
        logger.info("Parsing notes document...")
        notes_document = self._parse_document(notes_path)

        # Step 2: Detect sections
        logger.info("Detecting document sections...")
        notes_document.sections = self.section_detector.detect_sections(
            notes_document
        )
        logger.info(f"Detected {len(notes_document.sections)} sections")

        # Step 3: Load checklist
        logger.info("Loading checklist...")
        if checklist_path:
            checklist = self.checklist_loader.load_from_json(Path(checklist_path))
        else:
            checklist = self.checklist_loader.load_default_checklist()
        logger.info(f"Checklist loaded: {len(checklist.items)} items")

        # Step 4: Load UGB source if provided
        if ugb_source_path:
            logger.info("Loading UGB source...")
            ugb_doc = self._parse_document(Path(ugb_source_path))
            # Could enhance matching with actual UGB text here

        # Step 5: Match requirements
        logger.info("Matching requirements to document content...")
        match_results = self.requirement_matcher.match_all(
            checklist, notes_document
        )

        # Step 6: Evaluate each checklist item
        logger.info("Evaluating compliance...")
        result = ReviewResult(
            document_name=notes_path.name,
            checklist_name=checklist.name,
            review_timestamp=datetime.now(),
            tool_version=__version__,
        )

        for item in checklist.items:
            match_result = match_results.get(item.item_id)
            if not match_result:
                continue

            # Extract evidence
            evidence = self.evidence_extractor.extract_evidence(
                match_result, notes_document, item
            )

            # Evaluate
            finding = self.evaluator.evaluate(item, match_result, evidence)
            result.add_finding(finding)

        logger.info(
            f"Review complete: {len(result.findings)} items evaluated"
        )
        logger.info(
            f"Summary: {result.summary_statistics}"
        )

        return result

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
