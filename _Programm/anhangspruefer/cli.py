"""Command-line interface for Anhangsprüfer."""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from . import __version__, DISCLAIMER
from .compliance.engine import ReviewEngine
from .compliance.reporting.markdown_report import MarkdownReportGenerator
from .compliance.knowledge.checklist_loader import ChecklistLoader
from .vorjahresvergleich import (
    extract_label_value_pairs,
    compare_anhaenge,
    generate_report as generate_yoy_report,
    generate_excel as generate_yoy_excel,
)
from .config import Config
from .utils.logging_config import setup_logging


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="anhangspruefer",
        description="""
Anhangsprüfer - Prüfungsunterstützung für den Anhang zum Jahresabschluss

WICHTIG: Dieses Tool dient ausschließlich der Prüfungsunterstützung
und ersetzt NICHT die fachliche Beurteilung durch einen Wirtschaftsprüfer.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"Anhangsprüfer {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # Review command
    review_parser = subparsers.add_parser(
        "review",
        help="Anhang-Dokument prüfen",
    )
    review_parser.add_argument(
        "notes_file",
        type=Path,
        help="Pfad zum Anhang-Dokument (PDF)",
    )
    review_parser.add_argument(
        "-c", "--checklist",
        type=Path,
        help="Pfad zur Checklisten-Datei (JSON)",
    )
    review_parser.add_argument(
        "-u", "--ugb-source",
        type=Path,
        help="Pfad zur UGB-Quelldatei (RTF)",
    )
    review_parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Ausgabepfad für das Prüfungsprotokoll",
    )
    review_parser.add_argument(
        "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Ausgabeformat (Standard: markdown)",
    )
    review_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Ausführliche Ausgabe",
    )

    # Init command - create default checklist
    init_parser = subparsers.add_parser(
        "init",
        help="Projekt initialisieren / Standard-Checkliste erstellen",
    )
    init_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("checklist.json"),
        help="Ausgabepfad für die Checkliste",
    )

    # Parse checklist from PDF
    parse_parser = subparsers.add_parser(
        "parse-checklist",
        help="Checkliste aus PDF extrahieren (experimentell)",
    )
    parse_parser.add_argument(
        "pdf_file",
        type=Path,
        help="Pfad zur Checklisten-PDF",
    )
    parse_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("parsed_checklist.json"),
        help="Ausgabepfad",
    )

    # ----------------------------------------------------------------
    # ZIEL 2: Vorjahresvergleich
    # ----------------------------------------------------------------
    compare_parser = subparsers.add_parser(
        "compare-vorjahr",
        help="Vorjahreszahlen zwischen zwei Anhang-PDFs vergleichen (Ziel 2)",
    )
    compare_parser.add_argument(
        "current_pdf",
        type=Path,
        help="Anhang des aktuellen Berichtsjahres (z.B. Anhang 2025)",
    )
    compare_parser.add_argument(
        "prior_pdf",
        type=Path,
        help="Anhang des Vorjahres (z.B. Anhang 2024)",
    )
    compare_parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Ausgabepfad für den Vergleichsbericht (Markdown)",
    )
    compare_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Ausführliche Ausgabe",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Setup logging
    log_level = "DEBUG" if getattr(args, 'verbose', False) else "INFO"
    setup_logging(log_level=log_level)

    # Execute command
    try:
        if args.command == "review":
            run_review(args)
        elif args.command == "init":
            run_init(args)
        elif args.command == "parse-checklist":
            run_parse_checklist(args)
        elif args.command == "compare-vorjahr":
            run_compare_vorjahr(args)
    except FileNotFoundError as e:
        print(f"Fehler: Datei nicht gefunden - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        if getattr(args, 'verbose', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def run_review(args):
    """Execute the review command."""
    print("=" * 70)
    print("ANHANGSPRÜFER - Prüfungsunterstützung")
    print("=" * 70)
    print(DISCLAIMER)

    # Validate inputs
    if not args.notes_file.exists():
        raise FileNotFoundError(f"Anhang-Datei nicht gefunden: {args.notes_file}")

    # Initialize engine
    engine = ReviewEngine()

    # Run review
    print(f"\nPrüfe: {args.notes_file.name}")
    print("-" * 70)

    result = engine.review(
        notes_path=args.notes_file,
        checklist_path=args.checklist,
        ugb_source_path=args.ugb_source,
    )

    # Print summary
    engine.print_summary(result)

    # Generate report
    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"pruefungsprotokoll_{timestamp}.md")

    # Load checklist for report
    if args.checklist:
        loader = ChecklistLoader()
        checklist = loader.load_from_json(args.checklist)
    else:
        loader = ChecklistLoader()
        checklist = loader.load_default_checklist()

    # Generate report
    generator = MarkdownReportGenerator(checklist=checklist)

    if args.format == "html":
        generator.generate_word_compatible(result, output_path)
    else:
        generator.generate(result, output_path)

    print(f"\nPrüfungsprotokoll erstellt: {output_path}")
    print("\nHINWEIS: Das Protokoll erfordert Prüfervalidierung!")


def run_init(args):
    """Initialize project with default checklist."""
    print("Erstelle Standard-Checkliste...")

    loader = ChecklistLoader()
    checklist = loader.load_default_checklist()
    loader.save_to_json(checklist, args.output)

    print(f"Checkliste erstellt: {args.output}")
    print(f"  - {len(checklist.items)} Prüfungspunkte")
    print("\nSie können die Checkliste nach Bedarf anpassen.")


def run_parse_checklist(args):
    """Parse checklist from PDF."""
    print("WARNUNG: PDF-Parsing ist experimentell und fehleranfällig!")
    print("Eine manuelle Überprüfung des Ergebnisses ist erforderlich.")
    print("-" * 70)

    if not args.pdf_file.exists():
        raise FileNotFoundError(f"PDF nicht gefunden: {args.pdf_file}")

    loader = ChecklistLoader()
    checklist = loader.parse_pdf_checklist(args.pdf_file)
    loader.save_to_json(checklist, args.output)

    print(f"\nCheckliste extrahiert: {args.output}")
    print(f"  - {len(checklist.items)} Punkte erkannt")
    print("\nBitte prüfen Sie das Ergebnis manuell!")


def run_compare_vorjahr(args):
    """Execute the year-over-year comparison (Ziel 2)."""
    print("=" * 70)
    print("ANHANGSPRÜFER - Vorjahresvergleich (Ziel 2)")
    print("=" * 70)
    print(DISCLAIMER)

    if not args.current_pdf.exists():
        raise FileNotFoundError(f"Aktueller Anhang nicht gefunden: {args.current_pdf}")
    if not args.prior_pdf.exists():
        raise FileNotFoundError(f"Vorjahres-Anhang nicht gefunden: {args.prior_pdf}")

    print(f"\nAktueller Anhang: {args.current_pdf.name}")
    print(f"Vorjahres-Anhang: {args.prior_pdf.name}")
    print("-" * 70)
    print("Extrahiere Label/Zahl-Paare und vergleiche...")

    result = compare_anhaenge(args.current_pdf, args.prior_pdf)

    stats = result.stats
    print()
    print("Ergebnis:")
    print(f"  OK              : {stats.get('OK', 0)}")
    print(f"  ABWEICHUNG      : {stats.get('ABWEICHUNG', 0)}")
    print(f"  Nur aktuell     : {stats.get('NUR_AKTUELL', 0)}")
    print(f"  Nur vorjahr     : {stats.get('NUR_VORJAHR', 0)}")
    print(f"  Wert fehlt      : {stats.get('FEHLENDER_WERT', 0)}")
    print(f"  Gesamt          : {stats.get('GESAMT', 0)}")

    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"vorjahresvergleich_{timestamp}.md")

    generate_yoy_report(result, output_path)
    excel_path = output_path.with_suffix(".xlsx")
    generate_yoy_excel(result, excel_path)
    print(f"\nVergleichsbericht (Markdown): {output_path}")
    print(f"Vergleichsbericht (Excel)   : {excel_path}")
    print("\nHINWEIS: Heuristische Analyse - manuelle Validierung erforderlich!")


if __name__ == "__main__":
    main()
