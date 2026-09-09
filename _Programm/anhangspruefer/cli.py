"""Command-line interface for Anhangsprüfer."""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from . import __version__, DISCLAIMER
from .compliance.knowledge.checklist_loader import ChecklistLoader
from .compliance.knowledge.relevance import require_company_profile
from .compliance.reporting.checklist_excel import generate_checklist_xlsx
from .compliance.ugb_pipeline import review_checklist
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
        help="Pfad zum Anhang-Dokument (PDF oder Word)",
    )
    review_parser.add_argument(
        "--rechtsform",
        required=True,
        choices=["gmbh", "ag"],
        help="GmbH oder AG (ohne Angabe startet nichts)",
    )
    review_parser.add_argument(
        "--groessenklasse",
        required=True,
        choices=["klein", "mittel", "gross"],
        help="klein, mittel oder groß (ohne Angabe startet nichts)",
    )
    review_parser.add_argument(
        "-c", "--checklist",
        type=Path,
        help="Pfad zur Checklisten-Datei (Excel oder JSON)",
    )
    review_parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Ausgabepfad für die Excel-Checkliste",
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
    """Modus 3 zweistufig – ohne Gesellschaft startet nichts."""
    print("=" * 70)
    print("ANHANGSPRÜFER - UGB-Inhaltsprüfung")
    print("=" * 70)
    print(DISCLAIMER)

    if not args.notes_file.exists():
        raise FileNotFoundError(f"Anhang-Datei nicht gefunden: {args.notes_file}")

    legal_form, size_class = require_company_profile(args.rechtsform, args.groessenklasse)
    loader = ChecklistLoader()
    if args.checklist and args.checklist.suffix.lower() in {".xlsx", ".xlsm"}:
        checklist = loader.load_from_xlsx(args.checklist)
    elif args.checklist:
        checklist = loader.load_from_json(args.checklist)
    else:
        checklist = loader.load_default_checklist()

    print(f"\nPrüfe: {args.notes_file.name}")
    print(f"Gesellschaft: {legal_form} {size_class}")
    print("-" * 70)

    result, info = review_checklist(args.notes_file, checklist, legal_form, size_class)

    output_path = args.output
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"UGB-Checkliste_{timestamp}.xlsx")
    elif output_path.suffix.lower() != ".xlsx":
        output_path = output_path.with_suffix(".xlsx")

    generate_checklist_xlsx(
        checklist, result, output_path,
        legal_form=legal_form, size_class=size_class,
    )
    form_txt = "GmbH" if legal_form == "gmbh" else "AG"
    size_txt = {"klein": "klein", "mittel": "mittel", "gross": "groß"}[size_class]
    print(
        f"\nFür {form_txt} {size_txt}: "
        f"{info.get('zu_pruefen', 0)} von {len(result.findings)} Fragen geprüft."
    )
    print(f"Checkliste: {output_path}")
    print("Kein stilles unbekannt. Offene Punkte in Excel bestätigen.")


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
