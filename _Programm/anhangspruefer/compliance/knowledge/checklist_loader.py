"""Checklist loading and management."""

from pathlib import Path
from typing import Optional
import json
import re

from ...models.checklist import Checklist, ChecklistItem
from ...utils.logging_config import get_logger

logger = get_logger("checklist_loader")


class ChecklistLoader:
    """
    Loads and manages audit checklists.

    Can load from:
    - JSON definition files (structured)
    - PDF files (requires parsing)
    - Manual definition

    NOTE: PDF parsing of checklists is inherently error-prone.
    For production use, consider maintaining a JSON master file
    that is manually curated from the PDF checklist.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def load_from_json(self, file_path: Path) -> Checklist:
        """
        Load checklist from JSON file.

        Expected format:
        {
            "name": "PwC Anhangscheckliste",
            "version": "2024",
            "items": [
                {
                    "item_id": "item_001",
                    "category": "Allgemeine Angaben",
                    "description": "...",
                    "ugb_references": ["§ 236 Abs 1"],
                    "search_keywords": ["..."],
                    "is_mandatory": true
                }
            ]
        }
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        checklist = Checklist(
            name=data.get("name", "Unnamed Checklist"),
            version=data.get("version", ""),
            source_file=str(file_path),
        )

        for item_data in data.get("items", []):
            item = ChecklistItem(
                item_id=item_data["item_id"],
                category=item_data.get("category", ""),
                description=item_data.get("description", ""),
                ugb_references=item_data.get("ugb_references", []),
                search_keywords=item_data.get("search_keywords", []),
                applicable_to=item_data.get("applicable_to", ["alle"]),
                is_mandatory=item_data.get("is_mandatory", True),
                notes=item_data.get("notes", ""),
                requires_professional_judgment=item_data.get(
                    "requires_professional_judgment", True
                ),
                judgment_guidance=item_data.get("judgment_guidance", ""),
            )
            checklist.add_item(item)

        logger.info(
            f"Loaded checklist '{checklist.name}' with {len(checklist.items)} items"
        )

        return checklist

    def load_default_checklist(self) -> Checklist:
        """
        Create a default UGB Anhang checklist.

        This provides a baseline checklist based on common UGB §§ 236-243
        disclosure requirements. Should be enhanced based on specific
        audit methodology (e.g., PwC checklist structure).

        NOTE: This is a simplified baseline. Domain experts should
        expand this with comprehensive checklist items.
        """
        checklist = Checklist(
            name="UGB Anhang Basisprüfungsprogramm",
            version="1.0",
        )

        # Define baseline items
        items = [
            # Category: Allgemeine Angaben
            ChecklistItem(
                item_id="chk_001",
                category="Allgemeine Angaben",
                description="Sind die angewandten Bilanzierungs- und Bewertungsmethoden vollständig und zutreffend dargestellt?",
                ugb_references=["§ 236 Abs 1"],
                search_keywords=[
                    "Bilanzierungsmethoden", "Bewertungsmethoden",
                    "Bewertungsgrundsätze", "Grundlagen"
                ],
                judgment_guidance="Prüfen ob alle wesentlichen Posten methodisch erläutert sind",
            ),
            ChecklistItem(
                item_id="chk_002",
                category="Allgemeine Angaben",
                description="Sind Abweichungen von Bilanzierungs- und Bewertungsmethoden gegenüber dem Vorjahr angegeben und begründet?",
                ugb_references=["§ 236 Abs 1"],
                search_keywords=[
                    "Abweichung", "Änderung", "Vorjahr", "Stetigkeit"
                ],
                judgment_guidance="Bei Methodenwechsel: Begründung und Auswirkungen prüfen",
            ),

            # Category: Anlagevermögen
            ChecklistItem(
                item_id="chk_010",
                category="Anlagevermögen",
                description="Ist die Entwicklung des Anlagevermögens (Anlagenspiegel) vollständig dargestellt?",
                ugb_references=["§ 237 Z 2"],
                search_keywords=[
                    "Anlagenspiegel", "Anlagevermögen", "Entwicklung",
                    "Zugänge", "Abgänge"
                ],
                applicable_to=["mittelgroß", "groß"],
                judgment_guidance="Abstimmung mit Bilanz, Vollständigkeit der Bewegungen",
            ),
            ChecklistItem(
                item_id="chk_011",
                category="Anlagevermögen",
                description="Sind außerplanmäßige Abschreibungen mit Begründung angegeben?",
                ugb_references=["§ 237 Z 2"],
                search_keywords=[
                    "außerplanmäßig", "Abschreibung", "Wertminderung",
                    "Wertberichtigung"
                ],
                judgment_guidance="Begründung auf Plausibilität prüfen",
            ),

            # Category: Forderungen
            ChecklistItem(
                item_id="chk_020",
                category="Forderungen und Verbindlichkeiten",
                description="Sind Forderungen mit einer Restlaufzeit von mehr als einem Jahr angegeben?",
                ugb_references=["§ 237 Z 4"],
                search_keywords=[
                    "Forderungen", "Restlaufzeit", "langfristig"
                ],
                judgment_guidance="Betrag und Art der langfristigen Forderungen prüfen",
            ),

            # Category: Verbindlichkeiten
            ChecklistItem(
                item_id="chk_030",
                category="Forderungen und Verbindlichkeiten",
                description="Sind Verbindlichkeiten nach Restlaufzeiten gegliedert?",
                ugb_references=["§ 237 Z 5"],
                search_keywords=[
                    "Verbindlichkeiten", "Restlaufzeit", "Fristigkeit"
                ],
                judgment_guidance="Gliederung: bis 1 Jahr, 1-5 Jahre, über 5 Jahre",
            ),
            ChecklistItem(
                item_id="chk_031",
                category="Forderungen und Verbindlichkeiten",
                description="Sind gesicherte Verbindlichkeiten unter Angabe von Art und Form der Sicherheiten angegeben?",
                ugb_references=["§ 237 Z 6"],
                search_keywords=[
                    "Sicherheit", "besichert", "Pfandrecht", "Hypothek"
                ],
                judgment_guidance="Art der Sicherheiten und deren Umfang prüfen",
            ),

            # Category: Rückstellungen
            ChecklistItem(
                item_id="chk_040",
                category="Rückstellungen",
                description="Sind wesentliche sonstige Rückstellungen erläutert?",
                ugb_references=["§ 237 Z 7"],
                search_keywords=[
                    "Rückstellungen", "wesentlich", "Erläuterung"
                ],
                judgment_guidance="Wesentlichkeitsgrenze anwenden, Erläuterungstiefe beurteilen",
            ),

            # Category: Haftungsverhältnisse
            ChecklistItem(
                item_id="chk_050",
                category="Haftungsverhältnisse",
                description="Sind Haftungsverhältnisse (Eventualverbindlichkeiten) vollständig angegeben?",
                ugb_references=["§ 237 Z 8", "§ 199"],
                search_keywords=[
                    "Haftungsverhältnisse", "Eventualverbindlichkeiten",
                    "Bürgschaften", "Garantien"
                ],
                judgment_guidance="Vollständigkeit kritisch hinterfragen, Managementbefragung",
            ),
            ChecklistItem(
                item_id="chk_051",
                category="Haftungsverhältnisse",
                description="Sind sonstige finanzielle Verpflichtungen angegeben?",
                ugb_references=["§ 237 Z 9"],
                search_keywords=[
                    "finanzielle Verpflichtungen", "Leasing",
                    "Mietverträge", "Bestellobligo"
                ],
                judgment_guidance="Off-Balance-Sheet Verpflichtungen erfragen",
            ),

            # Category: Umsatzerlöse
            ChecklistItem(
                item_id="chk_060",
                category="GuV-Angaben",
                description="Sind die Umsatzerlöse nach Tätigkeitsbereichen und geografischen Märkten aufgegliedert?",
                ugb_references=["§ 237 Z 10"],
                search_keywords=[
                    "Umsatzerlöse", "Aufgliederung", "Segmente"
                ],
                applicable_to=["mittelgroß", "groß"],
                judgment_guidance="Segmentierung auf Sinnhaftigkeit prüfen",
            ),

            # Category: Personal
            ChecklistItem(
                item_id="chk_070",
                category="Personalangaben",
                description="Ist die durchschnittliche Zahl der Arbeitnehmer angegeben?",
                ugb_references=["§ 237 Z 11"],
                search_keywords=[
                    "Arbeitnehmer", "Mitarbeiter", "durchschnittlich",
                    "Personalstand"
                ],
                judgment_guidance="Berechnungsmethode und Gliederung prüfen",
            ),
            ChecklistItem(
                item_id="chk_071",
                category="Personalangaben",
                description="Sind Vergütungen für Geschäftsführer/Vorstand und Aufsichtsrat angegeben?",
                ugb_references=["§ 239"],
                search_keywords=[
                    "Vergütung", "Bezüge", "Geschäftsführer",
                    "Vorstand", "Aufsichtsrat"
                ],
                applicable_to=["mittelgroß", "groß"],
                judgment_guidance="Vollständigkeit, ggf. Schutzklausel beachten",
            ),

            # Category: Organe
            ChecklistItem(
                item_id="chk_080",
                category="Organangaben",
                description="Sind die Namen der Geschäftsführer/Vorstände und Aufsichtsratsmitglieder angegeben?",
                ugb_references=["§ 241"],
                search_keywords=[
                    "Geschäftsführer", "Vorstand", "Aufsichtsrat",
                    "Namen", "Mitglieder"
                ],
                judgment_guidance="Vollständigkeit mit HR-Auszug abgleichen",
            ),

            # Category: Eigenkapital
            ChecklistItem(
                item_id="chk_090",
                category="Eigenkapital",
                description="Ist die Entwicklung der Eigenkapitalbestandteile dargestellt?",
                ugb_references=["§ 240"],
                search_keywords=[
                    "Eigenkapital", "Entwicklung", "Eigenkapitalspiegel"
                ],
                applicable_to=["mittelgroß", "groß"],
                judgment_guidance="Abstimmung mit Bilanz, Ergebnisverwendung prüfen",
            ),
        ]

        for item in items:
            checklist.add_item(item)

        logger.info(
            f"Created default checklist with {len(checklist.items)} items"
        )

        return checklist

    def save_to_json(self, checklist: Checklist, file_path: Path) -> None:
        """Save checklist to JSON file for future use."""
        data = {
            "name": checklist.name,
            "version": checklist.version,
            "items": [
                {
                    "item_id": item.item_id,
                    "category": item.category,
                    "description": item.description,
                    "ugb_references": item.ugb_references,
                    "search_keywords": item.search_keywords,
                    "applicable_to": item.applicable_to,
                    "is_mandatory": item.is_mandatory,
                    "notes": item.notes,
                    "requires_professional_judgment": item.requires_professional_judgment,
                    "judgment_guidance": item.judgment_guidance,
                }
                for item in checklist.items
            ]
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved checklist to {file_path}")

    def parse_pdf_checklist(self, file_path: Path) -> Checklist:
        """
        Attempt to parse a checklist from PDF.

        WARNING: This is experimental and likely incomplete.
        PDF parsing of complex checklists is error-prone.
        Manual curation of the resulting checklist is strongly recommended.

        NOTE TO IMPLEMENTERS: This method should be enhanced based
        on the specific structure of the PwC checklist PDF.
        """
        from ...parsers.pdf_parser import PDFParser

        parser = PDFParser()
        text = parser.extract_text(file_path)

        checklist = Checklist(
            name="Parsed Checklist (requires manual review)",
            version="auto-parsed",
            source_file=str(file_path),
        )

        # Basic heuristic parsing - looks for numbered items with UGB references
        # Pattern: number. Description text (§ xxx)
        item_pattern = re.compile(
            r"(\d+(?:\.\d+)?)\.\s+(.+?)(?:\(([§\s\d,]+)\))?(?:\n|$)",
            re.MULTILINE
        )

        current_category = "Allgemein"
        item_count = 0

        for match in item_pattern.finditer(text):
            number = match.group(1)
            description = match.group(2).strip()
            ugb_refs = match.group(3)

            if len(description) < 10:
                continue

            # Parse UGB references
            references = []
            if ugb_refs:
                ref_matches = re.findall(r"§\s*\d+[a-z]?", ugb_refs)
                references = list(set(ref_matches))

            item_count += 1
            item = ChecklistItem(
                item_id=f"parsed_{item_count:03d}",
                category=current_category,
                description=description,
                ugb_references=references,
                search_keywords=self._extract_keywords(description),
            )
            checklist.add_item(item)

        logger.warning(
            f"Parsed {len(checklist.items)} items from PDF. "
            "Manual review required!"
        )

        return checklist

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract potential keywords from description text."""
        # Remove common stop words and short words
        stop_words = {
            "der", "die", "das", "und", "oder", "mit", "für", "von",
            "ist", "sind", "werden", "wurde", "hat", "haben", "wird",
            "bei", "als", "auch", "auf", "aus", "dem", "den", "des",
            "ein", "eine", "einer", "einem", "einen", "sich", "nicht",
            "nach", "über", "unter", "vor", "zum", "zur"
        }

        words = re.findall(r"\b[A-ZÄÖÜa-zäöüß]{4,}\b", text)
        keywords = [
            w for w in words
            if w.lower() not in stop_words
        ]

        # Return unique keywords, max 5
        seen = set()
        unique = []
        for kw in keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique.append(kw)
                if len(unique) >= 5:
                    break

        return unique
