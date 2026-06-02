#!/usr/bin/env python3
"""
Anhangsprüfer - Quick Start Script

Führt eine Prüfung des Anhangs durch und erstellt ein Prüfungsprotokoll.

WICHTIGER HINWEIS:
Dieses Tool dient ausschließlich der Prüfungsunterstützung und ersetzt
NICHT die fachliche Beurteilung durch einen qualifizierten Wirtschaftsprüfer.
"""

import sys
from pathlib import Path

# Add the package to path for direct execution
sys.path.insert(0, str(Path(__file__).parent))

from anhangspruefer.review.engine import ReviewEngine
from anhangspruefer.reporting.markdown_report import MarkdownReportGenerator
from anhangspruefer.knowledge.checklist_loader import ChecklistLoader
from anhangspruefer.utils.logging_config import setup_logging
from anhangspruefer import DISCLAIMER
from datetime import datetime


def main():
    """Run a review with default settings."""
    print("=" * 70)
    print("ANHANGSPRÜFER - Prüfungsunterstützung für den UGB-Anhang")
    print("=" * 70)
    print(DISCLAIMER)

    # Setup
    setup_logging(log_level="INFO")

    # Default paths - adjust as needed
    working_dir = Path(__file__).parent

    # Find input files
    notes_file = working_dir / "Anhang 2024.pdf"
    ugb_file = working_dir / "UGB, Fassung vom 13.01.2026.rtf"
    output_dir = working_dir / "output"

    # Validate
    if not notes_file.exists():
        print(f"FEHLER: Anhang-Datei nicht gefunden: {notes_file}")
        print("\nBitte stellen Sie sicher, dass die Datei 'Anhang 2024.pdf' im")
        print("Arbeitsverzeichnis vorhanden ist.")
        return 1

    print(f"\nEingabedateien:")
    print(f"  Anhang: {notes_file}")
    print(f"  UGB: {ugb_file if ugb_file.exists() else 'nicht gefunden'}")
    print("-" * 70)

    # Initialize
    engine = ReviewEngine()
    loader = ChecklistLoader()

    # Load default checklist
    print("\nLade Standard-Checkliste...")
    checklist = loader.load_default_checklist()
    print(f"  {len(checklist.items)} Prüfungspunkte geladen")

    # Save checklist for reference
    output_dir.mkdir(exist_ok=True)
    checklist_path = output_dir / "verwendete_checkliste.json"
    loader.save_to_json(checklist, checklist_path)

    # Run review
    print("\nStarte Prüfung...")
    print("-" * 70)

    try:
        result = engine.review(
            notes_path=notes_file,
            ugb_source_path=ugb_file if ugb_file.exists() else None,
        )
    except Exception as e:
        print(f"\nFEHLER bei der Prüfung: {e}")
        print("\nMögliche Ursachen:")
        print("  - pypdf Bibliothek nicht installiert (pip install pypdf)")
        print("  - PDF-Datei ist beschädigt oder passwortgeschützt")
        return 1

    # Print summary
    engine.print_summary(result)

    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"pruefungsprotokoll_{timestamp}.md"

    generator = MarkdownReportGenerator(checklist=checklist)
    generator.generate(result, report_path)

    # Also generate HTML version
    html_path = output_dir / f"pruefungsprotokoll_{timestamp}.html"
    generator.generate_word_compatible(result, html_path)

    print("\n" + "=" * 70)
    print("AUSGABE")
    print("=" * 70)
    print(f"Prüfungsprotokoll (Markdown): {report_path}")
    print(f"Prüfungsprotokoll (HTML/Word): {html_path}")
    print(f"Verwendete Checkliste: {checklist_path}")
    print()
    print("WICHTIG:")
    print("Alle Bewertungen sind vorläufig und erfordern Prüfervalidierung!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
