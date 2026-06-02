"""UGB disclosure requirements knowledge base."""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class CompanySize(Enum):
    """Company size categories under UGB."""
    KLEIN = "klein"
    MITTELGROSS = "mittelgroß"
    GROSS = "groß"
    ALL = "alle"


@dataclass
class DisclosureRequirement:
    """
    Represents a single UGB disclosure requirement.

    IMPORTANT: This is a simplified representation. The actual legal
    requirements are complex and require professional interpretation.
    This structure serves as audit support only.
    """
    requirement_id: str
    ugb_paragraph: str
    ugb_subsection: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    applicable_sizes: list[CompanySize] = field(default_factory=lambda: [CompanySize.ALL])
    is_mandatory: bool = True
    exemptions: list[str] = field(default_factory=list)
    related_requirements: list[str] = field(default_factory=list)

    # Audit guidance markers
    requires_quantitative_data: bool = False
    requires_qualitative_explanation: bool = False
    judgment_notes: str = ""

    def applies_to_size(self, size: CompanySize) -> bool:
        """Check if requirement applies to a company size."""
        return CompanySize.ALL in self.applicable_sizes or size in self.applicable_sizes


class UGBRequirements:
    """
    Knowledge base of UGB Anhang disclosure requirements (§§ 236-243).

    NOTE: This is a structured representation for audit support.
    The requirements herein are simplified and must not be considered
    as legal advice. Professional judgment is required.

    DOMAIN KNOWLEDGE REQUIRED: The keyword mappings and requirement
    interpretations should be reviewed and refined by audit professionals
    with UGB expertise.
    """

    def __init__(self):
        self.requirements: dict[str, DisclosureRequirement] = {}
        self._load_base_requirements()

    def _load_base_requirements(self) -> None:
        """
        Load the baseline UGB disclosure requirements.

        NOTE TO IMPLEMENTERS: These requirements are illustrative.
        A comprehensive implementation requires detailed mapping
        of all UGB §§ 236-243 provisions. This should be done in
        collaboration with audit domain experts.
        """
        requirements = [
            # § 236 - General provisions
            DisclosureRequirement(
                requirement_id="ugb_236_1",
                ugb_paragraph="§ 236",
                ugb_subsection="Abs 1",
                description="Angaben zu angewandten Bilanzierungs- und Bewertungsmethoden",
                keywords=[
                    "Bilanzierungsmethoden", "Bewertungsmethoden",
                    "Bewertungsgrundsätze", "Rechnungslegungsmethoden"
                ],
                requires_qualitative_explanation=True,
                judgment_notes="Prüfer muss Vollständigkeit und Angemessenheit der Methodendarstellung beurteilen",
            ),
            DisclosureRequirement(
                requirement_id="ugb_236_2",
                ugb_paragraph="§ 236",
                ugb_subsection="Abs 1",
                description="Abweichungen von Bilanzierungs- und Bewertungsmethoden mit Begründung",
                keywords=[
                    "Abweichung", "Methodenänderung", "Änderung der Bewertung",
                    "Stetigkeit"
                ],
                requires_qualitative_explanation=True,
                judgment_notes="Bei Abweichungen: Prüfung ob hinreichend begründet",
            ),

            # § 237 Z 1 - Accounting policies (already covered in 236)

            # § 237 Z 2 - Fixed assets schedule
            DisclosureRequirement(
                requirement_id="ugb_237_2",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 2",
                description="Entwicklung des Anlagevermögens (Anlagenspiegel)",
                keywords=[
                    "Anlagenspiegel", "Anlagevermögen", "Entwicklung",
                    "Zugänge", "Abgänge", "Abschreibungen", "Zuschreibungen"
                ],
                applicable_sizes=[CompanySize.MITTELGROSS, CompanySize.GROSS],
                requires_quantitative_data=True,
                judgment_notes="Vollständigkeit der Bewegungen prüfen, Abstimmung mit Bilanz",
            ),

            # § 237 Z 3 - Financial assets
            DisclosureRequirement(
                requirement_id="ugb_237_3",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 3",
                description="Angaben zu Finanzanlagen und verbundenen Unternehmen",
                keywords=[
                    "Finanzanlagen", "Beteiligungen", "verbundene Unternehmen",
                    "Anteile", "Anteilsbesitz"
                ],
                requires_quantitative_data=True,
                requires_qualitative_explanation=True,
                judgment_notes="Beteiligungsliste auf Vollständigkeit prüfen",
            ),

            # § 237 Z 4 - Receivables with maturity > 1 year
            DisclosureRequirement(
                requirement_id="ugb_237_4",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 4",
                description="Forderungen mit Restlaufzeit > 1 Jahr",
                keywords=[
                    "Forderungen", "Restlaufzeit", "langfristig",
                    "mehr als ein Jahr"
                ],
                requires_quantitative_data=True,
                judgment_notes="Fristigkeitsangaben auf Plausibilität prüfen",
            ),

            # § 237 Z 5 - Liabilities by maturity
            DisclosureRequirement(
                requirement_id="ugb_237_5",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 5",
                description="Verbindlichkeiten nach Restlaufzeiten",
                keywords=[
                    "Verbindlichkeiten", "Restlaufzeit", "bis 1 Jahr",
                    "1 bis 5 Jahre", "über 5 Jahre"
                ],
                requires_quantitative_data=True,
                judgment_notes="Fristigkeitsgliederung auf Vollständigkeit prüfen",
            ),

            # § 237 Z 6 - Secured liabilities
            DisclosureRequirement(
                requirement_id="ugb_237_6",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 6",
                description="Durch Pfandrechte oder ähnliche Rechte gesicherte Verbindlichkeiten",
                keywords=[
                    "Sicherheit", "Pfandrecht", "besichert", "Grundpfandrecht",
                    "Sicherungsübereignung"
                ],
                requires_quantitative_data=True,
                requires_qualitative_explanation=True,
                judgment_notes="Art und Umfang der Besicherungen auf Vollständigkeit prüfen",
            ),

            # § 237 Z 7 - Provisions
            DisclosureRequirement(
                requirement_id="ugb_237_7",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 7",
                description="Erläuterung wesentlicher sonstiger Rückstellungen",
                keywords=[
                    "Rückstellungen", "sonstige Rückstellungen", "wesentlich",
                    "Pensionsrückstellungen", "Abfertigungsrückstellungen"
                ],
                requires_qualitative_explanation=True,
                judgment_notes="Wesentlichkeitsgrenzen beachten, Erläuterungstiefe prüfen",
            ),

            # § 237 Z 8 - Contingent liabilities
            DisclosureRequirement(
                requirement_id="ugb_237_8",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 8",
                description="Haftungsverhältnisse (Eventualverbindlichkeiten)",
                keywords=[
                    "Haftungsverhältnisse", "Eventualverbindlichkeiten",
                    "Bürgschaften", "Garantien", "Wechselverbindlichkeiten"
                ],
                requires_quantitative_data=True,
                judgment_notes="Vollständigkeit der Haftungsverhältnisse kritisch prüfen",
            ),

            # § 237 Z 9 - Other financial obligations
            DisclosureRequirement(
                requirement_id="ugb_237_9",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 9",
                description="Sonstige finanzielle Verpflichtungen (nicht bilanziert)",
                keywords=[
                    "finanzielle Verpflichtungen", "nicht in Bilanz",
                    "Mietverträge", "Leasingverträge", "Bestellobligo"
                ],
                requires_quantitative_data=True,
                judgment_notes="Off-balance-sheet Verpflichtungen vollständig erfassen",
            ),

            # § 237 Z 10 - Revenue breakdown
            DisclosureRequirement(
                requirement_id="ugb_237_10",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 10",
                description="Aufgliederung der Umsatzerlöse",
                keywords=[
                    "Umsatzerlöse", "Aufgliederung", "Tätigkeitsbereiche",
                    "geografische Märkte"
                ],
                applicable_sizes=[CompanySize.MITTELGROSS, CompanySize.GROSS],
                requires_quantitative_data=True,
                judgment_notes="Sinnhaftigkeit der Gliederungsebenen beurteilen",
            ),

            # § 237 Z 11 - Average number of employees
            DisclosureRequirement(
                requirement_id="ugb_237_11",
                ugb_paragraph="§ 237",
                ugb_subsection="Z 11",
                description="Durchschnittliche Zahl der Arbeitnehmer während des Geschäftsjahres",
                keywords=[
                    "Arbeitnehmer", "Mitarbeiter", "durchschnittlich",
                    "Beschäftigte", "Personalstand"
                ],
                requires_quantitative_data=True,
                judgment_notes="Berechnungsmethode und Gruppierung prüfen",
            ),

            # § 239 - Personnel disclosures
            DisclosureRequirement(
                requirement_id="ugb_239",
                ugb_paragraph="§ 239",
                ugb_subsection="",
                description="Angaben zu Löhnen, Gehältern, Vergütungen für Organe",
                keywords=[
                    "Vergütung", "Bezüge", "Gehälter", "Löhne",
                    "Geschäftsführer", "Vorstand", "Aufsichtsrat"
                ],
                applicable_sizes=[CompanySize.MITTELGROSS, CompanySize.GROSS],
                requires_quantitative_data=True,
                judgment_notes="Vollständigkeit der Organvergütungen, Einzelangaben vs. Gesamtbetrag",
            ),

            # § 240 - Equity movements
            DisclosureRequirement(
                requirement_id="ugb_240",
                ugb_paragraph="§ 240",
                ugb_subsection="",
                description="Entwicklung der Bestandteile des Eigenkapitals",
                keywords=[
                    "Eigenkapital", "Eigenkapitalspiegel", "Gewinnrücklage",
                    "Kapitalrücklage", "Stammkapital", "Bilanzgewinn"
                ],
                applicable_sizes=[CompanySize.MITTELGROSS, CompanySize.GROSS],
                requires_quantitative_data=True,
                judgment_notes="Abstimmung mit Bilanz und GuV, Ergebnisverwendung",
            ),

            # § 241 - Names of management
            DisclosureRequirement(
                requirement_id="ugb_241",
                ugb_paragraph="§ 241",
                ugb_subsection="",
                description="Namen der Mitglieder der Geschäftsführung und des Aufsichtsrats",
                keywords=[
                    "Geschäftsführer", "Vorstand", "Aufsichtsrat",
                    "Mitglieder", "Name"
                ],
                requires_qualitative_explanation=True,
                judgment_notes="Vollständigkeit der Angaben zu allen Organen prüfen",
            ),
        ]

        for req in requirements:
            self.requirements[req.requirement_id] = req

    def get_requirement(self, requirement_id: str) -> Optional[DisclosureRequirement]:
        """Get a requirement by ID."""
        return self.requirements.get(requirement_id)

    def get_requirements_for_paragraph(self, paragraph: str) -> list[DisclosureRequirement]:
        """Get all requirements for a specific UGB paragraph."""
        return [
            req for req in self.requirements.values()
            if req.ugb_paragraph == paragraph
        ]

    def get_requirements_for_size(self, size: CompanySize) -> list[DisclosureRequirement]:
        """Get all requirements applicable to a company size."""
        return [
            req for req in self.requirements.values()
            if req.applies_to_size(size)
        ]

    def get_all_keywords(self) -> set[str]:
        """Get all keywords across all requirements."""
        keywords = set()
        for req in self.requirements.values():
            keywords.update(req.keywords)
        return keywords

    def search_by_keyword(self, keyword: str) -> list[DisclosureRequirement]:
        """Find requirements matching a keyword."""
        keyword_lower = keyword.lower()
        return [
            req for req in self.requirements.values()
            if any(keyword_lower in kw.lower() for kw in req.keywords)
        ]

    def add_custom_requirement(self, requirement: DisclosureRequirement) -> None:
        """
        Add a custom requirement to the knowledge base.

        Use this to extend the baseline requirements with firm-specific
        or client-specific disclosure requirements.
        """
        self.requirements[requirement.requirement_id] = requirement
