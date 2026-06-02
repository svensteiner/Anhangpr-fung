"""Configuration and constants for Anhangsprüfer."""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    # Paths
    working_directory: Path = Path(".")
    data_directory: Path = Path("./data")
    output_directory: Path = Path("./output")

    # Document parsing
    min_section_length: int = 50  # Minimum characters for valid section
    max_quote_length: int = 500  # Maximum length for evidence quotes

    # Search settings
    fuzzy_match_threshold: float = 0.75  # Threshold for fuzzy text matching
    max_evidence_per_item: int = 5  # Maximum evidence items to collect

    # Report settings
    report_language: str = "de"  # German
    include_raw_evidence: bool = True
    include_technical_details: bool = True

    @classmethod
    def default(cls) -> "Config":
        """Create default configuration."""
        return cls()


# UGB Disclosure Requirement Categories (§§ 236-243)
UGB_CATEGORIES = {
    "allgemein": {
        "title": "Allgemeine Angaben",
        "paragraphs": ["§ 236"],
        "description": "Allgemeine Anforderungen an den Anhang",
    },
    "bilanzierung": {
        "title": "Bilanzierungs- und Bewertungsmethoden",
        "paragraphs": ["§ 236 Abs 1", "§ 237 Z 1"],
        "description": "Angaben zu angewandten Bilanzierungs- und Bewertungsmethoden",
    },
    "anlagevermoegen": {
        "title": "Anlagevermögen",
        "paragraphs": ["§ 237 Z 2", "§ 238 Z 1"],
        "description": "Entwicklung des Anlagevermögens (Anlagenspiegel)",
    },
    "finanzanlagen": {
        "title": "Finanzanlagen und Beteiligungen",
        "paragraphs": ["§ 237 Z 3", "§ 238 Z 2"],
        "description": "Angaben zu Finanzanlagen und verbundenen Unternehmen",
    },
    "forderungen": {
        "title": "Forderungen",
        "paragraphs": ["§ 237 Z 4"],
        "description": "Angaben zu Forderungen mit Restlaufzeit > 1 Jahr",
    },
    "verbindlichkeiten": {
        "title": "Verbindlichkeiten",
        "paragraphs": ["§ 237 Z 5", "§ 237 Z 6"],
        "description": "Angaben zu Verbindlichkeiten nach Fristigkeiten und Besicherungen",
    },
    "rueckstellungen": {
        "title": "Rückstellungen",
        "paragraphs": ["§ 237 Z 7"],
        "description": "Angaben zu wesentlichen Rückstellungen",
    },
    "haftungsverhaeltnisse": {
        "title": "Haftungsverhältnisse",
        "paragraphs": ["§ 237 Z 8", "§ 238 Z 3"],
        "description": "Angaben zu Eventualverbindlichkeiten und Haftungen",
    },
    "sonstige_verpflichtungen": {
        "title": "Sonstige finanzielle Verpflichtungen",
        "paragraphs": ["§ 237 Z 9"],
        "description": "Nicht in der Bilanz ausgewiesene Verpflichtungen",
    },
    "umsatzerloese": {
        "title": "Umsatzerlöse",
        "paragraphs": ["§ 237 Z 10"],
        "description": "Aufgliederung der Umsatzerlöse",
    },
    "personal": {
        "title": "Personalangaben",
        "paragraphs": ["§ 237 Z 11", "§ 239"],
        "description": "Durchschnittliche Arbeitnehmerzahl und Vergütungen",
    },
    "organe": {
        "title": "Organe der Gesellschaft",
        "paragraphs": ["§ 239", "§ 241"],
        "description": "Angaben zu Geschäftsführern, Aufsichtsrat, Bezüge",
    },
    "eigenkapital": {
        "title": "Eigenkapital",
        "paragraphs": ["§ 240"],
        "description": "Entwicklung der Eigenkapitalbestandteile",
    },
    "latente_steuern": {
        "title": "Latente Steuern",
        "paragraphs": ["§ 238 Z 4"],
        "description": "Angaben zu latenten Steuern",
    },
    "sonstige_angaben": {
        "title": "Sonstige Pflichtangaben",
        "paragraphs": ["§ 238", "§ 241", "§ 242", "§ 243"],
        "description": "Weitere gesetzlich vorgeschriebene Angaben",
    },
}


# Size categories for Austrian companies under UGB
SIZE_CATEGORIES = {
    "klein": {
        "bilanzsumme_max": 5_000_000,
        "umsatz_max": 10_000_000,
        "mitarbeiter_max": 50,
        "criteria_count": 2,
    },
    "mittelgross": {
        "bilanzsumme_max": 20_000_000,
        "umsatz_max": 40_000_000,
        "mitarbeiter_max": 250,
        "criteria_count": 2,
    },
    "gross": {
        "bilanzsumme_min": 20_000_000,
        "umsatz_min": 40_000_000,
        "mitarbeiter_min": 250,
        "criteria_count": 2,
    },
}


# Common keywords for section detection in German notes documents
SECTION_KEYWORDS = {
    "bilanzierung": [
        "Bilanzierungs- und Bewertungsmethoden",
        "Bilanzierungsmethoden",
        "Bewertungsmethoden",
        "Bewertungsgrundsätze",
        "Rechnungslegungsgrundsätze",
        "Grundlagen der Rechnungslegung",
    ],
    "anlagevermoegen": [
        "Anlagevermögen",
        "Anlagenspiegel",
        "Entwicklung des Anlagevermögens",
        "Sachanlagen",
        "Immaterielle Vermögensgegenstände",
    ],
    "finanzanlagen": [
        "Finanzanlagen",
        "Beteiligungen",
        "Anteile an verbundenen Unternehmen",
        "Anteilsbesitz",
    ],
    "forderungen": [
        "Forderungen",
        "Forderungen und sonstige Vermögensgegenstände",
    ],
    "verbindlichkeiten": [
        "Verbindlichkeiten",
        "Verbindlichkeitenspiegel",
    ],
    "rueckstellungen": [
        "Rückstellungen",
        "Rückstellungsspiegel",
    ],
    "eigenkapital": [
        "Eigenkapital",
        "Eigenkapitalspiegel",
        "Entwicklung des Eigenkapitals",
    ],
    "haftung": [
        "Haftungsverhältnisse",
        "Eventualverbindlichkeiten",
        "Bürgschaften",
        "Garantien",
    ],
    "personal": [
        "Arbeitnehmer",
        "Mitarbeiter",
        "Personal",
        "Durchschnittliche Zahl",
    ],
    "organe": [
        "Organe",
        "Geschäftsführ",
        "Vorstand",
        "Aufsichtsrat",
    ],
    "umsatz": [
        "Umsatzerlöse",
        "Umsatz",
        "Erlöse",
    ],
}
