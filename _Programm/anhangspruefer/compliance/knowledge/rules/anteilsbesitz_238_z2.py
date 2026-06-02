"""
Audit-Grade Rule: Anteilsbesitz nach § 238 Abs 1 Z 2 UGB

This module defines the explicit, formalized rule for the disclosure
requirement regarding shareholdings/participations under Austrian UGB.

Formalization scope: ONE checklist item, fully decomposed.
No generalizations. No probabilistic scoring.

Author: Audit Methodology Engineering
Status: Production-ready rule definition
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum
from datetime import date


# =============================================================================
# RULE DEFINITION
# =============================================================================

RULE_ID = "UGB_238_1_Z2_ANTEILSBESITZ"

LEGAL_BASIS = {
    "primary": "§ 238 Abs 1 Z 2 UGB",
    "related": [
        "§ 189a Z 4 UGB",      # Definition of Beteiligung (>= 20%)
        "§ 228 UGB",           # Balance sheet item Finanzanlagen
        "§ 241 Abs 2 UGB",     # Protective clause (Schutzklausel)
        "§ 242 Abs 1 Z 1 UGB", # Exemption for subsidiaries
    ],
    "effective_text": """
    Im Anhang sind anzugeben:
    [...]
    2. Name und Sitz der Unternehmen, an denen die Gesellschaft mindestens
    mit einem Fünftel beteiligt ist, unter Angabe des Anteils am Kapital
    sowie der Höhe des Eigenkapitals und des Ergebnisses des letzten
    Geschäftsjahrs, für das ein Abschluss aufgestellt worden ist.
    """,
}


class CompanySize(Enum):
    """Company size classification under UGB."""
    KLEIN = "klein"
    MITTELGROSS = "mittelgross"
    GROSS = "gross"


class DisclosureStatus(Enum):
    """
    Assessment status for a single disclosure element.

    Conservative classification - when in doubt, NOT_ASSESSABLE.
    """
    PRESENT = "present"           # Element clearly identified
    ABSENT = "absent"             # Element definitively missing
    NOT_ASSESSABLE = "not_assessable"  # Cannot determine automatically


@dataclass(frozen=True)
class ApplicabilityConditions:
    """
    Conditions under which § 238 Abs 1 Z 2 applies.

    This is NOT a probabilistic assessment - these are binary legal facts
    that the auditor must verify manually if unknown.
    """
    # Applies only to medium and large companies
    applicable_sizes: tuple[CompanySize, ...] = (
        CompanySize.MITTELGROSS,
        CompanySize.GROSS,
    )

    # Small companies are exempt under § 242 Abs 1 Z 1
    exemption_for_small: bool = True

    # Subsidiaries preparing consolidated statements may have exemptions
    # (§ 242 Abs 1 Z 2) - requires manual verification
    subsidiary_exemption_possible: bool = True

    # Threshold for "participation" under § 189a Z 4 UGB
    beteiligung_threshold_percent: float = 20.0


@dataclass(frozen=True)
class RequiredDisclosureElement:
    """
    One mandatory data field in the Anteilsbesitz disclosure.

    Each element has:
    - A clear identification rule
    - Known patterns of omission
    - Whether protective clause can apply
    """
    element_id: str
    name_de: str
    name_en: str
    is_mandatory: bool
    protective_clause_applicable: bool
    common_omission_patterns: tuple[str, ...]
    identification_keywords: tuple[str, ...]


# The four mandatory elements per § 238 Abs 1 Z 2 UGB
REQUIRED_ELEMENTS = (
    RequiredDisclosureElement(
        element_id="name_and_seat",
        name_de="Name und Sitz des Unternehmens",
        name_en="Name and registered seat",
        is_mandatory=True,
        protective_clause_applicable=False,  # Name cannot be omitted
        common_omission_patterns=(
            "Only company name, no city/country",
            "Abbreviated name without legal form",
        ),
        identification_keywords=(
            "GmbH", "AG", "KG", "OG", "e.U.",
            "Sitz", "Wien", "Graz", "Linz", "Salzburg",
        ),
    ),
    RequiredDisclosureElement(
        element_id="share_percentage",
        name_de="Anteil am Kapital (in %)",
        name_en="Percentage of shares held",
        is_mandatory=True,
        protective_clause_applicable=False,  # Percentage cannot be omitted
        common_omission_patterns=(
            "Stated as 'majority' without exact percentage",
            "Missing for indirect holdings",
        ),
        identification_keywords=(
            "%", "Prozent", "Anteil", "Beteiligung", "100", "50", "25", "20",
        ),
    ),
    RequiredDisclosureElement(
        element_id="equity_capital",
        name_de="Eigenkapital",
        name_en="Equity capital amount",
        is_mandatory=True,
        protective_clause_applicable=True,  # Can be omitted with § 241 Abs 2
        common_omission_patterns=(
            "No figures provided without explanation",
            "Prior year figures used without note",
            "Consolidated equity instead of standalone",
        ),
        identification_keywords=(
            "Eigenkapital", "EK", "EUR", "TEUR", "Kapital",
        ),
    ),
    RequiredDisclosureElement(
        element_id="last_year_result",
        name_de="Ergebnis des letzten Geschäftsjahrs",
        name_en="Result of last financial year",
        is_mandatory=True,
        protective_clause_applicable=True,  # Can be omitted with § 241 Abs 2
        common_omission_patterns=(
            "No result figure without explanation",
            "Only profit/loss indicator without amount",
            "Figures older than last completed year",
        ),
        identification_keywords=(
            "Ergebnis", "Jahresüberschuss", "Jahresfehlbetrag",
            "Gewinn", "Verlust", "Bilanzgewinn",
        ),
    ),
)


@dataclass
class AcceptableVariant:
    """
    Situations where professional judgment determines acceptability.

    These are NOT automatic passes - they are documented deviations
    that require auditor sign-off.
    """
    variant_id: str
    description: str
    legal_basis: Optional[str]
    requires_auditor_judgment: bool
    judgment_reason: str


ACCEPTABLE_VARIANTS = (
    AcceptableVariant(
        variant_id="protective_clause",
        description="Equity/result omitted with reference to § 241 Abs 2 UGB",
        legal_basis="§ 241 Abs 2 UGB",
        requires_auditor_judgment=True,
        judgment_reason="Auditor must verify that serious disadvantage would actually result",
    ),
    AcceptableVariant(
        variant_id="delayed_accounts",
        description="Financial statements of participation not yet available",
        legal_basis=None,
        requires_auditor_judgment=True,
        judgment_reason="Auditor must assess whether delay is reasonable and whether estimation was considered",
    ),
    AcceptableVariant(
        variant_id="immaterial_omission",
        description="Participation omitted due to immateriality",
        legal_basis="§ 196a UGB (Wesentlichkeit)",
        requires_auditor_judgment=True,
        judgment_reason="Auditor must verify materiality assessment; law requires disclosure at >= 20%",
    ),
    AcceptableVariant(
        variant_id="indirect_holding",
        description="Indirect holding disclosed only at group level",
        legal_basis=None,
        requires_auditor_judgment=True,
        judgment_reason="Auditor must assess whether separate disclosure was required",
    ),
)


@dataclass
class NonCompliancePattern:
    """
    Known patterns that indicate definite non-compliance.

    These are explicit failure modes, not heuristics.
    """
    pattern_id: str
    description: str
    severity: Literal["formal_deficiency", "material_omission"]
    detection_method: str
    false_positive_risk: Literal["low", "medium", "high"]


NON_COMPLIANCE_PATTERNS = (
    NonCompliancePattern(
        pattern_id="missing_entity",
        description="Participation in balance sheet (Finanzanlagen > 0) but no Anteilsbesitz disclosure exists",
        severity="material_omission",
        detection_method="Compare Finanzanlagen line items with Anteilsbesitz list count",
        false_positive_risk="medium",  # Could be held-for-sale or other classification
    ),
    NonCompliancePattern(
        pattern_id="missing_percentage",
        description="Entity listed but percentage share not stated",
        severity="formal_deficiency",
        detection_method="Check for presence of % symbol or 'Anteil' near entity name",
        false_positive_risk="low",
    ),
    NonCompliancePattern(
        pattern_id="missing_financials_no_clause",
        description="Equity/result missing without protective clause reference",
        severity="formal_deficiency",
        detection_method="Check for Eigenkapital/Ergebnis values AND § 241 reference",
        false_positive_risk="medium",  # Could be structured differently
    ),
    NonCompliancePattern(
        pattern_id="threshold_violation",
        description="Holdings between 20-100% exist but fewer than expected participations disclosed",
        severity="material_omission",
        detection_method="Count participations vs. balance sheet items requiring disclosure",
        false_positive_risk="high",  # Cannot reliably determine holdings from text
    ),
)


@dataclass
class EvidenceExpectation:
    """
    What the tool should look for as evidence of compliance.

    Note: Finding evidence is NOT proof of compliance.
    NOT finding evidence is NOT proof of non-compliance.
    """
    evidence_id: str
    description: str
    search_approach: str
    minimum_for_partial: str
    sufficient_for_compliant: str
    when_not_assessable: str


EVIDENCE_EXPECTATIONS = (
    EvidenceExpectation(
        evidence_id="anteilsbesitz_table",
        description="Structured table of participations",
        search_approach="Look for table headers: Name/Firma, Sitz, Anteil, Eigenkapital, Ergebnis",
        minimum_for_partial="At least one entity name found with partial data",
        sufficient_for_compliant="Table with all four columns populated for each row",
        when_not_assessable="No table structure detected; text-only disclosure unclear",
    ),
    EvidenceExpectation(
        evidence_id="entity_entries",
        description="Individual participation entries",
        search_approach="Pattern: [Company Name] [Legal Form] [City] [Percentage] [EUR amounts]",
        minimum_for_partial="Company names with some numeric values nearby",
        sufficient_for_compliant="Each company has all four data points identifiable",
        when_not_assessable="Cannot parse individual entries from running text",
    ),
    EvidenceExpectation(
        evidence_id="protective_clause_reference",
        description="Reference to § 241 Abs 2 UGB when data omitted",
        search_approach="Search for '§ 241', 'Schutzklausel', 'erheblicher Nachteil'",
        minimum_for_partial="N/A - either present or absent",
        sufficient_for_compliant="Explicit reference when Eigenkapital/Ergebnis missing",
        when_not_assessable="Partial reference without clear scope",
    ),
)


# =============================================================================
# EVALUATION LOGIC
# =============================================================================

@dataclass
class ElementAssessment:
    """Assessment of a single required element for one participation."""
    element_id: str
    status: DisclosureStatus
    extracted_value: Optional[str] = None
    location_reference: Optional[str] = None
    confidence_note: str = ""


@dataclass
class ParticipationAssessment:
    """Assessment of disclosure completeness for one participation."""
    entity_name: Optional[str]
    entity_identified: bool
    element_assessments: list[ElementAssessment] = field(default_factory=list)
    protective_clause_claimed: bool = False
    protective_clause_reference: Optional[str] = None


@dataclass
class RuleEvaluationResult:
    """
    Complete evaluation result for § 238 Abs 1 Z 2.

    The tool provides structured findings. The tool does NOT make
    final compliance determinations except in trivial cases.
    """
    rule_id: str = RULE_ID

    # Applicability (must be verified by auditor if unknown)
    applicability_status: Literal["applicable", "not_applicable", "unknown"] = "unknown"
    applicability_note: str = ""

    # What we found
    participations_found: list[ParticipationAssessment] = field(default_factory=list)
    total_participations_detected: int = 0

    # Comparison with balance sheet (if possible)
    finanzanlagen_mentioned: bool = False
    apparent_count_mismatch: bool = False
    count_mismatch_note: str = ""

    # Overall assessment
    compliance_status: Literal[
        "COMPLIANT",           # All elements found for all participations
        "PARTIALLY_COMPLIANT", # Some elements found, gaps identified
        "NOT_COMPLIANT",       # Clear omission detected
        "NOT_ASSESSABLE",      # Cannot determine automatically
    ] = "NOT_ASSESSABLE"

    compliance_reasoning: str = ""

    # What the auditor must still do
    auditor_actions_required: list[str] = field(default_factory=list)

    # Uncertainties
    uncertainties: list[str] = field(default_factory=list)


def determine_compliance_status(
    participations: list[ParticipationAssessment],
    finanzanlagen_present: bool,
) -> tuple[str, str, list[str]]:
    """
    Determine compliance status based on explicit rules.

    Returns: (status, reasoning, auditor_actions)

    Conservative logic:
    - COMPLIANT only if ALL elements found for ALL participations
    - NOT_ASSESSABLE if we cannot parse the structure
    - PARTIALLY_COMPLIANT if some but not all elements found
    - NOT_COMPLIANT only if definite omission detected
    """
    auditor_actions = []

    # Case 1: No participations detected at all
    if not participations:
        if finanzanlagen_present:
            # Balance sheet shows Finanzanlagen but no participations disclosed
            # This COULD be non-compliance, but we cannot be certain
            return (
                "NOT_ASSESSABLE",
                "Finanzanlagen in Bilanz erkennbar, aber keine Anteilsbesitz-Angaben "
                "automatisch identifiziert. Kann auf fehlende Angaben hindeuten oder "
                "auf andere Klassifizierung der Finanzanlagen.",
                [
                    "Prüfen ob Anteilsbesitz-Angaben vorhanden sind",
                    "Abgleich Finanzanlagen-Posten mit Angabepflicht",
                    "Prüfen ob Befreiungstatbestand vorliegt (§ 242 UGB)",
                ]
            )
        else:
            return (
                "NOT_ASSESSABLE",
                "Keine Anteilsbesitz-Angaben und keine Finanzanlagen automatisch "
                "identifiziert. Vollständigkeit kann nicht beurteilt werden.",
                [
                    "Manuell prüfen ob Beteiligungen bestehen",
                    "Bilanz auf Finanzanlagen prüfen",
                ]
            )

    # Case 2: Participations detected - assess completeness
    all_complete = True
    any_data_found = False
    clear_omissions = []

    for p in participations:
        if not p.entity_identified:
            continue

        for elem in p.element_assessments:
            if elem.status == DisclosureStatus.PRESENT:
                any_data_found = True
            elif elem.status == DisclosureStatus.ABSENT:
                all_complete = False
                # Check if protective clause covers this
                if elem.element_id in ("equity_capital", "last_year_result"):
                    if not p.protective_clause_claimed:
                        clear_omissions.append(
                            f"{p.entity_name}: {elem.element_id} fehlt ohne Schutzklausel"
                        )
                else:
                    # Name and percentage cannot be protected
                    clear_omissions.append(
                        f"{p.entity_name}: {elem.element_id} fehlt"
                    )
            else:  # NOT_ASSESSABLE
                all_complete = False

    # Determine status
    if all_complete and any_data_found:
        return (
            "COMPLIANT",
            "Alle erforderlichen Angaben für alle identifizierten Beteiligungen "
            "automatisch erkannt. Prüfervalidierung der Vollständigkeit erforderlich.",
            [
                "Vollständigkeit der Beteiligungsliste gegen Buchhaltung prüfen",
                "Richtigkeit der angegebenen Werte verifizieren",
            ]
        )

    if clear_omissions:
        return (
            "PARTIALLY_COMPLIANT",
            f"Beteiligungen identifiziert, aber Lücken erkannt: {'; '.join(clear_omissions[:3])}",
            [
                "Identifizierte Lücken mit Mandant klären",
                "Prüfen ob Angaben an anderer Stelle im Anhang",
                "Bei Fehlen: Managementletter-Punkt",
            ]
        )

    if any_data_found:
        return (
            "PARTIALLY_COMPLIANT",
            "Einige Anteilsbesitz-Angaben erkannt, aber nicht alle Elemente "
            "automatisch zuordenbar. Strukturierte Prüfung erforderlich.",
            [
                "Vollständigkeit aller vier Pflichtangaben je Beteiligung prüfen",
                "Tabellenstruktur manuell analysieren",
            ]
        )

    return (
        "NOT_ASSESSABLE",
        "Angaben nicht eindeutig interpretierbar.",
        [
            "Manuelle Analyse des Anteilsbesitz-Abschnitts",
        ]
    )


# =============================================================================
# AUDITOR JUDGMENT REQUIREMENTS
# =============================================================================

AUDITOR_JUDGMENT_REQUIRED = True

JUDGMENT_REASONS = [
    "Vollständigkeit der Liste (alle Beteiligungen >= 20% erfasst?) kann nicht automatisch geprüft werden",
    "Wesentlichkeit von Abweichungen erfordert fachliche Einschätzung",
    "Angemessenheit der Schutzklausel-Anwendung ist Ermessensfrage",
    "Richtigkeit der angegebenen Eigenkapital/Ergebnis-Zahlen erfordert Abstimmung mit Unterlagen",
    "Aktualität der Zahlen (letztes verfügbares Geschäftsjahr) erfordert Prüfung",
]


# =============================================================================
# PYTHON STRUCTURES FOR INTEGRATION
# =============================================================================

RULE_SCHEMA = {
    "rule_id": RULE_ID,
    "legal_basis": LEGAL_BASIS,
    "applicability": {
        "company_sizes": ["mittelgross", "gross"],
        "exemptions": ["klein", "qualifying_subsidiary"],
        "threshold": "20% Beteiligung",
    },
    "required_elements": [
        {
            "id": elem.element_id,
            "name_de": elem.name_de,
            "mandatory": elem.is_mandatory,
            "protective_clause_applicable": elem.protective_clause_applicable,
            "keywords": list(elem.identification_keywords),
        }
        for elem in REQUIRED_ELEMENTS
    ],
    "acceptable_variants": [
        {
            "id": var.variant_id,
            "description": var.description,
            "requires_judgment": var.requires_auditor_judgment,
        }
        for var in ACCEPTABLE_VARIANTS
    ],
    "non_compliance_patterns": [
        {
            "id": pat.pattern_id,
            "description": pat.description,
            "severity": pat.severity,
            "false_positive_risk": pat.false_positive_risk,
        }
        for pat in NON_COMPLIANCE_PATTERNS
    ],
    "auditor_judgment_required": AUDITOR_JUDGMENT_REQUIRED,
    "judgment_reasons": JUDGMENT_REASONS,
}
